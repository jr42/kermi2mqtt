"""Home Assistant MQTT Discovery - Manual Implementation.

This module manually creates and publishes MQTT discovery messages for Home Assistant
while maintaining agnostic state publishing to simple MQTT topics that work with
ANY MQTT consumer (n8n, ioBroker, Node-RED, Grafana, etc.).

Architecture:
1. State publishing (agnostic): Publish values to kermi/device_id/sensor/name
2. HA Discovery (optional): Tell HA about those same state topics

Benefits of manual implementation:
- Full control over topic structure
- Uses existing MQTT client (single connection)
- State topics match exactly what we're publishing
- No library overhead or reconnections

References:
- HA MQTT Discovery: https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery
- Contract: specs/001-modbus-mqtt/contracts/ha-discovery.md
"""

import json
import logging
from typing import Any

from .models.datapoint import DeviceAttribute
from .models.device import KermiDevice
from .mqtt_client import MQTTClient

logger = logging.getLogger(__name__)

# Attribute filtering constants for StorageSystem devices
# Duplicated from bridge.py to avoid circular imports
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
    "set_hot_water_setpoint_constant",  # Control method
    "set_one_time_heating",  # DHW boost control
}

# Controls to EXCLUDE from individual entity discovery
# (they're handled by climate/water_heater entities instead)
STORAGE_HEATING_EXCLUDED_CONTROLS = {
    "season_selection",  # In climate entity (mode)
    "energy_mode",  # In climate entity (preset)
    "one_time_heating",  # Not applicable to floor heating
}

STORAGE_DHW_EXCLUDED_CONTROLS = {
    "season_selection",  # In water_heater entity (not used for DHW)
    "energy_mode",  # In water_heater entity (mode)
    "hot_water_setpoint",  # In water_heater entity (temperature)
    # NOTE: one_time_heating is KEPT as separate button
}


