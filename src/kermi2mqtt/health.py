"""
HTTP health-check server for Kubernetes probes.

Exposes three endpoints bound to the address/port configured via `health:` in
config.yaml:

- `GET /healthz` — liveness. 200 when MQTT + device clients are connected AND a
  successful poll cycle has completed recently; 503 otherwise. The staleness
  check is the important part: `is_connected` can report True while a socket is
  wedged (DNS flap, CNI identity drift, etc.), so we additionally require that
  `Bridge.poll_and_publish()` finished within `stale_after_seconds`.
- `GET /readyz` — readiness. 200 once both clients have completed at least one
  successful connect, 503 before that. Readiness is sticky after the first
  successful connect — we don't want pods flapping out of the Service during
  normal reconnect cycles; liveness handles extended wedges.
- `GET /status` (also `/`) — always 200; returns the raw signals as JSON for
  debugging.

Default staleness window: `max(2 * integration.poll_interval, 60)` — generous
enough to absorb a single missed poll, tight enough to act on a real wedge.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from aiohttp import web

from kermi2mqtt import __version__

if TYPE_CHECKING:
    from kermi2mqtt.bridge import Bridge
    from kermi2mqtt.config import HealthConfig
    from kermi2mqtt.http_client import HttpClient
    from kermi2mqtt.modbus_client import ModbusClient
    from kermi2mqtt.mqtt_client import MQTTClient


logger = logging.getLogger(__name__)

_MIN_STALE_AFTER = 60.0


class HealthServer:
    """aiohttp-based liveness/readiness endpoint."""

    def __init__(
        self,
        config: HealthConfig,
        bridge: Bridge,
        mqtt_client: MQTTClient,
        device_client: HttpClient | ModbusClient,
    ) -> None:
        self.config = config
        self.bridge = bridge
        self.mqtt = mqtt_client
        self.device = device_client
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None

    def build_app(self) -> web.Application:
        """Build the aiohttp Application (exposed for test use)."""
        app = web.Application()
        app.router.add_get("/healthz", self._healthz)
        app.router.add_get("/readyz", self._readyz)
        app.router.add_get("/status", self._status)
        app.router.add_get("/", self._status)
        return app

    async def start(self) -> None:
        """Start the HTTP server."""
        app = self.build_app()
        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.config.host, self.config.port)
        await self._site.start()
        logger.info(
            f"Health server listening on http://{self.config.host}:{self.config.port}"
        )

    async def stop(self) -> None:
        """Stop the HTTP server cleanly."""
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
            self._site = None
            logger.info("Health server stopped")

    def _stale_after_seconds(self) -> float:
        if self.config.stale_after_seconds is not None:
            return float(self.config.stale_after_seconds)
        return max(2.0 * self.bridge.config.integration.poll_interval, _MIN_STALE_AFTER)

    def _snapshot(self, now: float) -> dict[str, Any]:
        last = self.bridge.last_successful_poll_monotonic
        return {
            "version": __version__,
            "mqtt": self.mqtt.is_connected,
            "device": self.device.is_connected,
            "mqtt_ever_connected": self.mqtt.has_ever_connected,
            "device_ever_connected": self.device.has_ever_connected,
            "last_poll_seconds_ago": None if last is None else round(now - last, 1),
            "stale_after_seconds": self._stale_after_seconds(),
        }

    async def _healthz(self, _request: web.Request) -> web.Response:
        now = time.monotonic()
        last = self.bridge.last_successful_poll_monotonic
        stale_after = self._stale_after_seconds()
        healthy = (
            self.mqtt.is_connected
            and self.device.is_connected
            and last is not None
            and (now - last) < stale_after
        )
        return web.json_response(self._snapshot(now), status=200 if healthy else 503)

    async def _readyz(self, _request: web.Request) -> web.Response:
        ready = self.mqtt.has_ever_connected and self.device.has_ever_connected
        return web.json_response(
            self._snapshot(time.monotonic()), status=200 if ready else 503
        )

    async def _status(self, _request: web.Request) -> web.Response:
        return web.json_response(self._snapshot(time.monotonic()))
