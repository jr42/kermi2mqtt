# Home Assistant MQTT Discovery Payloads

**Feature**: 001-modbus-mqtt
**Date**: 2025-11-25
**Purpose**: Define HA MQTT discovery message formats for automatic entity creation

---

## Discovery Topic Format

```
homeassistant/{component}/{node_id}/{object_id}/config
```

- `component`: Entity type (sensor, number, climate, switch, water_heater)
- `node_id`: Device identifier (e.g., `kermi_12345abc`)
- `object_id`: Unique object within device (e.g., `outdoor_temp`)

All discovery messages MUST have `retain=true`.

---

## Sensor Entity (Temperature)

```json
{
  "name": "Outdoor Temperature",
  "unique_id": "kermi_12345abc_outdoor_temp",
  "state_topic": "kermi/12345ABC/sensors/outdoor_temp",
  "unit_of_measurement": "°C",
  "device_class": "temperature",
  "state_class": "measurement",
  "availability_topic": "kermi/12345ABC/availability",
  "device": {
    "identifiers": ["kermi_12345abc"],
    "name": "Kermi Heat Pump",
    "manufacturer": "Kermi",
    "model": "x-center",
    "sw_version": "1.0.0"
  }
}
```

**Topic**: `homeassistant/sensor/kermi_12345abc/outdoor_temp/config`

---

## Sensor Entity (Power)

```json
{
  "name": "Thermal Power",
  "unique_id": "kermi_12345abc_power_thermal",
  "state_topic": "kermi/12345ABC/sensors/power_thermal",
  "unit_of_measurement": "kW",
  "device_class": "power",
  "state_class": "measurement",
  "availability_topic": "kermi/12345ABC/availability",
  "device": {
    "identifiers": ["kermi_12345abc"]
  }
}
```

---

## Sensor Entity (COP - Unitless)

```json
{
  "name": "Coefficient of Performance",
  "unique_id": "kermi_12345abc_cop",
  "state_topic": "kermi/12345ABC/sensors/cop",
  "device_class": "power_factor",
  "state_class": "measurement",
  "availability_topic": "kermi/12345ABC/availability",
  "icon": "mdi:chart-line",
  "device": {
    "identifiers": ["kermi_12345abc"]
  }
}
```

---

## Number Entity (DHW Setpoint)

```json
{
  "name": "Hot Water Setpoint",
  "unique_id": "kermi_12345abc_dhw_setpoint",
  "state_topic": "kermi/12345ABC/water_heater/target_temp",
  "command_topic": "kermi/12345ABC/water_heater/target_temp/set",
  "unit_of_measurement": "°C",
  "device_class": "temperature",
  "min": 40,
  "max": 60,
  "step": 0.5,
  "mode": "slider",
  "availability_topic": "kermi/12345ABC/availability",
  "device": {
    "identifiers": ["kermi_12345abc"]
  }
}
```

---

## Climate Entity (Full HVAC Control)

```json
{
  "name": "Kermi Heating",
  "unique_id": "kermi_12345abc_climate",
  "mode_command_topic": "kermi/12345ABC/climate/mode/set",
  "mode_state_topic": "kermi/12345ABC/climate/mode",
  "modes": ["off", "heat", "cool", "auto"],
  "temperature_command_topic": "kermi/12345ABC/climate/target_temp/set",
  "temperature_state_topic": "kermi/12345ABC/climate/target_temp",
  "current_temperature_topic": "kermi/12345ABC/sensors/supply_temp",
  "min_temp": 10,
  "max_temp": 30,
  "temp_step": 0.5,
  "temperature_unit": "C",
  "availability_topic": "kermi/12345ABC/availability",
  "device": {
    "identifiers": ["kermi_12345abc"],
    "name": "Kermi Heat Pump",
    "manufacturer": "Kermi",
    "model": "x-center"
  }
}
```

**Topic**: `homeassistant/climate/kermi_12345abc/main/config`

**Note**: Climate entity requires appropriate setter methods in py-kermi-xcenter for mode and temperature control. Implement only if library supports these operations.

---

## Water Heater Entity

