"""
Main bridge logic - orchestrates device polling and MQTT publishing.

Handles:
- Device discovery and wrapping
- Polling loop with configurable interval
- Home Assistant discovery on startup (optional)
- Availability tracking
- Connection failure recovery

Architecture:
- State publishing: Always publishes to agnostic MQTT topics (works with all tools)
- HA Discovery: Optional, configurable via ha_discovery_enabled in config
- Supports both HTTP (recommended) and Modbus transports
"""

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol

from kermi_xcenter.types import EnergyMode, SeasonSelection

from kermi2mqtt import ha_discovery
from kermi2mqtt.config import Config
from kermi2mqtt.mappings import (
    get_heat_pump_attributes,
    get_ifm_attributes,
    get_storage_system_attributes,
)
from kermi2mqtt.models.datapoint import DeviceAttribute
from kermi2mqtt.models.device import KermiDevice
from kermi2mqtt.mqtt_client import MQTTClient
from kermi2mqtt.safety import RateLimiter, SafetyValidator

if TYPE_CHECKING:
    from kermi2mqtt.http_client import HttpClient
    from kermi2mqtt.modbus_client import ModbusClient


class DeviceClient(Protocol):
    """Protocol for device clients (HTTP or Modbus)."""

    @property
    def is_connected(self) -> bool: ...
    @property
    def heat_pump(self) -> Any: ...
    @property
    def storage_heating(self) -> Any: ...
    @property
    def storage_dhw(self) -> Any: ...

    async def reconnect_with_backoff(self) -> None: ...
    async def read_all_devices(self) -> dict[str, dict[str, Any]]: ...

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
    "summer_mode_active",  # Heating circuit concept - not relevant for DHW
    "t4_temperature",  # Outdoor sensor (T4) - physically on heating unit
    "outdoor_temperature_avg",  # Calculated outdoor average - on heating unit
    "operating_hours_circuit_pump",  # Circuit pump is on heating unit
}

