"""
MQTT client wrapper for aiomqtt with Home Assistant discovery support.

Provides:
- Async MQTT publish/subscribe
- QoS handling for state and command topics
- Home Assistant MQTT discovery protocol
- Automatic reconnection with exponential backoff
- Clean shutdown handling
"""

import asyncio
import json
import logging
import ssl
from typing import Any, Callable

import aiomqtt

from kermi2mqtt.config import AdvancedConfig, MQTTConfig
from kermi2mqtt.models.datapoint import DeviceAttribute
from kermi2mqtt.models.device import KermiDevice

logger = logging.getLogger(__name__)


class MQTTClient:
    """
    Async MQTT client wrapper with HA discovery support.

    Handles:
    - Publishing device state updates
    - Subscribing to command topics
    - Publishing HA discovery messages
    - Availability tracking
    """

    def __init__(
        self,
        mqtt_config: MQTTConfig,
        advanced_config: AdvancedConfig,
        ha_discovery_prefix: str = "homeassistant",
    ):
        """
        Initialize MQTT client.

        Args:
            mqtt_config: MQTT broker configuration
            advanced_config: Advanced settings (QoS, reconnect delays, retain)
            ha_discovery_prefix: Home Assistant discovery prefix
        """
        self.mqtt_config = mqtt_config
        self.advanced_config = advanced_config
        self.ha_discovery_prefix = ha_discovery_prefix

        self.client: aiomqtt.Client | None = None
        self._connected = False
        self._reconnect_delay = advanced_config.mqtt_reconnect_delay
        self._max_reconnect_delay = advanced_config.mqtt_max_reconnect_delay

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

    async def publish_discovery(
        self,
        device: KermiDevice,
        attribute: DeviceAttribute,
    ) -> None:
        """
        Publish Home Assistant MQTT discovery message for an attribute.

        Args:
            device: Device this attribute belongs to
            attribute: Attribute to publish discovery for

        Discovery topic format:
        <discovery_prefix>/<component>/<device_id>/<object_id>/config

        Example:
        homeassistant/sensor/heat_pump/outdoor_temp/config
        """
        # Build discovery topic
        # Extract object_id from mqtt_topic_suffix (e.g., "sensors/outdoor_temp" -> "outdoor_temp")
        object_id = attribute.mqtt_topic_suffix.split("/")[-1]

        discovery_topic = (
            f"{self.ha_discovery_prefix}/"
            f"{attribute.ha_component}/"
            f"{device.device_id}/"
            f"{object_id}/config"
        )

        # Build discovery payload
        state_topic = device.get_mqtt_topic(attribute)
        availability_topic = device.get_availability_topic()

        payload = {
            "name": attribute.friendly_name,
            "state_topic": state_topic,
            "availability_topic": availability_topic,
            "unique_id": f"{device.device_id}_{object_id}",
            "device": {
                "identifiers": [device.device_id],
                "name": f"Kermi {device.device_type.replace('_', ' ').title()}",
                "manufacturer": "Kermi",
                "model": device.device_type,
            },
        }

        # Add HA-specific config (unit_of_measurement, device_class, state_class, etc.)
        payload.update(attribute.ha_config)

        # Publish with retain=True (discovery messages should be retained)
        retain = self.advanced_config.mqtt_retain_discovery

        try:
            await self.client.publish(
                discovery_topic,
                payload=json.dumps(payload),
                qos=self.advanced_config.mqtt_qos_state,
                retain=retain,
            )
            logger.debug(f"Published discovery for {device.device_id}/{object_id}")

        except Exception as e:
            logger.error(f"Failed to publish discovery for {object_id}: {e}")
            raise

    async def publish_all_discovery(self, devices: list[KermiDevice]) -> None:
        """
        Publish discovery messages for all devices and their attributes.

        Args:
            devices: List of devices to publish discovery for
        """
        logger.info(f"Publishing Home Assistant discovery for {len(devices)} device(s)")

        for device in devices:
            logger.info(
                f"Publishing {len(device.attributes)} discovery messages for {device.device_id}"
            )

            for attribute in device.attributes:
                await self.publish_discovery(device, attribute)

        logger.info("All discovery messages published")

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
