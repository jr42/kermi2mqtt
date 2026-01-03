"""
Main bridge logic - orchestrates Modbus polling and MQTT publishing.

Handles:
- Device discovery and wrapping
- Polling loop with configurable interval
- Home Assistant discovery on startup (optional)
- Availability tracking
- Connection failure recovery

Architecture:
- State publishing: Always publishes to agnostic MQTT topics (works with all tools)
- HA Discovery: Optional, configurable via ha_discovery_enabled in config
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from kermi_xcenter.types import EnergyMode, SeasonSelection

from kermi2mqtt import ha_discovery
from kermi2mqtt.config import Config
from kermi2mqtt.mappings import get_heat_pump_attributes, get_storage_system_attributes
from kermi2mqtt.modbus_client import ModbusClient
from kermi2mqtt.models.datapoint import DeviceAttribute
from kermi2mqtt.models.device import KermiDevice
from kermi2mqtt.mqtt_client import MQTTClient
from kermi2mqtt.safety import RateLimiter, SafetyValidator

logger = logging.getLogger(__name__)

# Attribute filtering constants for StorageSystem devices
# These define which attributes are exclusive to heating or DHW units
HEATING_ONLY_ATTRIBUTES = {
    "heating_setpoint",
    "heating_actual",
    "heating_circuit_setpoint",
    "heating_circuit_actual",
    "heating_circuit_status",
    "heating_circuit_operating_mode",
    "cooling_actual",
    "cooling_mode_active",
    "t4_temperature",  # Outdoor sensor (T4) - physically on heating unit
    "outdoor_temperature_avg",  # Calculated outdoor average - on heating unit
}

DHW_ONLY_ATTRIBUTES = {
    "hot_water_setpoint",
    "hot_water_actual",
    "hot_water_setpoint_constant",
}


def _should_publish_attribute(
    device_type: str,
    attribute: "DeviceAttribute",
    value: Any,
) -> bool:
    """
    Determine if an attribute should be published based on device type and value.

    Filtering Rules:
    0. Never publish None or obviously wrong values (sanity checks)
    1. Always publish non-zero values (real data overrides everything)
    2. Filter heating-only attributes on DHW devices when value is 0.0
    3. Filter DHW-only attributes on heating devices when value is 0.0
    4. Publish everything else (shared sensors: temps, operating hours, etc.)

    This auto-adapts to:
    - Shared sensors (outdoor_temp on Unit 50 but used by both)
    - Combined units (both heating and DHW active with non-zero values)
    - Legitimate zero values (cooling_actual when not cooling - publishes on first use)

    Args:
        device_type: Type of device ("storage_heating", "storage_dhw", "heat_pump")
        attribute: Device attribute to check
        value: Current value of the attribute

    Returns:
        True if attribute should be published, False if it should be filtered
    """
    # RULE 0: Never publish None (no data available)
    if value is None:
        return False

    # RULE 0b: Sanity checks for obviously wrong values
    # Temperature sensors should be in reasonable range (-50 to +100°C)
    if attribute.ha_component == "sensor" and "temperature" in attribute.method_name.lower():
        try:
            temp_value = float(value)
            if temp_value < -50 or temp_value > 100:
                logger.warning(
                    f"Filtering {attribute.method_name} with invalid temperature: {temp_value}°C "
                    f"(expected -50 to +100°C range)"
                )
                return False
        except (ValueError, TypeError):
            pass  # Not a numeric temperature, continue with other checks

    # RULE 1.5: Always filter heating-only attributes on DHW devices
    # (regardless of value - outdoor sensors are physically on heating unit)
    if device_type == "storage_dhw" and attribute.method_name in HEATING_ONLY_ATTRIBUTES:
        return False

    # RULE 1.6: Always filter DHW-only attributes on heating devices
    # (regardless of value)
    if device_type == "storage_heating" and attribute.method_name in DHW_ONLY_ATTRIBUTES:
        return False

    # RULE 1: Always publish non-zero values (real data)
    if value not in (0.0, 0, False):
        return True

    # RULE 4: Publish everything else (shared sensors, temps, etc.)
    return True


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

        # Command handling (User Story 2)
        self.rate_limiter = RateLimiter(min_interval_seconds=60.0)
        self.safety_validator = SafetyValidator("bridge")

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
                f"Discovered StorageSystem heating (Unit 50) with "
                f"{len(storage_heating_device.attributes)} attributes"
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
                f"Discovered StorageSystem DHW (Unit 51) with "
                f"{len(storage_dhw_device.attributes)} attributes"
            )

        logger.info(f"Discovery complete - found {len(self.devices)} device(s)")

    async def publish_discovery(self) -> None:
        """
        Publish Home Assistant discovery messages for all devices (if enabled).

        Called once on startup to register entities with Home Assistant.
        Controlled by ha_discovery_enabled config option.

        Note:
            State publishing to MQTT topics happens regardless of this setting.
            This only controls whether HA auto-discovery messages are published.
            Non-HA tools (n8n, ioBroker, etc.) use the same state topics directly.
        """
        if not self.config.integration.ha_discovery_enabled:
            logger.info("Home Assistant discovery disabled - skipping")
            logger.info(
                "State publishing to MQTT topics will continue (works with any MQTT tool)"
            )
            return

        logger.info("Publishing Home Assistant discovery messages...")
        logger.debug(f"HA discovery prefix: {self.config.integration.ha_discovery_prefix}")
        logger.debug(f"Publishing for {len(self.devices)} device(s)")

        # Publish all discovery messages using our existing MQTT client
        try:
            await ha_discovery.publish_all_discovery(
                mqtt_client=self.mqtt,
                devices=self.devices,
                ha_discovery_prefix=self.config.integration.ha_discovery_prefix,
            )
            logger.info("✓ Home Assistant discovery complete")
        except Exception as e:
            logger.error(f"Failed to publish HA discovery messages: {e}", exc_info=True)
            logger.warning("Continuing without HA discovery - state publishing will still work")

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
                device.last_poll = datetime.now(tz=None)

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

            # Publish unavailability if MQTT is still connected
            try:
                await self.publish_availability(False)
            except Exception as mqtt_err:
                logger.debug(f"Could not publish unavailability (MQTT disconnected): {mqtt_err}")

            # Re-raise to let polling loop handle reconnection
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
                # Check if this attribute should be published for this device type
                if not _should_publish_attribute(device.device_type, attribute, value):
                    logger.debug(
                        f"Filtering {device.device_id}.{attribute.method_name} "
                        f"(value={value}, not applicable to {device.device_type})"
                    )
                    continue  # Skip publishing this attribute

                # Transform value based on component type and enum
                if attribute.ha_component == "binary_sensor":
                    # Home Assistant binary_sensor expects "ON" or "OFF"
                    payload = "ON" if value else "OFF"
                elif attribute.value_enum:
                    # Translate numeric value using enum
                    try:
                        enum_value = attribute.value_enum(value)
                        enum_name = enum_value.name  # e.g., "STANDBY", "HEATING"

                        # Transform specific enums for HA climate/water_heater compatibility
                        # These need lowercase values that match HA's expected preset/mode names
                        if attribute.value_enum.__name__ == "EnergyMode":
                            # Map EnergyMode to lowercase HA-compatible names
                            energy_mode_map = {
                                "ECO": "eco",
                                "NORMAL": "comfort",
                                "COMFORT": "boost",
                                "OFF": "away",
                                "CUSTOM": "heat_pump"  # Unique value for heat pump mode
                            }
                            payload = energy_mode_map.get(enum_name, enum_name.lower())
                        elif attribute.value_enum.__name__ == "SeasonSelection":
                            # Map SeasonSelection to lowercase HA-compatible mode names
                            season_map = {
                                "AUTO": "auto",
                                "HEATING": "heat",
                                "COOLING": "cool",
                                "OFF": "off"
                            }
                            payload = season_map.get(enum_name, enum_name.lower())
                        else:
                            # Keep other enums as uppercase
                            payload = enum_name
                    except (ValueError, KeyError):
                        # If value not in enum, use raw value
                        logger.warning(
                            f"Unknown enum value {value} for {attribute.method_name}, "
                            f"expected {attribute.value_enum.__name__}"
                        )
                        payload = str(value)
                else:
                    # For regular sensors, use string representation
                    payload = str(value)

                # Publish to MQTT
                topic = device.get_mqtt_topic(attribute)
                await self.mqtt.publish_state(topic, payload)
            else:
                # Only log debug for missing values (some attributes may not always be present)
                logger.debug(
                    f"No data for {device.device_id}.{attribute.method_name}"
                )

    async def handle_command(self, topic: str, payload: str) -> None:
        """
        Handle MQTT command messages.

        Topic format: {base_topic}/{device_id}/controls/{control_name}/set
        Example: kermi/xcenter/storage_dhw/controls/hot_water_setpoint/set

        Args:
            topic: MQTT topic that received the command
            payload: Command payload (string, number, or enum value)

        Raises:
            Exception: On command execution failure (published to error topic)
        """
        try:
            # Parse topic to extract device_id and control_name
            # Expected format: {base_topic}/{device_id}/controls/{control_name}/set
            topic_parts = topic.split("/")
            if len(topic_parts) < 5 or topic_parts[-3] != "controls" or topic_parts[-1] != "set":
                logger.error(f"Invalid command topic format: {topic}")
                return

            control_name = topic_parts[-2]
            # Find device_id - everything between base_topic and "controls"
            controls_index = topic_parts.index("controls")
            device_id = "/".join(topic_parts[:controls_index])

            logger.info(f"Received command: {control_name} = {payload} (device: {device_id})")

            # Find matching device
            device = None
            for d in self.devices:
                if topic.startswith(d.mqtt_base_topic):
                    device = d
                    break

            if not device:
                error_msg = f"Device not found for topic: {topic}"
                logger.error(error_msg)
                await self._publish_command_error(topic, error_msg)
                return

            # Find matching writable attribute
            attribute = None
            for attr in device.attributes:
                if attr.mqtt_topic_suffix.endswith(control_name) and attr.writable:
                    attribute = attr
                    break

            if not attribute:
                error_msg = f"Writable attribute not found: {control_name}"
                logger.error(error_msg)
                await self._publish_command_error(topic, error_msg)
                return

            # Rate limiting check
            can_write, rate_msg = self.rate_limiter.can_write(f"{device.device_id}_{control_name}")
            if not can_write:
                logger.warning(f"Rate limit: {rate_msg}")
                await self._publish_command_error(topic, rate_msg)
                return

            # Parse payload based on component type
            parsed_value = None
            if attribute.ha_component == "number":
                try:
                    parsed_value = float(payload)
                except ValueError:
                    error_msg = f"Invalid number value: {payload}"
                    logger.error(error_msg)
                    await self._publish_command_error(topic, error_msg)
                    return

                # Safety validation for number controls
                if attribute.method_name == "set_hot_water_setpoint_constant":
                    is_valid, error = SafetyValidator.validate_dhw_temperature(parsed_value)
                    if not is_valid:
                        logger.error(f"Safety validation failed: {error}")
                        await self._publish_command_error(topic, error)
                        return
                elif attribute.method_name == "set_heating_curve_offset":
                    is_valid, error = SafetyValidator.validate_heating_curve_offset(parsed_value)
                    if not is_valid:
                        logger.error(f"Safety validation failed: {error}")
                        await self._publish_command_error(topic, error)
                        return
                elif attribute.method_name == "set_season_threshold_heating_limit":
                    is_valid, error = SafetyValidator.validate_season_threshold(parsed_value)
                    if not is_valid:
                        logger.error(f"Safety validation failed: {error}")
                        await self._publish_command_error(topic, error)
                        return

            elif attribute.ha_component == "select":
                # Transform HA values back to enum names
                # (reverse of the transformation in _publish_device_state)
                payload_clean = payload.strip().lower()

                if attribute.method_name == "set_season_selection_manual":
                    # Map HA climate mode values back to SeasonSelection enum names
                    season_reverse_map = {
                        "auto": "AUTO",
                        "heat": "HEATING",
                        "cool": "COOLING",
                        "off": "OFF"
                    }
                    enum_name = season_reverse_map.get(payload_clean)
                    if not enum_name:
                        error_msg = f"Invalid season selection: {payload}"
                        logger.error(error_msg)
                        await self._publish_command_error(topic, error_msg)
                        return

                    is_valid, error = SafetyValidator.validate_season_selection(enum_name)
                    if not is_valid:
                        logger.error(f"Validation failed: {error}")
                        await self._publish_command_error(topic, error)
                        return
                    # Convert to enum
                    parsed_value = SeasonSelection[enum_name]

                elif attribute.method_name == "set_heating_circuit_energy_mode":
                    # Map HA preset/mode values back to EnergyMode enum names
                    # Support both climate preset modes AND water_heater modes
                    energy_reverse_map = {
                        # Climate presets (from climate entity)
                        "eco": "ECO",
                        "comfort": "NORMAL",
                        "boost": "COMFORT",
                        "away": "OFF",
                        # Water heater modes (from water_heater entity)
                        "performance": "NORMAL",   # Maps to NORMAL
                        "high_demand": "COMFORT",  # Maps to COMFORT
                        "heat_pump": "CUSTOM",     # Maps to CUSTOM
                        "off": "OFF"               # Maps to OFF
                    }
                    enum_name = energy_reverse_map.get(payload_clean)
                    if not enum_name:
                        error_msg = f"Invalid energy mode: {payload}"
                        logger.error(error_msg)
                        await self._publish_command_error(topic, error_msg)
                        return

                    is_valid, error = SafetyValidator.validate_energy_mode(enum_name)
                    if not is_valid:
                        logger.error(f"Validation failed: {error}")
                        await self._publish_command_error(topic, error)
                        return
                    # Convert to enum
                    parsed_value = EnergyMode[enum_name]

                else:
                    error_msg = f"Unknown select control: {attribute.method_name}"
                    logger.error(error_msg)
                    await self._publish_command_error(topic, error_msg)
                    return

            elif attribute.ha_component == "button":
                # Button commands expect "1" or "PRESS"
                if payload.upper() not in ("1", "PRESS"):
                    error_msg = f"Invalid button payload: {payload}"
                    logger.error(error_msg)
                    await self._publish_command_error(topic, error_msg)
                    return
                parsed_value = 1  # Button press value

            else:
                error_msg = f"Unsupported component type for write: {attribute.ha_component}"
                logger.error(error_msg)
                await self._publish_command_error(topic, error_msg)
                return

            # Execute write operation via py-kermi-xcenter
            logger.info(
                f"Executing write: {device.device_id}.{attribute.method_name}({parsed_value})"
            )

            try:
                # Get the write method from the xcenter instance
                write_method = getattr(device.xcenter_instance, attribute.method_name)
                await write_method(parsed_value)

                logger.info(f"✓ Write successful: {attribute.method_name} = {parsed_value}")

                # Read back confirmation (for non-button controls)
                if attribute.ha_component != "button":
                    # Small delay to let device update
                    await asyncio.sleep(0.5)

                    # Trigger immediate poll to publish updated state
                    await self.poll_and_publish()

            except Exception as e:
                error_msg = f"Write operation failed: {e}"
                logger.error(error_msg, exc_info=True)
                await self._publish_command_error(topic, error_msg)
                raise

        except Exception as e:
            logger.error(f"Command handler error: {e}", exc_info=True)
            await self._publish_command_error(topic, str(e))

    async def _publish_command_error(self, command_topic: str, error: str) -> None:
        """
        Publish command error to error topic.

        Error topic format: {command_topic}/error
        Example: kermi/xcenter/storage_dhw/controls/hot_water_setpoint/set/error

        Args:
            command_topic: Original command topic
            error: Error message to publish
        """
        error_topic = f"{command_topic}/error"
        try:
            await self.mqtt.publish_state(error_topic, error, retain=False)
            logger.debug(f"Published error to {error_topic}")
        except Exception as e:
            logger.error(f"Failed to publish command error: {e}")

    async def run_polling_loop(self) -> None:
        """
        Main polling loop - continuously poll and publish at configured interval.

        Runs until stopped via stop().
        Handles automatic reconnection for both MQTT and Modbus clients.
        """
        self._running = True
        interval = self.config.integration.poll_interval

        logger.info(f"Starting polling loop (interval: {interval}s)")

        while self._running:
            try:
                # Check if clients are connected before polling
                if not self.mqtt.is_connected:
                    logger.warning("MQTT disconnected, attempting reconnection...")
                    await self.mqtt.reconnect_with_backoff()
                    logger.info("MQTT reconnected successfully")

                    # After MQTT reconnects, republish availability and discovery
                    await self.publish_availability(True)

                if not self.modbus.is_connected:
                    logger.warning("Modbus disconnected, attempting reconnection...")
                    await self.modbus.reconnect_with_backoff()
                    logger.info("Modbus reconnected successfully")

                # Poll and publish
                await self.poll_and_publish()

            except ConnectionError as e:
                # Connection errors are expected when clients disconnect
                logger.error(f"Connection error in polling loop: {e}")
                logger.info("Will attempt reconnection on next iteration")
                # Don't sleep full interval on connection errors - retry sooner
                await asyncio.sleep(min(5.0, interval))
                continue

            except Exception as e:
                logger.error(f"Unexpected error in polling loop: {e}", exc_info=True)
                # For unexpected errors, continue with normal interval

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

        # Subscribe to command topics (User Story 2)
        base_topic = self.config.integration.base_topic
        subscription_pattern = f"{base_topic}/#"
        logger.info(f"Setting up MQTT command subscription to: {subscription_pattern}")
        logger.info("Command handler will process topics ending with: /controls/*/set")
        try:
            await self.mqtt.subscribe_commands(base_topic, self.handle_command)
            logger.info(f"✓ Command subscription active - monitoring {subscription_pattern}")
            logger.info("  Expected command topics:")
            for device in self.devices:
                logger.info(f"    - {device.mqtt_base_topic}/controls/*/set")
        except Exception as e:
            logger.error(f"Failed to subscribe to commands: {e}", exc_info=True)
            logger.warning("Continuing in read-only mode")

        # Run polling loop
        await self.run_polling_loop()

        # Cleanup on exit
        logger.info("Publishing offline availability...")
        await self.publish_availability(False)

        logger.info("Bridge shutdown complete")
