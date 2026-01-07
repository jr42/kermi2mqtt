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
        entity_category="diagnostic",
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
        entity_category="diagnostic",
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
        enabled_by_default=False,
        entity_category="diagnostic",
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
        enabled_by_default=False,
        entity_category="diagnostic",
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
            "suggested_display_precision": 1,
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
            "suggested_display_precision": 1,
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
            "suggested_display_precision": 1,
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
    # ==========================================================================
    # PV Modulation (py-kermi-xcenter 0.3.1+)
    # ==========================================================================
    # Status sensors
    DeviceAttribute(
        device_class="HeatPump",
        method_name="pv_modulation_active",
        friendly_name="PV Modulation Active",
        mqtt_topic_suffix="binary_sensors/pv_modulation_active",
        writable=False,
        ha_component="binary_sensor",
        ha_config={"icon": "mdi:solar-power"},
    ),
    DeviceAttribute(
        device_class="HeatPump",
        method_name="pv_modulation_enabled",
        friendly_name="PV Modulation Enabled",
        mqtt_topic_suffix="switches/pv_modulation_enabled",
        writable=True,
        ha_component="switch",
        ha_config={"icon": "mdi:solar-power-variant"},
    ),
    # Power sensors
    DeviceAttribute(
        device_class="HeatPump",
        method_name="pv_modulation_power",
        friendly_name="PV Modulation Power",
        mqtt_topic_suffix="sensors/pv_modulation_power",
        writable=False,
        ha_component="sensor",
        ha_config={
            "device_class": "power",
            "unit_of_measurement": "W",
            "state_class": "measurement",
            "icon": "mdi:solar-power",
        },
    ),
    DeviceAttribute(
        device_class="HeatPump",
        method_name="pv_available_power",
        friendly_name="PV Available Power",
        mqtt_topic_suffix="sensors/pv_available_power",
        writable=False,
        ha_component="sensor",
        ha_config={
            "device_class": "power",
            "unit_of_measurement": "W",
            "state_class": "measurement",
            "icon": "mdi:solar-power",
        },
    ),
    DeviceAttribute(
        device_class="HeatPump",
        method_name="pv_electrical_power",
        friendly_name="PV Electrical Power",
        mqtt_topic_suffix="sensors/pv_electrical_power",
        writable=False,
        ha_component="sensor",
        ha_config={
            "device_class": "power",
            "unit_of_measurement": "W",
            "state_class": "measurement",
        },
        enabled_by_default=False,
        entity_category="diagnostic",
    ),
    DeviceAttribute(
        device_class="HeatPump",
        method_name="pv_calculated_heating_power",
        friendly_name="PV Target Heating Power",
        mqtt_topic_suffix="sensors/pv_target_heating_power",
        writable=False,
        ha_component="sensor",
        ha_config={
            "device_class": "power",
            "unit_of_measurement": "kW",
            "state_class": "measurement",
        },
        enabled_by_default=False,
        entity_category="diagnostic",
    ),
    # PV Power settings (writable)
    DeviceAttribute(
        device_class="HeatPump",
        method_name="pv_setpoint_power",
        friendly_name="PV Setpoint Power",
        mqtt_topic_suffix="controls/pv_setpoint_power",
        writable=True,
        ha_component="number",
        ha_config={
            "device_class": "power",
            "unit_of_measurement": "W",
            "min": 0,
            "max": 10000,
            "step": 100,
            "icon": "mdi:solar-power-variant-outline",
        },
    ),
    DeviceAttribute(
        device_class="HeatPump",
        method_name="pv_turn_on_power",
        friendly_name="PV Turn-On Power",
        mqtt_topic_suffix="controls/pv_turn_on_power",
        writable=True,
        ha_component="number",
        ha_config={
            "device_class": "power",
            "unit_of_measurement": "W",
            "min": 0,
            "max": 10000,
            "step": 100,
            "entity_category": "config",
        },
        enabled_by_default=False,
    ),
    DeviceAttribute(
        device_class="HeatPump",
        method_name="pv_turn_off_power",
        friendly_name="PV Turn-Off Power",
        mqtt_topic_suffix="controls/pv_turn_off_power",
        writable=True,
        ha_component="number",
        ha_config={
            "device_class": "power",
            "unit_of_measurement": "W",
            "min": 0,
            "max": 10000,
            "step": 100,
            "entity_category": "config",
        },
        enabled_by_default=False,
    ),
    # PV Delay settings
    DeviceAttribute(
        device_class="HeatPump",
        method_name="pv_pre_delay",
        friendly_name="PV Pre-Delay",
        mqtt_topic_suffix="controls/pv_pre_delay",
        writable=True,
        ha_component="number",
        ha_config={
            "unit_of_measurement": "min",
            "min": 0,
            "max": 60,
            "step": 1,
            "icon": "mdi:timer-outline",
            "entity_category": "config",
        },
        enabled_by_default=False,
    ),
    DeviceAttribute(
        device_class="HeatPump",
        method_name="pv_post_delay",
        friendly_name="PV Post-Delay",
        mqtt_topic_suffix="controls/pv_post_delay",
        writable=True,
        ha_component="number",
        ha_config={
            "unit_of_measurement": "min",
            "min": 0,
            "max": 60,
            "step": 1,
            "icon": "mdi:timer-outline",
            "entity_category": "config",
        },
        enabled_by_default=False,
    ),
    # PV Temperature setpoints
    DeviceAttribute(
        device_class="HeatPump",
        method_name="pv_setpoint_temp_heating",
        friendly_name="PV Heating Setpoint",
        mqtt_topic_suffix="controls/pv_setpoint_temp_heating",
        writable=True,
        ha_component="number",
        ha_config={
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "min": 20,
            "max": 45,
            "step": 0.5,
            "entity_category": "config",
        },
        enabled_by_default=False,
    ),
    DeviceAttribute(
        device_class="HeatPump",
        method_name="pv_setpoint_temp_hot_water",
        friendly_name="PV Hot Water Setpoint",
        mqtt_topic_suffix="controls/pv_setpoint_temp_hot_water",
        writable=True,
        ha_component="number",
        ha_config={
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "min": 40,
            "max": 65,
            "step": 0.5,
            "entity_category": "config",
        },
        enabled_by_default=False,
    ),
    DeviceAttribute(
        device_class="HeatPump",
        method_name="pv_setpoint_temp_cooling",
        friendly_name="PV Cooling Setpoint",
        mqtt_topic_suffix="controls/pv_setpoint_temp_cooling",
        writable=True,
        ha_component="number",
        ha_config={
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "min": 15,
            "max": 30,
            "step": 0.5,
            "entity_category": "config",
        },
        enabled_by_default=False,
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
        },
        enabled_by_default=False,
        entity_category="diagnostic",
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
    # One-Time Heating Button (manual hot water boost)
    DeviceAttribute(
        device_class="StorageSystem",
        method_name="set_hot_water_single_charge_active",
        friendly_name="Boost Hot Water",
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


# =============================================================================
# IFM Gateway Attribute Mappings (Unit 0) - HTTP API Only
# Based on actual data keys from get_all_values(0)
# =============================================================================

IFM_ATTRIBUTES = [
    # ==========================================================================
    # Network Info (Tier 3: diagnostic, disabled by default)
    # ==========================================================================
    DeviceAttribute(
        device_class="IFM",
        method_name="ifm_ip_address",
        friendly_name="IP Address",
        mqtt_topic_suffix="sensors/ip_address",
        writable=False,
        ha_component="sensor",
        ha_config={"icon": "mdi:ip-network"},
        enabled_by_default=False,
        entity_category="diagnostic",
    ),
    DeviceAttribute(
        device_class="IFM",
        method_name="ifm_hostname",
        friendly_name="Hostname",
        mqtt_topic_suffix="sensors/hostname",
        writable=False,
        ha_component="sensor",
        ha_config={"icon": "mdi:server"},
        enabled_by_default=False,
        entity_category="diagnostic",
    ),
    DeviceAttribute(
        device_class="IFM",
        method_name="ifm_serial_number",
        friendly_name="Serial Number",
        mqtt_topic_suffix="sensors/serial_number",
        writable=False,
        ha_component="sensor",
        ha_config={"icon": "mdi:barcode"},
        enabled_by_default=False,
        entity_category="diagnostic",
    ),
    DeviceAttribute(
        device_class="IFM",
        method_name="ifm_software_version",
        friendly_name="Software Version",
        mqtt_topic_suffix="sensors/software_version",
        writable=False,
        ha_component="sensor",
        ha_config={"icon": "mdi:package-variant"},
        enabled_by_default=False,
        entity_category="diagnostic",
    ),
    DeviceAttribute(
        device_class="IFM",
        method_name="ifm_gateway",
        friendly_name="Gateway",
        mqtt_topic_suffix="sensors/gateway",
        writable=False,
        ha_component="sensor",
        ha_config={"icon": "mdi:router-network"},
        enabled_by_default=False,
        entity_category="diagnostic",
    ),
    DeviceAttribute(
        device_class="IFM",
        method_name="ifm_netmask",
        friendly_name="Netmask",
        mqtt_topic_suffix="sensors/netmask",
        writable=False,
        ha_component="sensor",
        ha_config={"icon": "mdi:ip-network-outline"},
        enabled_by_default=False,
        entity_category="diagnostic",
    ),
    DeviceAttribute(
        device_class="IFM",
        method_name="ifm_dhcp_enabled",
        friendly_name="DHCP Enabled",
        mqtt_topic_suffix="binary_sensors/dhcp_enabled",
        writable=False,
        ha_component="binary_sensor",
        ha_config={"icon": "mdi:ethernet"},
        enabled_by_default=False,
        entity_category="diagnostic",
    ),
    # ==========================================================================
    # Connectivity (Tier 1: enabled, important for users)
    # ==========================================================================
    DeviceAttribute(
        device_class="IFM",
        method_name="ifm_remote_connected",
        friendly_name="Remote Connected",
        mqtt_topic_suffix="binary_sensors/remote_connected",
        writable=False,
        ha_component="binary_sensor",
        ha_config={"device_class": "connectivity"},
        # Tier 1: Always enabled - important for monitoring
    ),
    # ==========================================================================
    # SmartGrid/EVU Signals (Tier 1-2: enabled for energy-aware users)
    # ==========================================================================
    DeviceAttribute(
        device_class="IFM",
        method_name="ifm_smartgrid_state",
        friendly_name="SmartGrid State",
        mqtt_topic_suffix="sensors/smartgrid_state",
        writable=False,
        ha_component="sensor",
        ha_config={"icon": "mdi:solar-power"},
        # Tier 1: Always enabled - SmartGrid is key feature
    ),
    DeviceAttribute(
        device_class="IFM",
        method_name="ifm_evu_signal",
        friendly_name="EVU Signal",
        mqtt_topic_suffix="binary_sensors/evu_signal",
        writable=False,
        ha_component="binary_sensor",
        ha_config={"icon": "mdi:transmission-tower"},
        # Tier 2: Enabled - useful for energy monitoring
    ),
    DeviceAttribute(
        device_class="IFM",
        method_name="ifm_sgready2_signal",
        friendly_name="SG Ready 2 Signal",
        mqtt_topic_suffix="binary_sensors/sgready2_signal",
        writable=False,
        ha_component="binary_sensor",
        ha_config={"icon": "mdi:flash"},
        # Tier 2: Enabled - useful for energy monitoring
    ),
    # ==========================================================================
    # Power Metering (Tier 1: enabled - key monitoring)
    # ==========================================================================
    DeviceAttribute(
        device_class="IFM",
        method_name="ifm_s0_power",
        friendly_name="S0 Power",
        mqtt_topic_suffix="sensors/s0_power",
        writable=False,
        ha_component="sensor",
        ha_config={
            "device_class": "power",
            "unit_of_measurement": "W",
            "state_class": "measurement",
        },
        # Tier 1: Always enabled - power monitoring is key
    ),
    # ==========================================================================
    # LEDs and Outputs (Tier 3: config, disabled by default)
    # ==========================================================================
    DeviceAttribute(
        device_class="IFM",
        method_name="ifm_led1",
        friendly_name="LED 1",
        mqtt_topic_suffix="switches/led1",
        writable=True,
        ha_component="switch",
        ha_config={"icon": "mdi:led-on"},
        enabled_by_default=False,
        entity_category="config",
    ),
    DeviceAttribute(
        device_class="IFM",
        method_name="ifm_led2",
        friendly_name="LED 2",
        mqtt_topic_suffix="switches/led2",
        writable=True,
        ha_component="switch",
        ha_config={"icon": "mdi:led-on"},
        enabled_by_default=False,
        entity_category="config",
    ),
    DeviceAttribute(
        device_class="IFM",
        method_name="ifm_output1",
        friendly_name="Output 1",
        mqtt_topic_suffix="switches/output1",
        writable=True,
        ha_component="switch",
        ha_config={"icon": "mdi:electric-switch"},
        enabled_by_default=False,
        entity_category="config",
    ),
    DeviceAttribute(
        device_class="IFM",
        method_name="ifm_output2",
        friendly_name="Output 2",
        mqtt_topic_suffix="switches/output2",
        writable=True,
        ha_component="switch",
        ha_config={"icon": "mdi:electric-switch"},
        enabled_by_default=False,
        entity_category="config",
    ),
    # ==========================================================================
    # System Status (Tier 1: enabled - important for monitoring)
    # ==========================================================================
    DeviceAttribute(
        device_class="IFM",
        method_name="ifm_alarm_status",
        friendly_name="Alarm Status",
        mqtt_topic_suffix="sensors/alarm_status",
        writable=False,
        ha_component="sensor",
        ha_config={"icon": "mdi:alert-circle"},
        # Tier 1: Always enabled - alarm monitoring is critical
    ),
    # ==========================================================================
    # Alarm System (Tier 1: enabled - critical for monitoring)
    # ==========================================================================
    DeviceAttribute(
        device_class="IFM",
        method_name="alarms_active",
        friendly_name="Alarms Active",
        mqtt_topic_suffix="binary_sensors/alarms_active",
        writable=False,
        ha_component="binary_sensor",
        ha_config={
            "device_class": "problem",
            "icon": "mdi:alert",
        },
        # Tier 1: Always enabled - critical for monitoring
    ),
    DeviceAttribute(
        device_class="IFM",
        method_name="alarm_count",
        friendly_name="Active Alarm Count",
        mqtt_topic_suffix="sensors/alarm_count",
        writable=False,
        ha_component="sensor",
        ha_config={
            "icon": "mdi:alert-circle-outline",
            "state_class": "measurement",
        },
        # Tier 1: Always enabled - critical for monitoring
    ),
    DeviceAttribute(
        device_class="IFM",
        method_name="clear_alarms",
        friendly_name="Clear Alarms",
        mqtt_topic_suffix="controls/clear_alarms",
        writable=True,
        ha_component="button",
        ha_config={
            "icon": "mdi:alert-remove",
        },
        # Tier 1: Always enabled - important control
    ),
    DeviceAttribute(
        device_class="IFM",
        method_name="alarm_history_count",
        friendly_name="Alarm History Count",
        mqtt_topic_suffix="sensors/alarm_history_count",
        writable=False,
        ha_component="sensor",
        ha_config={
            "icon": "mdi:history",
            "state_class": "total_increasing",
        },
        enabled_by_default=False,
        entity_category="diagnostic",
    ),
]


def get_ifm_attributes() -> list[DeviceAttribute]:
    """
    Get all attribute mappings for IFM gateway device.

    Returns:
        List of DeviceAttribute instances
    """
    return IFM_ATTRIBUTES.copy()


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