DHW_ONLY_ATTRIBUTES = {
    "hot_water_setpoint",
    "hot_water_actual",
    "hot_water_setpoint_constant",
    "set_hot_water_setpoint_constant",  # Control method
    "set_one_time_heating",  # DHW boost control
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


class Bridge:
    """
    Main bridge between device (HTTP/Modbus) and MQTT.

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
        device_client: "HttpClient | ModbusClient",
        mqtt_client: MQTTClient,
    ):
        """
        Initialize bridge.

        Args:
            config: Application configuration
            device_client: Connected device client (HTTP or Modbus)
            mqtt_client: Connected MQTT client
        """
        self.config = config
        self.device_client = device_client
        self.mqtt = mqtt_client
        self.devices: list[KermiDevice] = []
        self.scenes: list = []  # SceneOverview objects from HTTP API
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
        conn_type = self.config.integration.connection_type
        logger.info(f"Discovering devices via {conn_type.upper()}...")

        # Determine device_id (from config or derive from host)
        device_id = self.config.integration.device_id
        if not device_id:
            # Derive from host (sanitize for MQTT)
            if conn_type == "http" and self.config.http:
                host = self.config.http.host
            elif self.config.modbus:
                host = self.config.modbus.host
            else:
                host = "unknown"
            device_id = host.replace(".", "_").replace(":", "_")
            logger.info(f"Auto-detected device_id: {device_id}")

        base_topic = self.config.integration.base_topic
        is_http = self.config.integration.connection_type == "http"

        # Helper to get device metadata (HTTP only)
        async def get_device_metadata(unit_id: int) -> tuple[str | None, str | None, str | None]:
            """Get serial, model, sw_version for a device (HTTP only)."""
            if is_http and hasattr(self.device_client, "get_device_info"):
                try:
                    info = await self.device_client.get_device_info(unit_id)
                    return info.serial_number, info.model, info.software_version
                except Exception as e:
                    logger.warning(f"Could not get device info for unit {unit_id}: {e}")
            return None, None, None

        # Create IFM device wrapper (HTTP only - Unit 0)
        if is_http and hasattr(self.device_client, "ifm") and self.device_client.ifm:
            serial, model, sw_ver = await get_device_metadata(0)
            ifm_device = KermiDevice(
                device_id=f"{device_id}_ifm",
                device_type="ifm",
                unit_id=0,
                xcenter_instance=self.device_client.ifm,
                attributes=get_ifm_attributes(),
                mqtt_base_topic=f"{base_topic}/{device_id}/ifm",
                available=True,
                serial_number=serial,
                model_name=model,
                software_version=sw_ver,
            )
            self.devices.append(ifm_device)
            logger.info(f"Discovered IFM (Unit 0) - Serial: {serial}")

            # Discover scenes (x-center automation rules)
            try:
                self.scenes = await self.device_client.get_scenes()
                if self.scenes:
                    logger.info(f"Discovered {len(self.scenes)} scene(s)")
                    for scene in self.scenes:
                        status = "enabled" if scene.enabled else "disabled"
                        logger.debug(f"  - {scene.display_name} ({status})")
            except Exception as e:
                logger.warning(f"Could not discover scenes: {e}")

        # Create HeatPump device wrapper
        if self.device_client.heat_pump:
            serial, model, sw_ver = await get_device_metadata(40)
            heat_pump_device = KermiDevice(
                device_id=f"{device_id}_heat_pump",
                device_type="heat_pump",
                unit_id=40,
                xcenter_instance=self.device_client.heat_pump,
                attributes=get_heat_pump_attributes(),
                mqtt_base_topic=f"{base_topic}/{device_id}/heat_pump",
                available=True,
                serial_number=serial,
                model_name=model,
                software_version=sw_ver,
            )
            self.devices.append(heat_pump_device)
            logger.info(
                f"Discovered HeatPump (Unit 40) - Serial: {serial}, "
                f"{len(heat_pump_device.attributes)} attributes"
            )

        # Create StorageSystem heating device wrapper
        if self.device_client.storage_heating:
            serial, model, sw_ver = await get_device_metadata(50)
            storage_heating_device = KermiDevice(
                device_id=f"{device_id}_storage_heating",
                device_type="storage_heating",
                unit_id=50,
                xcenter_instance=self.device_client.storage_heating,
                attributes=get_storage_system_attributes(),
                mqtt_base_topic=f"{base_topic}/{device_id}/storage_heating",
                available=True,
                serial_number=serial,
                model_name=model,
                software_version=sw_ver,
            )
            self.devices.append(storage_heating_device)
            logger.info(
                f"Discovered StorageSystem heating (Unit 50) - Serial: {serial}, "
                f"{len(storage_heating_device.attributes)} attributes"
            )

        # Create StorageSystem DHW device wrapper
        if self.device_client.storage_dhw:
            serial, model, sw_ver = await get_device_metadata(51)
            storage_dhw_device = KermiDevice(
                device_id=f"{device_id}_storage_dhw",
                device_type="storage_dhw",
                unit_id=51,
                xcenter_instance=self.device_client.storage_dhw,
                attributes=get_storage_system_attributes(),
                mqtt_base_topic=f"{base_topic}/{device_id}/storage_dhw",
                available=True,
                serial_number=serial,
                model_name=model,
                software_version=sw_ver,
            )
            self.devices.append(storage_dhw_device)
            logger.info(
                f"Discovered StorageSystem DHW (Unit 51) - Serial: {serial}, "
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
            logger.info("State publishing to MQTT topics will continue (works with any MQTT tool)")
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
                connection_type=self.config.integration.connection_type,
                scenes=self.scenes if self.scenes else None,
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
            all_data = await self.device_client.read_all_devices()

            # Process each device
            for device in self.devices:
                # Get data for this device
                if device.device_type == "ifm":
                    device_data = all_data.get("ifm", {})
                elif device.device_type == "heat_pump":
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

                # For IFM device with HTTP connection, also poll and publish alarms and scenes
                if device.device_type == "ifm" and self.config.integration.connection_type == "http":
                    await self._poll_and_publish_alarms(device)
                    await self._publish_scene_states(device)

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

            # Filter NaN values (causes "unknown" in HA)
            # Can be float NaN or string "NaN" depending on API response
            if (isinstance(value, float) and value != value) or value == "NaN":  # noqa: PLR0124
                logger.debug(f"Filtering {device.device_id}.{attribute.method_name} - NaN value")
                continue

            if value is not None:
                # Check if this attribute should be published for this device type
                if not _should_publish_attribute(device.device_type, attribute, value):
                    logger.debug(
                        f"Filtering {device.device_id}.{attribute.method_name} "
                        f"(value={value}, not applicable to {device.device_type})"
                    )
                    continue  # Skip publishing this attribute

                # Transform value based on component type and enum
                if attribute.ha_component in ("binary_sensor", "switch"):
                    # Home Assistant binary_sensor and switch expect "ON" or "OFF"
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
                                "CUSTOM": "heat_pump",  # Unique value for heat pump mode
                            }
                            payload = energy_mode_map.get(enum_name, enum_name.lower())
                        elif attribute.value_enum.__name__ == "SeasonSelection":
                            # Map SeasonSelection to lowercase HA-compatible mode names
                            season_map = {
                                "AUTO": "auto",
                                "HEATING": "heat",
                                "COOLING": "cool",
                                "OFF": "off",
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
                logger.debug(f"No data for {device.device_id}.{attribute.method_name}")

    async def _poll_and_publish_alarms(self, ifm_device: KermiDevice) -> None:
        """
        Poll alarm data from HTTP API and publish to MQTT.

        Publishes:
        - binary_sensors/alarms_active: ON if any alarm active
        - sensors/alarm_count: Number of active alarms
        - sensors/alarm_history_count: Number of alarms in history

        Args:
            ifm_device: The IFM KermiDevice to publish alarm data under
        """
        try:
            # Get current alarms
            current_alarms = await self.device_client.get_current_alarms()
            alarm_count = len(current_alarms)
            alarms_active = alarm_count > 0

            # Get alarm history
            alarm_history = await self.device_client.get_alarm_history()
            history_count = len(alarm_history)

            # Publish alarms_active binary sensor
            active_topic = f"{ifm_device.mqtt_base_topic}/binary_sensors/alarms_active"
            await self.mqtt.publish_state(active_topic, "ON" if alarms_active else "OFF")

            # Publish alarm_count sensor
            count_topic = f"{ifm_device.mqtt_base_topic}/sensors/alarm_count"
            await self.mqtt.publish_state(count_topic, str(alarm_count))

            # Publish alarm_history_count sensor
            history_topic = f"{ifm_device.mqtt_base_topic}/sensors/alarm_history_count"
            await self.mqtt.publish_state(history_topic, str(history_count))

            logger.debug(
                f"Alarm status: {alarm_count} active, {history_count} in history"
            )

        except Exception as e:
            logger.error(f"Failed to poll alarms: {e}")

    async def _publish_scene_states(self, ifm_device: KermiDevice) -> None:
        """
        Publish scene states to MQTT.

        For each scene publishes:
        - enabled: ON/OFF for the enable/disable switch
        - available: online/offline for scene trigger availability
          (disabled scenes show as greyed out in HA)

        Args:
            ifm_device: The IFM KermiDevice to publish scene states under
        """
        if not self.scenes:
            return

        try:
            # Re-fetch scenes to get current enabled status
            self.scenes = await self.device_client.get_scenes()

            for scene in self.scenes:
                # Sanitize scene_id for topic (remove dashes from UUID)
                safe_scene_id = scene.scene_id.replace("-", "")
                base_topic = f"{ifm_device.mqtt_base_topic}/scenes/{safe_scene_id}"

                # Publish enabled state (for the switch entity)
                await self.mqtt.publish_state(
                    f"{base_topic}/enabled", "ON" if scene.enabled else "OFF"
                )

                # Publish availability (for the scene trigger entity)
                # Disabled scenes appear greyed out in HA
                await self.mqtt.publish_state(
                    f"{base_topic}/available", "online" if scene.enabled else "offline"
                )

            logger.debug(f"Published state for {len(self.scenes)} scene(s)")

        except Exception as e:
            logger.error(f"Failed to publish scene states: {e}")

    async def _handle_scene_command(self, topic: str, payload: str) -> None:
        """
        Handle scene-related MQTT commands.

        Topic formats:
        - Enable/disable: .../scenes/{scene_id}/enabled/set (payload: ON/OFF)
        - Trigger: .../scenes/{scene_id}/trigger/set (payload: ACTIVATE)

        Args:
            topic: MQTT topic
            payload: Command payload
        """
        topic_parts = topic.split("/")

        # Extract scene_id and command type from topic
        # Expected path: .../scenes/<scene_id>/<enabled|trigger>/set
        try:
            scenes_idx = topic_parts.index("scenes")
            scene_id_sanitized = topic_parts[scenes_idx + 1]
            command_type = topic_parts[scenes_idx + 2]  # "enabled" or "trigger"
        except (ValueError, IndexError):
            logger.error(f"Invalid scene command topic: {topic}")
            return

        # Find matching scene (scene_id in topic is sanitized, without dashes)
        matching_scene = None
        for scene in self.scenes:
            if scene.scene_id.replace("-", "") == scene_id_sanitized:
                matching_scene = scene
                break

        if not matching_scene:
            logger.error(f"Scene not found: {scene_id_sanitized}")
            await self._publish_command_error(topic, f"Scene not found: {scene_id_sanitized}")
            return

        scene_id = matching_scene.scene_id
        scene_name = matching_scene.display_name

        try:
            if command_type == "enabled":
                # Enable/disable scene
                if payload.upper() == "ON":
                    logger.info(f"Enabling scene: {scene_name}")
                    await self.device_client.set_scene_enabled(scene_id, True)
                elif payload.upper() == "OFF":
                    logger.info(f"Disabling scene: {scene_name}")
                    await self.device_client.set_scene_enabled(scene_id, False)
                else:
                    error_msg = f"Invalid scene enable payload: {payload} (expected ON/OFF)"
                    logger.error(error_msg)
                    await self._publish_command_error(topic, error_msg)
                    return

                logger.info(f"✓ Scene {scene_name} {'enabled' if payload.upper() == 'ON' else 'disabled'}")

                # Re-publish scene states to update HA
                ifm_device = next((d for d in self.devices if d.device_type == "ifm"), None)
                if ifm_device:
                    await self._publish_scene_states(ifm_device)

            elif command_type == "trigger":
                # Trigger scene execution
                if payload.upper() != "ACTIVATE":
                    error_msg = f"Invalid scene trigger payload: {payload} (expected ACTIVATE)"
                    logger.error(error_msg)
                    await self._publish_command_error(topic, error_msg)
                    return

                # Check if scene is enabled
                if not matching_scene.enabled:
                    error_msg = f"Cannot trigger disabled scene: {scene_name}"
                    logger.warning(error_msg)
                    await self._publish_command_error(topic, error_msg)
                    return

                logger.info(f"Triggering scene: {scene_name}")
                await self.device_client.execute_scene(scene_id)
                logger.info(f"✓ Scene {scene_name} triggered successfully")

            else:
                logger.error(f"Unknown scene command type: {command_type}")

        except Exception as e:
            error_msg = f"Scene command failed: {e}"
            logger.error(error_msg, exc_info=True)
            await self._publish_command_error(topic, error_msg)

    async def handle_command(self, topic: str, payload: str) -> None:
        """
        Handle MQTT command messages.

        Topic formats:
        - Controls: {base_topic}/{device_id}/controls/{control_name}/set
        - Scene enable: {base_topic}/{device_id}/ifm/scenes/{scene_id}/enabled/set
        - Scene trigger: {base_topic}/{device_id}/ifm/scenes/{scene_id}/trigger/set

        Args:
            topic: MQTT topic that received the command
            payload: Command payload (string, number, or enum value)

        Raises:
            Exception: On command execution failure (published to error topic)
        """
        try:
            topic_parts = topic.split("/")

            # Check for scene commands first (path contains /scenes/ and ends with /set)
            if "/scenes/" in topic and topic.endswith("/set"):
                await self._handle_scene_command(topic, payload)
                return

            # Parse topic to extract device_id and control_name
            # Expected format: {base_topic}/{device_id}/controls/{control_name}/set
            if len(topic_parts) < 5 or topic_parts[-3] != "controls" or topic_parts[-1] != "set":
                logger.debug(f"Ignoring non-command topic: {topic}")
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
                        "off": "OFF",
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
                        "performance": "NORMAL",  # Maps to NORMAL
                        "high_demand": "COMFORT",  # Maps to COMFORT
                        "heat_pump": "CUSTOM",  # Maps to CUSTOM
                        "off": "OFF",  # Maps to OFF
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

                # Special handling for clear_alarms button (HTTP only)
                if attribute.method_name == "clear_alarms":
                    if self.config.integration.connection_type == "http":
                        logger.info("Clearing alarms via HTTP API...")
                        await self.device_client.clear_alarms()
                        logger.info("✓ Alarms cleared successfully")
                        # Re-poll alarms to update state
                        await self._poll_and_publish_alarms(device)
                        return

                    error_msg = "Clear alarms is only available with HTTP connection"
                    logger.error(error_msg)
                    await self._publish_command_error(topic, error_msg)
                    return

                parsed_value = 1  # Button press value

            elif attribute.ha_component == "switch":
                # Switch commands expect "ON" or "OFF"
                if payload.upper() not in ("ON", "OFF"):
                    error_msg = f"Invalid switch payload: {payload}"
                    logger.error(error_msg)
                    await self._publish_command_error(topic, error_msg)
                    return
                parsed_value = payload.upper() == "ON"

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

                if not self.device_client.is_connected:
                    logger.warning("Device client disconnected, attempting reconnection...")
                    await self.device_client.reconnect_with_backoff()
                    logger.info("Device client reconnected successfully")

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
        conn_type = self.config.integration.connection_type.upper()
        logger.info(f"Starting {conn_type}-MQTT bridge")

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


# Backward compatibility alias
ModbusMQTTBridge = Bridge
