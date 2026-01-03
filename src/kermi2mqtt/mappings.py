"""
Attribute mappings for HeatPump and StorageSystem devices.

Maps py-kermi-xcenter methods to MQTT topics and Home Assistant entities.

Based on research findings (research.md section 2b):
- HeatPump: 28 get_* methods
- StorageSystem: 36 get_* methods
"""

from kermi_xcenter.types import (
    EnergyMode,
    HeatingCircuitStatus,
    HeatPumpStatus,
    OperatingMode,
    SeasonSelection,
)

from kermi2mqtt.models.datapoint import DeviceAttribute

# =============================================================================
# HeatPump Attribute Mappings (Unit 40)
# Based on actual data keys from get_all_readable_values()
# =============================================================================

HEAT_PUMP_ATTRIBUTES = [
    # Temperature sensors
    DeviceAttribute(
        device_class="HeatPump",
        method_name="outdoor_temperature",
        friendly_name="Outdoor Temperature",
        mqtt_topic_suffix="sensors/outdoor_temp",
        writable=False,
        ha_component="sensor",
        ha_config={
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "state_class": "measurement",
        },
    ),
    DeviceAttribute(
        device_class="HeatPump",
        method_name="supply_temp_heat_pump",
        friendly_name="Supply Temperature",
        mqtt_topic_suffix="sensors/supply_temp",
        writable=False,
        ha_component="sensor",
        ha_config={
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "state_class": "measurement",
        },
    ),
    DeviceAttribute(
        device_class="HeatPump",
        method_name="return_temp_heat_pump",
        friendly_name="Return Temperature",
        mqtt_topic_suffix="sensors/return_temp",
        writable=False,
        ha_component="sensor",
        ha_config={
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "state_class": "measurement",
        },
    ),
    DeviceAttribute(
        device_class="HeatPump",
        method_name="energy_source_inlet",
        friendly_name="Energy Source Inlet Temperature",
        mqtt_topic_suffix="sensors/energy_source_inlet",
        writable=False,
        ha_component="sensor",
        ha_config={
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "state_class": "measurement",
        },
    ),
    DeviceAttribute(
        device_class="HeatPump",
        method_name="energy_source_outlet",
        friendly_name="Energy Source Outlet Temperature",
        mqtt_topic_suffix="sensors/energy_source_outlet",
        writable=False,
        ha_component="sensor",
        ha_config={
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "state_class": "measurement",
        },
    ),
    # Power and COP
    DeviceAttribute(
        device_class="HeatPump",
        method_name="power_total",
        friendly_name="Total Thermal Power",
        mqtt_topic_suffix="sensors/power_total",
        writable=False,
        ha_component="sensor",
        ha_config={
            "device_class": "power",
            "unit_of_measurement": "kW",
            "state_class": "measurement",
        },
    ),
    DeviceAttribute(
        device_class="HeatPump",
        method_name="power_electrical_total",
        friendly_name="Total Electrical Power",
        mqtt_topic_suffix="sensors/power_electrical",
        writable=False,
        ha_component="sensor",
        ha_config={
            "device_class": "power",
            "unit_of_measurement": "kW",
            "state_class": "measurement",
        },
    ),
    DeviceAttribute(
        device_class="HeatPump",
        method_name="power_heating",
        friendly_name="Heating Power",
        mqtt_topic_suffix="sensors/power_heating",
        writable=False,
        ha_component="sensor",
        ha_config={
            "device_class": "power",
            "unit_of_measurement": "kW",
            "state_class": "measurement",
        },
    ),
    DeviceAttribute(
        device_class="HeatPump",
        method_name="power_hot_water",
        friendly_name="Hot Water Power",
        mqtt_topic_suffix="sensors/power_hot_water",
        writable=False,
        ha_component="sensor",
        ha_config={
            "device_class": "power",
            "unit_of_measurement": "kW",
            "state_class": "measurement",
        },
    ),
    DeviceAttribute(
        device_class="HeatPump",
        method_name="cop_total",
        friendly_name="COP Total",
        mqtt_topic_suffix="sensors/cop_total",
        writable=False,
        ha_component="sensor",
        ha_config={
            "state_class": "measurement",
            "icon": "mdi:gauge",
        },
    ),
    DeviceAttribute(
        device_class="HeatPump",
        method_name="cop_heating",
        friendly_name="COP Heating",
        mqtt_topic_suffix="sensors/cop_heating",
        writable=False,
        ha_component="sensor",
        ha_config={
            "state_class": "measurement",
            "icon": "mdi:gauge",
        },
    ),
    DeviceAttribute(
        device_class="HeatPump",
        method_name="cop_hot_water",
        friendly_name="COP Hot Water",
        mqtt_topic_suffix="sensors/cop_hot_water",
        writable=False,
        ha_component="sensor",
        ha_config={
            "state_class": "measurement",
            "icon": "mdi:gauge",
        },
    ),
    # Status and runtime
    DeviceAttribute(
        device_class="HeatPump",
        method_name="heat_pump_status",
        friendly_name="Heat Pump Status",
        mqtt_topic_suffix="sensors/status",
        writable=False,
        ha_component="sensor",
        ha_config={
            "icon": "mdi:state-machine",
            "entity_category": "diagnostic",
        },
        value_enum=HeatPumpStatus,
    ),
    DeviceAttribute(
        device_class="HeatPump",
        method_name="global_alarm",
        friendly_name="Global Alarm",
        mqtt_topic_suffix="binary_sensors/alarm",
        writable=False,
        ha_component="binary_sensor",
        ha_config={
            "device_class": "problem",
        },
    ),
    DeviceAttribute(
        device_class="HeatPump",
        method_name="operating_hours_compressor",
        friendly_name="Compressor Operating Hours",
        mqtt_topic_suffix="sensors/compressor_hours",
        writable=False,
        ha_component="sensor",
        ha_config={
            "device_class": "duration",
            "unit_of_measurement": "h",
            "state_class": "total_increasing",
            "entity_category": "diagnostic",  # Maintenance metric - technical sensor
        },
    ),
    DeviceAttribute(
        device_class="HeatPump",
        method_name="operating_hours_fan",
        friendly_name="Fan Operating Hours",
        mqtt_topic_suffix="sensors/fan_hours",
        writable=False,
        ha_component="sensor",
        ha_config={
            "device_class": "duration",
            "unit_of_measurement": "h",
            "state_class": "total_increasing",
            "entity_category": "diagnostic",  # Maintenance metric - technical sensor
        },
    ),
    # PV modulation (read-only for MVP)
    DeviceAttribute(
        device_class="HeatPump",
        method_name="pv_modulation_status",
        friendly_name="PV Modulation Active",
        mqtt_topic_suffix="binary_sensors/pv_modulation",
        writable=False,
        ha_component="binary_sensor",
        ha_config={
            "icon": "mdi:solar-power",
        },
    ),
    DeviceAttribute(
        device_class="HeatPump",
        method_name="pv_modulation_power",
        friendly_name="PV Modulation Power",
        mqtt_topic_suffix="sensors/pv_power",
        writable=False,
        ha_component="sensor",
        ha_config={
            "device_class": "power",
            "unit_of_measurement": "W",
            "state_class": "measurement",
        },
    ),
]