def _should_publish_attribute(
    device_type: str,
    attribute: DeviceAttribute,
    value: Any,
) -> bool:
    """
    Determine if an attribute should be published based on device type and value.

    Filtering Rules:
    0. Never publish None or obviously wrong values (sanity checks)
    1. Always publish if value is non-zero (real data overrides everything)
    2. Filter heating-only attributes on DHW devices when value is 0.0
    3. Filter DHW-only attributes on heating devices when value is 0.0
    4. Publish everything else (shared sensors: temps, operating hours, etc.)

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

    # RULE 1.6b: Filter DHW controls from storage_dhw individual discovery
    # (they're handled by water_heater entity instead)
    if device_type == "storage_dhw" and attribute.method_name == "set_hot_water_setpoint_constant":
        logger.debug("Filtering set_hot_water_setpoint_constant - handled by water_heater entity")
        return False

    # RULE 1.7: Filter controls that are handled by climate/water_heater entities
    # This avoids duplicating controls in HA UI
    topic_suffix = attribute.mqtt_topic_suffix.split("/")[-1]
    if device_type == "storage_heating" and topic_suffix in STORAGE_HEATING_EXCLUDED_CONTROLS:
        logger.debug(f"Filtering {topic_suffix} - handled by climate entity")
        return False

    if device_type == "storage_dhw" and topic_suffix in STORAGE_DHW_EXCLUDED_CONTROLS:
        logger.debug(f"Filtering {topic_suffix} - handled by water_heater entity")
        return False

    # RULE 1: Always publish non-zero values (real data)
    if value not in (0.0, 0, False):
        return True

    # RULE 4: Publish everything else (shared sensors, temps, etc.)
    return True


def generate_device_info(device: KermiDevice) -> dict:
    """Generate Home Assistant device info dictionary.

    Creates a UNIFIED device for all Kermi entities. This means:
    - All heat_pump, storage_heating, storage_dhw entities appear under ONE device
    - Cleaner UX in Home Assistant
    - Technical MQTT separation is maintained (different topics per Modbus unit)

    Args:
        device: Kermi device (used to extract base identifier)

    Returns:
        Device info dict with unified identifiers, name, manufacturer, model

    Example:
        {
            "identifiers": ["kermi_xcenter"],
            "name": "Kermi X-Center",
            "manufacturer": "Kermi",
            "model": "X-Center Heat Pump System"
        }
    """
    # Extract base identifier (e.g., "xcenter" from "xcenter_heat_pump")
    # Split on first underscore to get the system name
    base_id = device.device_id.split("_", 1)[0] if "_" in device.device_id else device.device_id

    return {
        "identifiers": [f"kermi_{base_id}"],
        "name": "Kermi X-Center",
        "manufacturer": "Kermi",
        "model": "X-Center Heat Pump System",
    }


def generate_sensor_discovery_payload(
    device: KermiDevice,
    attribute: DeviceAttribute,
) -> dict:
    """Generate Home Assistant sensor discovery payload.

    Args:
        device: Device this attribute belongs to
        attribute: Attribute to create sensor for

    Returns:
        Discovery payload dictionary

    Example payload:
        {
            "name": "Outdoor Temperature",
            "state_topic": "kermi/xcenter/heat_pump/sensors/outdoor_temp",
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "state_class": "measurement",
            "availability_topic": "kermi/xcenter/availability",
            "unique_id": "xcenter_heat_pump_outdoor_temp",
            "device": {
                "identifiers": ["xcenter_heat_pump"],
                "name": "Kermi Heat Pump",
                ...
            }
        }
    """
    # Extract object_id from mqtt_topic_suffix
    object_id = attribute.mqtt_topic_suffix.split("/")[-1]

    # Build state topic (where values are actually published)
    state_topic = device.get_mqtt_topic(attribute)
    availability_topic = device.get_availability_topic()

    # Base discovery payload
    payload = {
        "name": attribute.friendly_name,
        "state_topic": state_topic,
        "availability_topic": availability_topic,
        "unique_id": f"{device.device_id}_{object_id}",
        "device": generate_device_info(device),
    }

    # Add binary_sensor specific payloads
    if attribute.ha_component == "binary_sensor":
        payload["payload_on"] = "ON"
        payload["payload_off"] = "OFF"

    # Add HA-specific config from attribute
    # (device_class, unit_of_measurement, state_class, icon, etc.)
    payload.update(attribute.ha_config)

    return payload


def generate_number_discovery_payload(
    device: KermiDevice,
    attribute: DeviceAttribute,
) -> dict:
    """Generate Home Assistant number entity discovery payload.

    Args:
        device: Device this number belongs to
        attribute: Writable number attribute (e.g., DHW setpoint)

    Returns:
        Discovery payload dict
    """
    object_id = attribute.mqtt_topic_suffix.split("/")[-1]
    # For writable attributes: use same base topic for state and command (command adds /set)
    # This matches the pattern used by successful MQTT integrations like zigbee2mqtt
    base_topic = device.get_mqtt_topic(attribute)
    state_topic = base_topic
    command_topic = f"{base_topic}/set"

    payload = {
        "name": attribute.friendly_name,
        "unique_id": f"{device.device_id}_{object_id}",
        "device": generate_device_info(device),
        "state_topic": state_topic,
        "command_topic": command_topic,
        "availability_topic": device.get_availability_topic(),
        "optimistic": False,  # Critical: HA must publish to command_topic, not state_topic directly
    }

    # Add number-specific config from attribute (min, max, step, mode, etc.)
    payload.update(attribute.ha_config)

    return payload


def generate_select_discovery_payload(
    device: KermiDevice,
    attribute: DeviceAttribute,
) -> dict:
    """Generate Home Assistant select entity discovery payload.

    Args:
        device: Device this select belongs to
        attribute: Writable select attribute (e.g., season selection, energy mode)

    Returns:
        Discovery payload dict
    """
    object_id = attribute.mqtt_topic_suffix.split("/")[-1]
    # For writable attributes: use same base topic for state and command (command adds /set)
    # This matches the pattern used by successful MQTT integrations like zigbee2mqtt
    base_topic = device.get_mqtt_topic(attribute)
    state_topic = base_topic
    command_topic = f"{base_topic}/set"

    payload = {
        "name": attribute.friendly_name,
        "unique_id": f"{device.device_id}_{object_id}",
        "device": generate_device_info(device),
        "state_topic": state_topic,
        "command_topic": command_topic,
        "availability_topic": device.get_availability_topic(),
        "optimistic": False,  # Critical: HA must publish to command_topic, not state_topic directly
    }

    # Add select-specific config from attribute (options, icon, etc.)
    payload.update(attribute.ha_config)

    return payload


def generate_button_discovery_payload(
    device: KermiDevice,
    attribute: DeviceAttribute,
) -> dict:
    """Generate Home Assistant button entity discovery payload.

    Args:
        device: Device this button belongs to
        attribute: Writable button attribute (e.g., one-time heating)

    Returns:
        Discovery payload dict
    """
    object_id = attribute.mqtt_topic_suffix.split("/")[-1]
    command_topic = f"{device.get_mqtt_topic(attribute)}/set"

    payload = {
        "name": attribute.friendly_name,
        "unique_id": f"{device.device_id}_{object_id}",
        "device": generate_device_info(device),
        "command_topic": command_topic,
        "availability_topic": device.get_availability_topic(),
        "payload_press": "1",
    }

    # Add button-specific config from attribute (icon, etc.)
    payload.update(attribute.ha_config)

    return payload


def generate_discovery_topic(
    device: KermiDevice,
    attribute: DeviceAttribute,
    ha_discovery_prefix: str,
) -> str:
    """Generate Home Assistant discovery topic.

    Args:
        device: Device this attribute belongs to
        attribute: Attribute to create sensor for
        ha_discovery_prefix: HA discovery prefix (typically "homeassistant")

    Returns:
        Discovery topic string

    Topic format:
        <discovery_prefix>/<component>/<device_id>/<object_id>/config

    Example:
        homeassistant/sensor/xcenter_heat_pump/outdoor_temp/config
    """
    object_id = attribute.mqtt_topic_suffix.split("/")[-1]

    discovery_topic = (
        f"{ha_discovery_prefix}/{attribute.ha_component}/{device.device_id}/{object_id}/config"
    )

    return discovery_topic


async def publish_discovery_message(
    mqtt_client: MQTTClient,
    device: KermiDevice,
    attribute: DeviceAttribute,
    ha_discovery_prefix: str,
) -> None:
    """Publish a single discovery message for an attribute.

    Args:
        mqtt_client: Connected MQTT client
        device: Device this attribute belongs to
        attribute: Attribute to create sensor for
        ha_discovery_prefix: HA discovery prefix

    Raises:
        Exception: If MQTT publish fails
    """
    # Generate discovery topic
    topic = generate_discovery_topic(device, attribute, ha_discovery_prefix)

    # Generate payload based on component type
    if attribute.ha_component == "number":
        payload = generate_number_discovery_payload(device, attribute)
    elif attribute.ha_component == "select":
        payload = generate_select_discovery_payload(device, attribute)
    elif attribute.ha_component == "button":
        payload = generate_button_discovery_payload(device, attribute)
    elif attribute.ha_component in ("sensor", "binary_sensor"):
        payload = generate_sensor_discovery_payload(device, attribute)
    else:
        logger.error(f"Unsupported component type: {attribute.ha_component}")
        return

    # Convert payload to JSON
    payload_json = json.dumps(payload)

    logger.debug(f"Publishing discovery to: {topic}")
    logger.debug(f"  Payload: {payload_json[:200]}...")  # Log first 200 chars

    # Publish discovery message (retained)
    await mqtt_client.publish_state(
        topic=topic,
        payload=payload_json,
        retain=True,  # Discovery messages must be retained
    )

    logger.debug(f"✓ Published discovery for {attribute.friendly_name}")


async def publish_all_discovery(
    mqtt_client: MQTTClient,
    devices: list[KermiDevice],
    ha_discovery_prefix: str,
) -> None:
    """Publish discovery messages for all devices and their attributes.

    Args:
        mqtt_client: Connected MQTT client
        devices: List of detected devices with attributes
        ha_discovery_prefix: HA discovery prefix (typically "homeassistant")

    Note:
        This only tells HA about the sensors. Actual state values are
        published separately by bridge.py to the same state topics.

        Attributes are filtered based on device type to avoid creating
        HA entities for sensors that will never have data (e.g., hot_water_*
        on heating-only devices).
    """
    logger.info(f"Publishing Home Assistant discovery for {len(devices)} device(s)...")

    total_published = 0
    total_filtered = 0

    for device in devices:
        logger.debug(
            f"Publishing discovery messages for {device.device_id} "
            f"(device_type: {device.device_type})"
        )

        for attribute in device.attributes:
            # Filter discovery for attributes that won't have data
            # Use dummy 0.0 value to simulate filtering check
            if not _should_publish_attribute(device.device_type, attribute, 0.0):
                logger.debug(
                    f"Skipping discovery for {device.device_id}.{attribute.method_name} "
                    f"(not applicable to {device.device_type})"
                )
                total_filtered += 1
                continue

            try:
                await publish_discovery_message(mqtt_client, device, attribute, ha_discovery_prefix)
                total_published += 1

            except Exception as e:
                logger.error(
                    f"Failed to publish discovery for {attribute.friendly_name}: {e}",
                    exc_info=True,
                )
                # Continue with other sensors

    logger.info(
        f"✓ Published {total_published} sensor discovery messages "
        f"({total_filtered} filtered as not applicable)"
    )

    # Publish complex entities (climate and water_heater)
    # These aggregate multiple control/sensor attributes into unified entities
    logger.info("Publishing complex entity discovery (climate, water_heater)...")

    complex_entities_published = 0

    for device in devices:
        try:
            # Publish climate entity for storage_heating devices
            if device.device_type == "storage_heating":
                climate_topic = f"{ha_discovery_prefix}/climate/{device.device_id}/climate/config"
                climate_payload = generate_climate_discovery_payload(device)
                await mqtt_client.publish_state(
                    topic=climate_topic,
                    payload=climate_payload,
                    retain=True,
                )
                logger.debug(f"✓ Published climate entity for {device.device_id}")
                complex_entities_published += 1

            # Publish water_heater entity for storage_dhw devices
            elif device.device_type == "storage_dhw":
                water_heater_topic = (
                    f"{ha_discovery_prefix}/water_heater/{device.device_id}/water_heater/config"
                )
                water_heater_payload = generate_water_heater_discovery_payload(device)
                await mqtt_client.publish_state(
                    topic=water_heater_topic,
                    payload=water_heater_payload,
                    retain=True,
                )
                logger.debug(f"✓ Published water_heater entity for {device.device_id}")
                complex_entities_published += 1

        except Exception as e:
            logger.error(
                f"Failed to publish complex entity for {device.device_id}: {e}",
                exc_info=True,
            )

    logger.info(f"✓ Published {complex_entities_published} complex entity discovery messages")


async def remove_discovery_messages(
    mqtt_client: MQTTClient,
    devices: list[KermiDevice],
    ha_discovery_prefix: str,
) -> None:
    """Remove discovery messages from MQTT (makes entities disappear in HA).

    Publishes empty retained messages to all discovery topics.
    Only call this if you want to uninstall/remove entities completely.

    Args:
        mqtt_client: Connected MQTT client
        devices: List of devices whose entities should be removed
        ha_discovery_prefix: HA discovery prefix
    """
    logger.info("Removing Home Assistant discovery messages...")

    for device in devices:
        for attribute in device.attributes:
            try:
                topic = generate_discovery_topic(device, attribute, ha_discovery_prefix)
                # Publish empty retained message to remove discovery
                await mqtt_client.publish_state(
                    topic=topic,
                    payload="",
                    retain=True,
                )
            except Exception as e:
                logger.error(f"Failed to remove discovery for {attribute.friendly_name}: {e}")

    logger.info("Discovery cleanup complete")


def generate_climate_discovery_payload(
    device: KermiDevice,
) -> dict:
    """Generate Home Assistant climate entity discovery payload.

    Creates climate entity for heating control:
    - Current temperature from heating circuit
    - HVAC mode control (maps season_selection)
    - Preset mode control (maps energy_mode)
    - Action state (what the system is currently doing)
    - NO temperature setpoint (EU uses room thermostats per room)

    Args:
        device: StorageSystem heating device

    Returns:
        Discovery payload dict for climate entity

    Example:
        For storage_heating device, creates climate entity with mode
        control suitable for EU floor heating systems.
    """
    current_temp_topic = f"{device.mqtt_base_topic}/sensors/heating_circuit_actual"
    mode_command_topic = f"{device.mqtt_base_topic}/controls/season_selection/set"
    mode_state_topic = f"{device.mqtt_base_topic}/sensors/season_selection"
    preset_command_topic = f"{device.mqtt_base_topic}/controls/energy_mode/set"
    preset_state_topic = f"{device.mqtt_base_topic}/sensors/energy_mode"
    action_topic = f"{device.mqtt_base_topic}/sensors/heating_circuit_status"

    payload = {
        "name": "Floor Heating",
        "unique_id": f"{device.device_id}_climate",
        "device": generate_device_info(device),
        # Current temperature (read-only)
        "current_temperature_topic": current_temp_topic,
        "temperature_unit": "C",
        # HVAC mode control (season selection: AUTO, HEATING, COOLING, OFF)
        "mode_command_topic": mode_command_topic,
        "mode_state_topic": mode_state_topic,
        "modes": ["auto", "heat", "cool", "off"],
        # Preset modes (energy modes: ECO, NORMAL, COMFORT, OFF)
        # Note: CUSTOM is not exposed as HA doesn't allow 'none' as a preset mode
        "preset_mode_command_topic": preset_command_topic,
        "preset_mode_state_topic": preset_state_topic,
        "preset_modes": ["eco", "comfort", "boost", "away"],
        # Current action (what the device is doing right now)
        "action_topic": action_topic,
        "action_template": (
            "{{ 'heating' if value in ['HEATING', 'HEATING_UP'] else "
            "'cooling' if value in ['COOLING', 'COOLING_DOWN'] else "
            "'idle' }}"
        ),
        # Optimistic mode off - we have state topics for everything
        "optimistic": False,
        # Availability
        "availability_topic": device.get_availability_topic(),
        # HVAC Mode - values are pre-transformed in bridge.py
        # State topic publishes: 'auto', 'heat', 'cool', 'off' (lowercase)
        # Commands need to be transformed back to enum values
        "mode_command_template": (
            "{% set modes = {'auto': 'AUTO', 'heat': 'HEATING', 'cool': 'COOLING', 'off': 'OFF'} %}"
            "{{ modes[value] if value in modes else 'OFF' }}"
        ),
        # Preset Mode - values are pre-transformed in bridge.py
        # State topic publishes: 'eco', 'comfort', 'boost', 'away' (lowercase)
        # Commands need to be transformed back to enum values
        "preset_mode_command_template": (
            "{% set modes = {'eco': 'ECO', 'comfort': 'NORMAL', 'boost': 'COMFORT', 'away': 'OFF'} %}"
            "{{ modes[value] if value in modes else 'NORMAL' }}"
        ),
    }

    return payload


def generate_water_heater_discovery_payload(
    device: KermiDevice,
) -> dict:
    """Generate Home Assistant water_heater entity discovery payload.

    Creates water_heater entity for DHW control with mode support:
    - Temperature setpoint control (40-60°C with safety validation)
    - Current temperature reading
    - Operating mode support (maps energy_mode sensor)

    Args:
        device: StorageSystem DHW device

    Returns:
        Discovery payload dict for water_heater entity

    Example:
        For storage_dhw device, creates water_heater entity with
        temperature and mode control.
    """
    current_temp_topic = f"{device.mqtt_base_topic}/sensors/hot_water_actual"
    target_temp_command_topic = f"{device.mqtt_base_topic}/controls/hot_water_setpoint/set"
    target_temp_state_topic = f"{device.mqtt_base_topic}/sensors/hot_water_setpoint_constant"
    mode_command_topic = f"{device.mqtt_base_topic}/controls/energy_mode/set"
    mode_state_topic = f"{device.mqtt_base_topic}/sensors/energy_mode"

    payload = {
        "name": "Hot Water",
        "unique_id": f"{device.device_id}_water_heater",
        "device": generate_device_info(device),
        # Current temperature
        "current_temperature_topic": current_temp_topic,
        "temperature_unit": "C",
        # Temperature setpoint control
        "temperature_command_topic": target_temp_command_topic,
        "temperature_state_topic": target_temp_state_topic,
        "min_temp": 40,
        "max_temp": 60,
        "precision": 0.5,
        # Operating mode (map energy_mode: OFF, ECO, NORMAL, COMFORT, CUSTOM)
        "mode_command_topic": mode_command_topic,
        "mode_state_topic": mode_state_topic,
        "modes": ["off", "eco", "performance", "high_demand", "heat_pump"],
        # Optimistic mode off - we have state topics for everything
        "optimistic": False,
        # Availability
        "availability_topic": device.get_availability_topic(),
        # Mode templates - for water_heater, we need special mapping
        # State values from bridge are: 'eco', 'comfort', 'boost', 'away', 'heat_pump' (transformed EnergyMode)
        # But water_heater expects: 'eco', 'performance', 'high_demand', etc.
        "mode_state_template": (
            "{% set modes = {'eco': 'eco', 'comfort': 'performance', 'boost': 'high_demand', 'away': 'off', 'heat_pump': 'heat_pump'} %}"
            "{{ modes[value] if value in modes else 'performance' }}"
        ),
        "mode_command_template": (
            "{% set modes = {'off': 'OFF', 'eco': 'ECO', 'performance': 'NORMAL', 'high_demand': 'COMFORT', 'heat_pump': 'CUSTOM'} %}"
            "{{ modes[value] if value in modes else 'NORMAL' }}"
        ),
    }

    return payload
