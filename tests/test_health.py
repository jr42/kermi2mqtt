"""Tests for the /healthz, /readyz, /status HTTP endpoints."""

from __future__ import annotations

import time
from dataclasses import dataclass

import pytest
from aiohttp.test_utils import TestClient, TestServer

from kermi2mqtt.config import HealthConfig
from kermi2mqtt.health import HealthServer


@dataclass
class FakeIntegration:
    poll_interval: float = 30.0


@dataclass
class FakeConfig:
    integration: FakeIntegration


class FakeBridge:
    """Stands in for Bridge — HealthServer only needs these two attributes."""

    def __init__(self, poll_interval: float = 30.0) -> None:
        self.config = FakeConfig(integration=FakeIntegration(poll_interval=poll_interval))
        self.last_successful_poll_monotonic: float | None = None


class FakeClient:
    def __init__(self, connected: bool = False, ever_connected: bool = False) -> None:
        self.is_connected = connected
        self.has_ever_connected = ever_connected or connected


def make_server(
    *,
    bridge: FakeBridge | None = None,
    mqtt: FakeClient | None = None,
    device: FakeClient | None = None,
    stale_after: float | None = None,
) -> HealthServer:
    return HealthServer(
        config=HealthConfig(stale_after_seconds=stale_after),
        bridge=bridge or FakeBridge(),  # type: ignore[arg-type]
        mqtt_client=mqtt or FakeClient(connected=True),  # type: ignore[arg-type]
        device_client=device or FakeClient(connected=True),  # type: ignore[arg-type]
    )


async def _client(server: HealthServer) -> TestClient:
    test_server = TestServer(server.build_app())
    client = TestClient(test_server)
    await client.start_server()
    return client


async def test_healthz_ok() -> None:
    bridge = FakeBridge()
    bridge.last_successful_poll_monotonic = time.monotonic()
    server = make_server(bridge=bridge)
    client = await _client(server)
    try:
        resp = await client.get("/healthz")
        assert resp.status == 200
        body = await resp.json()
        assert body["mqtt"] is True
        assert body["device"] is True
        assert body["last_poll_seconds_ago"] is not None
        assert body["last_poll_seconds_ago"] < 1
    finally:
        await client.close()


async def test_healthz_stale() -> None:
    bridge = FakeBridge(poll_interval=30.0)
    bridge.last_successful_poll_monotonic = time.monotonic() - 120.0  # > 60s default
    server = make_server(bridge=bridge)
    client = await _client(server)
    try:
        resp = await client.get("/healthz")
        assert resp.status == 503
    finally:
        await client.close()


async def test_healthz_mqtt_disconnected() -> None:
    bridge = FakeBridge()
    bridge.last_successful_poll_monotonic = time.monotonic()
    server = make_server(
        bridge=bridge,
        mqtt=FakeClient(connected=False, ever_connected=True),
    )
    client = await _client(server)
    try:
        resp = await client.get("/healthz")
        assert resp.status == 503
    finally:
        await client.close()


async def test_healthz_device_disconnected() -> None:
    bridge = FakeBridge()
    bridge.last_successful_poll_monotonic = time.monotonic()
    server = make_server(
        bridge=bridge,
        device=FakeClient(connected=False, ever_connected=True),
    )
    client = await _client(server)
    try:
        resp = await client.get("/healthz")
        assert resp.status == 503
    finally:
        await client.close()


async def test_healthz_never_polled() -> None:
    bridge = FakeBridge()
    # last_successful_poll_monotonic stays None
    server = make_server(bridge=bridge)
    client = await _client(server)
    try:
        resp = await client.get("/healthz")
        assert resp.status == 503
        body = await resp.json()
        assert body["last_poll_seconds_ago"] is None
    finally:
        await client.close()


async def test_readyz_waits_for_first_connect() -> None:
    server = make_server(
        mqtt=FakeClient(connected=True, ever_connected=True),
        device=FakeClient(connected=False, ever_connected=False),
    )
    client = await _client(server)
    try:
        resp = await client.get("/readyz")
        assert resp.status == 503
    finally:
        await client.close()


async def test_readyz_sticky() -> None:
    # Both have connected in the past but are currently disconnected.
    server = make_server(
        mqtt=FakeClient(connected=False, ever_connected=True),
        device=FakeClient(connected=False, ever_connected=True),
    )
    client = await _client(server)
    try:
        resp = await client.get("/readyz")
        assert resp.status == 200
    finally:
        await client.close()


async def test_status_payload() -> None:
    bridge = FakeBridge(poll_interval=30.0)
    bridge.last_successful_poll_monotonic = time.monotonic() - 5.0
    server = make_server(bridge=bridge)
    client = await _client(server)
    try:
        resp = await client.get("/status")
        assert resp.status == 200
        body = await resp.json()
        expected_keys = {
            "version",
            "mqtt",
            "device",
            "mqtt_ever_connected",
            "device_ever_connected",
            "last_poll_seconds_ago",
            "stale_after_seconds",
        }
        assert set(body.keys()) == expected_keys
        assert body["stale_after_seconds"] == 60.0  # max(2*30, 60)
    finally:
        await client.close()


@pytest.mark.parametrize(
    ("poll_interval", "expected"),
    [(30.0, 60.0), (45.0, 90.0), (15.0, 60.0)],
)
async def test_default_stale_after(poll_interval: float, expected: float) -> None:
    bridge = FakeBridge(poll_interval=poll_interval)
    server = make_server(bridge=bridge)
    assert server._stale_after_seconds() == expected


async def test_explicit_stale_after_overrides_default() -> None:
    bridge = FakeBridge(poll_interval=30.0)
    server = make_server(bridge=bridge, stale_after=10.0)
    assert server._stale_after_seconds() == 10.0