# =============================================================================
# StorageSystem Attribute Mappings (Units 50/51)
# Based on actual data keys from get_all_readable_values()
# =============================================================================

STORAGE_SYSTEM_ATTRIBUTES = [
    # Temperature sensors (T1-T4)
    DeviceAttribute(
        device_class="StorageSystem",
        method_name="t1_temperature",
        friendly_name="T1 Temperature",
        mqtt_topic_suffix="sensors/t1_temp",
        writable=False,
        ha_component="sensor",
        ha_config={
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "state_class": "measurement",
            "entity_category": "diagnostic",  # Buffer temp - technical measurement
        },
    ),
    DeviceAttribute(
        device_class="StorageSystem",
        method_name="t4_temperature",
        friendly_name="Outdoor Temperature (T4)",
        mqtt_topic_suffix="sensors/t4_temp",
        writable=False,
        ha_component="sensor",
        ha_config={
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "state_class": "measurement",
            "entity_category": "diagnostic",  # Outdoor sensor - used for calculations
        },
    ),
    DeviceAttribute(
        device_class="StorageSystem",
        method_name="outdoor_temperature_avg",
        friendly_name="Outdoor Temperature Average",
        mqtt_topic_suffix="sensors/outdoor_temp_avg",
        writable=False,
        ha_component="sensor",
        ha_config={
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "state_class": "measurement",
        },
    ),
    # Heating circuit
    DeviceAttribute(
        device_class="StorageSystem",
        method_name="heating_setpoint",
        friendly_name="Heating Setpoint",
        mqtt_topic_suffix="sensors/heating_setpoint",
        writable=False,
        ha_component="sensor",
        ha_config={
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "state_class": "measurement",
        },
    ),
    DeviceAttribute(
        device_class="StorageSystem",
        method_name="heating_actual",
        friendly_name="Heating Actual Temperature",
        mqtt_topic_suffix="sensors/heating_actual",
        writable=False,
        ha_component="sensor",
        ha_config={
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "state_class": "measurement",
        },
    ),
    DeviceAttribute(
        device_class="StorageSystem",
        method_name="heating_circuit_setpoint",
        friendly_name="Heating Circuit Setpoint",
        mqtt_topic_suffix="sensors/heating_circuit_setpoint",
        writable=False,
        ha_component="sensor",
        ha_config={
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "state_class": "measurement",
        },
    ),
    DeviceAttribute(
        device_class="StorageSystem",
        method_name="heating_circuit_actual",
        friendly_name="Heating Circuit Actual",
        mqtt_topic_suffix="sensors/heating_circuit_actual",
        writable=False,
        ha_component="sensor",
        ha_config={
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "state_class": "measurement",
        },
    ),
    DeviceAttribute(
        device_class="StorageSystem",
        method_name="heating_circuit_status",
        friendly_name="Heating Circuit Status",
        mqtt_topic_suffix="sensors/heating_circuit_status",
        writable=False,
        ha_component="sensor",
        ha_config={
            "icon": "mdi:state-machine",
            "entity_category": "diagnostic",
        },
        value_enum=HeatingCircuitStatus,
    ),
    DeviceAttribute(
        device_class="StorageSystem",
        method_name="heating_circuit_operating_mode",
        friendly_name="Heating Circuit Operating Mode",
        mqtt_topic_suffix="sensors/heating_circuit_mode",
        writable=False,
        ha_component="sensor",
        ha_config={
            "icon": "mdi:cog",
            "entity_category": "diagnostic",
        },
        value_enum=OperatingMode,
    ),
    # Hot water
    DeviceAttribute(
        device_class="StorageSystem",
        method_name="hot_water_setpoint",
        friendly_name="Hot Water Setpoint",
        mqtt_topic_suffix="sensors/hot_water_setpoint",
        writable=False,
        ha_component="sensor",
        ha_config={
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "state_class": "measurement",
        },
    ),
    DeviceAttribute(
        device_class="StorageSystem",
        method_name="hot_water_actual",
        friendly_name="Hot Water Actual Temperature",
        mqtt_topic_suffix="sensors/hot_water_actual",
        writable=False,
        ha_component="sensor",
        ha_config={
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "state_class": "measurement",
        },
    ),
    DeviceAttribute(
        device_class="StorageSystem",
        method_name="hot_water_setpoint_constant",
        friendly_name="Hot Water Setpoint Constant",
        mqtt_topic_suffix="sensors/hot_water_setpoint_constant",
        writable=False,
        ha_component="sensor",
        ha_config={
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "state_class": "measurement",
        },
    ),
    # Cooling (if available)
    DeviceAttribute(
        device_class="StorageSystem",
        method_name="cooling_actual",
        friendly_name="Cooling Actual Temperature",
        mqtt_topic_suffix="sensors/cooling_actual",
        writable=False,
        ha_component="sensor",
        ha_config={
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "state_class": "measurement",
        },
    ),
    DeviceAttribute(
        device_class="StorageSystem",
        method_name="cooling_mode_active",
        friendly_name="Cooling Mode Active",
        mqtt_topic_suffix="binary_sensors/cooling_active",
        writable=False,
        ha_component="binary_sensor",
        ha_config={
            "icon": "mdi:snowflake",
        },
    ),
    # Mode and Status sensors (readable current state)
    DeviceAttribute(
        device_class="StorageSystem",
        method_name="season_selection_manual",
        friendly_name="Season Selection (Current)",
        mqtt_topic_suffix="sensors/season_selection",
        writable=False,
        ha_component="sensor",
        ha_config={
            "icon": "mdi:calendar-range",
        },
        value_enum=SeasonSelection,  # Maps numeric value to enum name
    ),
    DeviceAttribute(
        device_class="StorageSystem",
        method_name="heating_circuit_energy_mode",
        friendly_name="Energy Mode (Current)",
        mqtt_topic_suffix="sensors/energy_mode",
        writable=False,
        ha_component="sensor",
        ha_config={
            "icon": "mdi:leaf",
        },
        value_enum=EnergyMode,  # Maps numeric value to enum name
    ),
    # Season modes
    DeviceAttribute(
        device_class="StorageSystem",
        method_name="summer_mode_active",
        friendly_name="Summer Mode Active",
        mqtt_topic_suffix="binary_sensors/summer_mode",
        writable=False,
        ha_component="binary_sensor",
        ha_config={
            "icon": "mdi:weather-sunny",
        },
    ),
    # Operating hours
    DeviceAttribute(
        device_class="StorageSystem",
        method_name="operating_hours_circuit_pump",
        friendly_name="Circuit Pump Operating Hours",
        mqtt_topic_suffix="sensors/circuit_pump_hours",
        writable=False,
        ha_component="sensor",
        ha_config={
            "device_class": "duration",
            "unit_of_measurement": "h",
            "state_class": "total_increasing",
            "entity_category": "diagnostic",  # Maintenance metric - technical sensor
        },
    ),
    # =============================================================================
    # Control Attributes (User Story 2 - Writable)
    # =============================================================================
    # Hot Water Control (DHW - Unit 51)
    DeviceAttribute(
        device_class="StorageSystem",
        method_name="set_hot_water_setpoint_constant",
        friendly_name="Hot Water Setpoint",
        mqtt_topic_suffix="controls/hot_water_setpoint",
        writable=True,
        ha_component="number",
        ha_config={
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "min": 40.0,  # Legionella safety
            "max": 60.0,  # Scalding prevention
            "step": 0.5,
            "mode": "slider",
        },
    ),
    # One-Time Heating Button
    DeviceAttribute(
        device_class="StorageSystem",
        method_name="set_hot_water_single_charge_active",
        friendly_name="One-Time Heating",
        mqtt_topic_suffix="controls/one_time_heating",
        writable=True,
        ha_component="button",
        ha_config={
            "icon": "mdi:water-boiler",
        },
    ),
    # Season Selection (Manual Override)
    DeviceAttribute(
        device_class="StorageSystem",
        method_name="set_season_selection_manual",
        friendly_name="Season Selection",
        mqtt_topic_suffix="controls/season_selection",
        writable=True,
        ha_component="select",
        ha_config={
            "icon": "mdi:calendar-range",
            # Options match the transformed lowercase values published by bridge.py
            "options": ["auto", "heat", "cool", "off"],
        },
        value_enum=SeasonSelection,  # Maps 0-3 to enum
    ),
    # Energy Mode (Eco/Normal/Comfort)
    DeviceAttribute(
        device_class="StorageSystem",
        method_name="set_heating_circuit_energy_mode",
        friendly_name="Energy Mode",
        mqtt_topic_suffix="controls/energy_mode",
        writable=True,
        ha_component="select",
        ha_config={
            "icon": "mdi:leaf",
            # Options match the transformed lowercase values published by bridge.py
            # Note: CUSTOM maps to 'comfort' so we don't include it as separate option
            "options": ["away", "eco", "comfort", "boost"],
        },
        value_enum=EnergyMode,  # Maps 0-4 to enum
    ),
]


def get_heat_pump_attributes() -> list[DeviceAttribute]:
    """
    Get all attribute mappings for HeatPump device.

    Returns:
        List of DeviceAttribute instances
    """
    return HEAT_PUMP_ATTRIBUTES.copy()


def get_storage_system_attributes() -> list[DeviceAttribute]:
    """
    Get all attribute mappings for StorageSystem device.

    Returns:
        List of DeviceAttribute instances
    """
    return STORAGE_SYSTEM_ATTRIBUTES.copy()
