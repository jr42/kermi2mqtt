"""
MQTT client wrapper for aiomqtt.

Provides:
- Async MQTT publish/subscribe
- QoS handling for state and command topics
- Availability tracking
- Automatic reconnection with exponential backoff
- Clean shutdown handling

Note: Home Assistant discovery is handled by the ha_discovery module.
"""

import asyncio
import json
import logging
import ssl
from typing import Any, Callable

import aiomqtt

from kermi2mqtt.config import AdvancedConfig, MQTTConfig
from kermi2mqtt.models.device import KermiDevice

logger = logging.getLogger(__name__)


class MQTTClient:
    """
    Async MQTT client wrapper.

    Handles:
    - Publishing device state updates
    - Subscribing to command topics
    - Availability tracking

    Note: HA discovery is handled separately by the ha_discovery module.
    """

    def __init__(
        self,
        mqtt_config: MQTTConfig,
        advanced_config: AdvancedConfig,
    ):
        """
        Initialize MQTT client.

        Args:
            mqtt_config: MQTT broker configuration
            advanced_config: Advanced settings (QoS, reconnect delays, retain)
        """
        self.mqtt_config = mqtt_config
        self.advanced_config = advanced_config

        self.client: aiomqtt.Client | None = None
        self._connected = False
        self._reconnect_delay = advanced_config.mqtt_reconnect_delay
        self._max_reconnect_delay = advanced_config.mqtt_max_reconnect_delay

        # Command subscription (User Story 2)
        self._command_callback: Callable[[str, str], None] | None = None
        self._message_listener_task: asyncio.Task | None = None

    async def __aenter__(self) -> "MQTTClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.disconnect()

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._connected

    async def connect(self) -> None:
        """
        Connect to MQTT broker.

        Raises:
            ConnectionError: If connection fails
        """
        logger.info(
            f"Connecting to MQTT broker at {self.mqtt_config.host}:{self.mqtt_config.port}"
        )

        try:
            # Configure TLS if enabled
            tls_context = None
            if self.mqtt_config.tls_enabled:
                tls_context = ssl.create_default_context()

                # Load custom CA certificate if provided
                if self.mqtt_config.ca_certs:
                    tls_context.load_verify_locations(cafile=self.mqtt_config.ca_certs)

                # Load client certificate if provided
                if self.mqtt_config.certfile and self.mqtt_config.keyfile:
                    tls_context.load_cert_chain(
                        certfile=self.mqtt_config.certfile,
                        keyfile=self.mqtt_config.keyfile,
                    )

                # Disable certificate verification if requested (insecure!)
                if self.mqtt_config.tls_insecure:
                    tls_context.check_hostname = False
                    tls_context.verify_mode = ssl.CERT_NONE
                    logger.warning("TLS certificate verification disabled (insecure!)")

                logger.debug("TLS/SSL enabled for MQTT connection")

            self.client = aiomqtt.Client(
                hostname=self.mqtt_config.host,
                port=self.mqtt_config.port,
                username=self.mqtt_config.username,
                password=self.mqtt_config.password,
                tls_context=tls_context,
            )

            await self.client.__aenter__()
            self._connected = True
            logger.info("MQTT connection established successfully")

        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            self._connected = False
            raise ConnectionError(f"MQTT connection failed: {e}") from e

    async def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        logger.info("Disconnecting from MQTT broker")

        if self.client:
            try:
                await self.client.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error during MQTT disconnect: {e}")

        self.client = None
        self._connected = False
        logger.info("MQTT disconnected")

    async def reconnect_with_backoff(self) -> None:
        """
        Reconnect with exponential backoff.

        Delays start at mqtt_reconnect_delay and double each attempt
        up to mqtt_max_reconnect_delay.
        """
        current_delay = self._reconnect_delay

        while True:
            logger.info(f"Reconnecting to MQTT in {current_delay:.1f}s...")
            await asyncio.sleep(current_delay)

            try:
                await self.connect()
                logger.info("MQTT reconnection successful")
                return
            except Exception as e:
                logger.error(f"MQTT reconnection failed: {e}")
                # Exponential backoff
                current_delay = min(
                    current_delay * 2,
                    self._max_reconnect_delay,
                )

    async def publish_state(
        self,
        topic: str,
        payload: str | dict[str, Any],
        retain: bool | None = None,
    ) -> None:
        """
        Publish a state update.

        Args:
            topic: MQTT topic
            payload: Payload as string or dict (will be JSON-encoded)
            retain: Override default retain setting

        Raises:
            ConnectionError: If not connected
        """
        if not self.client or not self._connected:
            raise ConnectionError("Not connected to MQTT broker")

        # Convert dict to JSON
        if isinstance(payload, dict):
            payload_str = json.dumps(payload)
        else:
            payload_str = payload

        # Use configured retain setting if not overridden
        if retain is None:
            retain = self.advanced_config.mqtt_retain_state

        try:
            await self.client.publish(
                topic,
                payload=payload_str,
                qos=self.advanced_config.mqtt_qos_state,
                retain=retain,
            )
            logger.debug(f"Published state to {topic}: {payload_str[:100]}")

        except Exception as e:
            logger.error(f"Failed to publish state to {topic}: {e}")
            self._connected = False
            raise ConnectionError(f"MQTT publish failed: {e}") from e

    async def publish_availability(
        self,
        device: KermiDevice,
        available: bool,
    ) -> None:
        """
        Publish device availability status.

        Args:
            device: Device to update availability for
            available: True if available, False if unavailable
        """
        topic = device.get_availability_topic()
        payload = "online" if available else "offline"

        await self.publish_state(topic, payload, retain=True)
        logger.info(f"Published availability for {device.device_id}: {payload}")

    async def subscribe(
        self,
        topic: str,
        callback: Callable[[str, str], None],
    ) -> None:
        """
        Subscribe to a topic and call callback on messages.

        Args:
            topic: MQTT topic (can use wildcards)
            callback: Async function called with (topic, payload)

        Note: This is a simplified interface. For MVP (read-only),
        command subscriptions are not yet implemented.
        """
        if not self.client or not self._connected:
            raise ConnectionError("Not connected to MQTT broker")

        logger.info(f"Subscribing to topic: {topic}")

        try:
            await self.client.subscribe(topic, qos=self.advanced_config.mqtt_qos_command)

            # Start message listener task
            async for message in self.client.messages:
                topic_str = str(message.topic)
                payload_str = message.payload.decode()
                logger.debug(f"Received message on {topic_str}: {payload_str}")

                # Call callback (note: callback should be async)
                await callback(topic_str, payload_str)

        except Exception as e:
            logger.error(f"Error in subscription to {topic}: {e}")
            self._connected = False
            raise

    async def subscribe_commands(
        self,
        base_topic: str,
        callback: Callable[[str, str], None],
    ) -> None:
        """
        Subscribe to command topics and start message listener.

        Subscribes to: {base_topic}/#
        Filters in handler for topics ending with: /controls/*/set

        This flexible pattern works for both:
        - {base_topic}/{device_type}/controls/{control_name}/set (no device_id)
        - {base_topic}/{device_id}/{device_type}/controls/{control_name}/set (with device_id)

        Args:
            base_topic: Base MQTT topic (e.g., "kermi/xcenter")
            callback: Async function called with (topic, payload) for commands

        Raises:
            ConnectionError: If not connected

        Note: This method starts a background task that listens for messages.
        The task will run until the client is disconnected.
        """
        if not self.client or not self._connected:
            raise ConnectionError("Not connected to MQTT broker")

        command_pattern = f"{base_topic}/#"
        logger.info(f"Subscribing to command topics: {command_pattern}")

        try:
            await self.client.subscribe(command_pattern, qos=self.advanced_config.mqtt_qos_command)
            self._command_callback = callback

            # Start message listener task
            self._message_listener_task = asyncio.create_task(self._message_listener())
            logger.info("Command subscription active - message listener started")

        except Exception as e:
            logger.error(f"Failed to subscribe to commands: {e}")
            self._connected = False
            raise

    async def _message_listener(self) -> None:
        """
        Internal message listener task.

        Runs in background and dispatches incoming MQTT messages to callbacks.
        Automatically stops when client is disconnected.
        """
        if not self.client:
            logger.error("Cannot start message listener: no client")
            return

        logger.info("Message listener started")

        try:
            async for message in self.client.messages:
                topic_str = str(message.topic)
                payload_str = message.payload.decode()

                logger.info(f"📩 MQTT message received: {topic_str} = {payload_str}")

                # Handle command messages (topics ending with /set)
                if topic_str.endswith("/set") and self._command_callback:
                    logger.info(f"✓ Command message detected: {topic_str} = {payload_str}")
                    logger.info(f"  Calling command handler...")
                    try:
                        await self._command_callback(topic_str, payload_str)
                    except Exception as e:
                        logger.error(
                            f"Error in command callback for {topic_str}: {e}",
                            exc_info=True
                        )
                        # Continue processing other messages
                else:
                    if not topic_str.endswith("/set"):
                        logger.debug(f"  Ignoring (not a command - doesn't end with /set): {topic_str}")
                    elif not self._command_callback:
                        logger.warning(f"  Command callback not set! Topic: {topic_str}")

        except asyncio.CancelledError:
            logger.info("Message listener cancelled")
        except Exception as e:
            logger.error(f"Message listener error: {e}", exc_info=True)
            self._connected = False