```json
{
  "name": "Kermi DHW",
  "unique_id": "kermi_12345abc_water_heater",
  "mode_command_topic": "kermi/12345ABC/water_heater/mode/set",
  "mode_state_topic": "kermi/12345ABC/water_heater/mode",
  "modes": ["off", "eco", "performance"],
  "temperature_command_topic": "kermi/12345ABC/water_heater/target_temp/set",
  "temperature_state_topic": "kermi/12345ABC/water_heater/target_temp",
  "current_temperature_topic": "kermi/12345ABC/water_heater/current_temp",
  "min_temp": 40,
  "max_temp": 60,
  "temperature_unit": "C",
  "availability_topic": "kermi/12345ABC/availability",
  "device": {
    "identifiers": ["kermi_12345abc"]
  }
}
```

**Topic**: `homeassistant/water_heater/kermi_12345abc/dhw/config`

---

## Switch Entity (One-Time Heating)

```json
{
  "name": "DHW One-Time Heating",
  "unique_id": "kermi_12345abc_dhw_once",
  "command_topic": "kermi/12345ABC/switches/dhw_once/set",
  "state_topic": "kermi/12345ABC/switches/dhw_once",
  "payload_on": "ON",
  "payload_off": "OFF",
  "availability_topic": "kermi/12345ABC/availability",
  "icon": "mdi:water-boiler",
  "device": {
    "identifiers": ["kermi_12345abc"]
  }
}
```

---

## Binary Sensor Entity (Status)

```json
{
  "name": "Heat Pump Running",
  "unique_id": "kermi_12345abc_running",
  "state_topic": "kermi/12345ABC/status/heat_pump_status",
  "value_template": "{{ 'ON' if value in ['HEATING', 'COOLING'] else 'OFF' }}",
  "payload_on": "ON",
  "payload_off": "OFF",
  "device_class": "running",
  "availability_topic": "kermi/12345ABC/availability",
  "device": {
    "identifiers": ["kermi_12345abc"]
  }
}
```

---

## Device Registry Linking

All entities MUST include identical `device.identifiers` to link them to the same device in HA's device registry.

**Device Info Structure**:
```json
{
  "identifiers": ["kermi_12345abc"],    // Unique device ID
  "name": "Kermi Heat Pump",            // Display name in HA
  "manufacturer": "Kermi",              // Manufacturer
  "model": "x-center",                  // Model name
  "sw_version": "1.0.0",                // Integration version (optional)
  "serial_number": "12345ABC",          // Serial if available (optional)
  "configuration_url": "http://192.168.1.100"  // Link to device web UI (optional)
}
```

Only the first discovery message needs complete device info. Subsequent messages can use minimal:
```json
{
  "device": {
    "identifiers": ["kermi_12345abc"]
  }
}
```

---

## Discovery Message Lifecycle

### On Integration Startup

```
1. Connect to MQTT broker
2. For each entity to discover:
   - Generate discovery payload
   - Publish to discovery topic with retain=true
3. Publish availability=online
4. Start publishing state to state_topics
```

### On Integration Shutdown

```
1. Publish availability=offline (with retain=true)
2. Optionally: Remove discovery (publish empty payload to config topics)
   - This removes entities from HA
   - Only do if user requests "clean uninstall"
```

### On Home Assistant Restart

- HA reads retained discovery messages from MQTT
- Entities automatically recreated
- HA subscribes to state topics
- Integration continues publishing (no change needed)

---

## Entity Availability

All entities share a single availability topic per device:
```json
"availability_topic": "kermi/12345ABC/availability"
```

When device goes offline:
- Publish `"offline"` to availability topic
- All entities in HA show as "Unavailable"

When device comes online:
- Publish `"online"` to availability topic
- All entities in HA become available again

---

## Implementation Checklist

- [ ] Generate sensor entities for all `get_*` methods
- [ ] Generate number entities for `set_*` methods with numeric parameters
- [ ] Generate switch entities for `set_*` methods with boolean/enum parameters
- [ ] Generate climate entity if temperature + mode control available
- [ ] Generate water_heater entity if DHW control available
- [ ] Use consistent device identifiers across all entities
- [ ] Publish all discovery with retain=true
- [ ] Test HA restart scenario (entities persist)
- [ ] Test availability toggle (entities show unavailable)
- [ ] Test multi-instance (no ID conflicts)
