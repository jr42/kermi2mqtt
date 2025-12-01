"""
Main bridge logic - orchestrates Modbus polling and MQTT publishing.

Handles:
- Device discovery and wrapping
- Polling loop with configurable interval
- Home Assistant discovery on startup
- Availability tracking
- Connection failure recovery
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from kermi2mqtt.config import Config
from kermi2mqtt.mappings import get_heat_pump_attributes, get_storage_system_attributes
from kermi2mqtt.modbus_client import ModbusClient
from kermi2mqtt.models.device import KermiDevice
from kermi2mqtt.mqtt_client import MQTTClient

logger = logging.getLogger(__name__)


class ModbusMQTTBridge:
    """
    Main bridge between Modbus and MQTT.

    Responsibilities:
    - Discover devices on startup
    - Poll devices at configured interval
    - Publish state updates to MQTT
    - Maintain availability status
    - Publish Home Assistant discovery
    """

    def __init__(
        self,
        config: Config,
        modbus_client: ModbusClient,
        mqtt_client: MQTTClient,
    ):
        """
        Initialize bridge.

        Args:
            config: Application configuration
            modbus_client: Connected Modbus client
            mqtt_client: Connected MQTT client
        """
        self.config = config
        self.modbus = modbus_client
        self.mqtt = mqtt_client
        self.devices: list[KermiDevice] = []
        self._running = False

    async def discover_devices(self) -> None:
        """
        Discover available devices and create KermiDevice wrappers.

        Creates wrappers for:
        - HeatPump (Unit 40)
        - StorageSystem heating (Unit 50, auto-detected)
        - StorageSystem DHW (Unit 51, auto-detected)
        """
        logger.info("Discovering Modbus devices...")

        # Determine device_id (from config or derive from host)
        device_id = self.config.integration.device_id
        if not device_id:
            # Derive from Modbus host (sanitize for MQTT)
            device_id = self.config.modbus.host.replace(".", "_").replace(":", "_")
            logger.info(f"Auto-detected device_id: {device_id}")

        base_topic = self.config.integration.base_topic

        # Create HeatPump device wrapper
        if self.modbus.heat_pump:
            heat_pump_device = KermiDevice(
                device_id=f"{device_id}_heat_pump",
                device_type="heat_pump",
                unit_id=40,
                xcenter_instance=self.modbus.heat_pump,
                attributes=get_heat_pump_attributes(),
                mqtt_base_topic=f"{base_topic}/{device_id}/heat_pump",
                available=True,
            )
            self.devices.append(heat_pump_device)
            logger.info(
                f"Discovered HeatPump (Unit 40) with {len(heat_pump_device.attributes)} attributes"
            )

        # Create StorageSystem heating device wrapper
        if self.modbus.storage_heating:
            storage_heating_device = KermiDevice(
                device_id=f"{device_id}_storage_heating",
                device_type="storage_heating",
                unit_id=50,
                xcenter_instance=self.modbus.storage_heating,
                attributes=get_storage_system_attributes(),
                mqtt_base_topic=f"{base_topic}/{device_id}/storage_heating",
                available=True,
            )
            self.devices.append(storage_heating_device)
            logger.info(
                f"Discovered StorageSystem heating (Unit 50) with {len(storage_heating_device.attributes)} attributes"
            )

        # Create StorageSystem DHW device wrapper
        if self.modbus.storage_dhw:
            storage_dhw_device = KermiDevice(
                device_id=f"{device_id}_storage_dhw",
                device_type="storage_dhw",
                unit_id=51,
                xcenter_instance=self.modbus.storage_dhw,
                attributes=get_storage_system_attributes(),
                mqtt_base_topic=f"{base_topic}/{device_id}/storage_dhw",
                available=True,
            )
            self.devices.append(storage_dhw_device)
            logger.info(
                f"Discovered StorageSystem DHW (Unit 51) with {len(storage_dhw_device.attributes)} attributes"
            )

        logger.info(f"Discovery complete - found {len(self.devices)} device(s)")

    async def publish_discovery(self) -> None:
        """
        Publish Home Assistant discovery messages for all devices.

        Called once on startup to register entities with Home Assistant.
        """
        logger.info("Publishing Home Assistant discovery messages...")
        await self.mqtt.publish_all_discovery(self.devices)
        logger.info("Home Assistant discovery complete")

    async def publish_availability(self, available: bool) -> None:
        """
        Publish availability status for all devices.

        Args:
            available: True if devices are available, False otherwise
        """
        for device in self.devices:
            await self.mqtt.publish_availability(device, available)

    async def poll_and_publish(self) -> None:
        """
        Poll all devices and publish state updates to MQTT.

        Uses get_all_readable_values() for efficient bulk reads.
        """
        logger.debug("Polling devices...")

        try:
            # Read all devices using efficient bulk method
            all_data = await self.modbus.read_all_devices()

            # Process each device
            for device in self.devices:
                # Get data for this device
                if device.device_type == "heat_pump":
                    device_data = all_data.get("heat_pump", {})
                elif device.device_type == "storage_heating":
                    device_data = all_data.get("storage_heating", {})
                elif device.device_type == "storage_dhw":
                    device_data = all_data.get("storage_dhw", {})
                else:
                    logger.warning(f"Unknown device type: {device.device_type}")
                    continue

                # Publish each attribute
                await self._publish_device_state(device, device_data)

                # Update last poll time
                device.last_poll = datetime.now()

            # Mark devices as available
            if not all(d.available for d in self.devices):
                for device in self.devices:
                    device.available = True
                await self.publish_availability(True)

            logger.debug("Poll complete")

        except Exception as e:
            logger.error(f"Poll failed: {e}")

            # Mark devices as unavailable
            for device in self.devices:
                device.available = False
            await self.publish_availability(False)

            # Re-raise to trigger reconnection
            raise

    async def _publish_device_state(
        self,
        device: KermiDevice,
        device_data: dict[str, Any],
    ) -> None:
        """
        Publish state for a single device.

        Args:
            device: Device to publish state for
            device_data: Data dictionary from get_all_readable_values()
        """
        for attribute in device.attributes:
            # method_name is now the actual data key from get_all_readable_values()
            data_key = attribute.method_name

            # Get value from data
            value = device_data.get(data_key)

            if value is not None:
                # Publish to MQTT
                topic = device.get_mqtt_topic(attribute)
                await self.mqtt.publish_state(topic, str(value))
            else:
                # Only log debug for missing values (some attributes may not always be present)
                logger.debug(
                    f"No data for {device.device_id}.{attribute.method_name}"
                )

    async def run_polling_loop(self) -> None:
        """
        Main polling loop - continuously poll and publish at configured interval.

        Runs until stopped via stop().
        """
        self._running = True
        interval = self.config.integration.poll_interval

        logger.info(f"Starting polling loop (interval: {interval}s)")

        while self._running:
            try:
                await self.poll_and_publish()

            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                # Continue running - reconnection will be handled by clients

            # Wait for next poll (or until stopped)
            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                logger.info("Polling loop cancelled")
                break

        logger.info("Polling loop stopped")

    def stop(self) -> None:
        """Stop the polling loop."""
        logger.info("Stopping bridge...")
        self._running = False

    async def run(self) -> None:
        """
        Run the complete bridge lifecycle.

        Steps:
        1. Discover devices
        2. Publish HA discovery
        3. Publish initial availability
        4. Start polling loop
        """
        logger.info("Starting Modbus-MQTT bridge")

        # Discover devices
        await self.discover_devices()

        # Publish Home Assistant discovery
        await self.publish_discovery()

        # Publish initial availability
        await self.publish_availability(True)

        # Run polling loop
        await self.run_polling_loop()

        # Cleanup on exit
        logger.info("Publishing offline availability...")
        await self.publish_availability(False)

        logger.info("Bridge shutdown complete")
