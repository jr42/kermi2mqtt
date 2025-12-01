# MQTT Topic Specification

**Feature**: 001-modbus-mqtt
**Date**: 2025-11-25
**Purpose**: Define MQTT topic structure for Kermi heat pump integration

---

## Topic Hierarchy

```
kermi/{device_id}/
├── availability                                    # Device online/offline
├── sensors/
│   ├── outdoor_temp                               # Outdoor temperature (°C)
│   ├── supply_temp                                # Supply temperature (°C)
│   ├── cop                                        # Coefficient of Performance
│   ├── power_thermal                              # Thermal power (kW)
│   └── power_electrical                           # Electrical power (kW)
├── status/
│   └── heat_pump_status                           # Operating status (enum)
├── water_heater/
│   ├── current_temp                               # Current DHW temperature
│   ├── target_temp                                # Target DHW setpoint
│   └── target_temp/set                            # Command topic for setpoint
└── controls/
    ├── pv_modulation                              # PV modulation power (W)
    └── pv_modulation/set                          # Command topic

homeassistant/{component}/{device_id}/{object_id}/
└── config                                         # HA discovery (retained)
```

---

## Topic Naming Conventions

### device_id Format

- **If serial number available**: Use serial (e.g., `kermi_12345ABC`)
- **If serial unavailable**: Use configured name (e.g., `kermi_main`)
- **Always**: Lowercase, underscores for spaces, alphanumeric only

### State Topics (Read-Only)

Format: `kermi/{device_id}/{category}/{parameter}`

**Examples**:
```
kermi/12345ABC/sensors/outdoor_temp
kermi/12345ABC/status/heat_pump_status
kermi/12345ABC/water_heater/current_temp
```

**Payload**: JSON value (number, string, or object)
```json
5.2                        // Temperature
"HEATING"                  // Status enum
{"value": 5.2, "unit": "°C"}  // Structured (if needed)
```

**Retain**: `false` (sensor values change frequently)

### Command Topics (Writable)

Format: `kermi/{device_id}/{category}/{parameter}/set`

**Examples**:
```
kermi/12345ABC/water_heater/target_temp/set
kermi/12345ABC/controls/pv_modulation/set
```

**Payload**: JSON value matching expected type
```json
50.0        // Set DHW to 50°C
2000        // Set PV modulation to 2000W
```

**Response**: Updated value published to state topic (without `/set`)

### Availability Topic

Format: `kermi/{device_id}/availability`

**Payload**: `"online"` or `"offline"`

**Retain**: `true` (so subscribers know state immediately)

**When Published**:
- `"online"`: On successful connection + first successful poll
- `"offline"`: On disconnection, poll failure, or service shutdown

---

## Message Formats

### Sensor Values

```json
// Temperature
{
  "topic": "kermi/12345ABC/sensors/outdoor_temp",
  "payload": 5.2,
  "qos": 0,
  "retain": false
}

// Power
{
  "topic": "kermi/12345ABC/sensors/power_thermal",
  "payload": 8.5,
  "qos": 0,
  "retain": false
}

// Coefficient of Performance
{
  "topic": "kermi/12345ABC/sensors/cop",
  "payload": 4.2,
  "qos": 0,
  "retain": false
}
```

### Status Values

```json
// Enum status
{
  "topic": "kermi/12345ABC/status/heat_pump_status",
  "payload": "HEATING",
  "qos": 0,
  "retain": false
}

// Possible values: "OFF", "HEATING", "COOLING", "STANDBY", "ERROR", etc.
```

### Control Commands

```json
// Set DHW temperature
{
  "topic": "kermi/12345ABC/water_heater/target_temp/set",
  "payload": 50.0,
  "qos": 1,
  "retain": false
}

// Set PV modulation
{
  "topic": "kermi/12345ABC/controls/pv_modulation/set",
  "payload": 2000,
  "qos": 1,
  "retain": false
}
```

### Availability

```json
{
  "topic": "kermi/12345ABC/availability",
  "payload": "online",
  "qos": 1,
  "retain": true
}
```

---

## Quality of Service (QoS)

| Topic Type | QoS | Rationale |
|------------|-----|-----------|
| Sensor state | 0 | Fire-and-forget, values updated frequently |
| Status state | 0 | Fire-and-forget, polled regularly |
| Commands (/set) | 1 | At-least-once delivery critical for control |
| Availability | 1 | Must be delivered, retained for late subscribers |
| HA Discovery | 1 | Must be delivered, retained for HA restart |

---

## Error Handling

### Validation Errors

When a command fails validation:

```json
// Error published to {command_topic}/error
{
  "topic": "kermi/12345ABC/water_heater/target_temp/set/error",
  "payload": {
    "error": "Value 70.0 outside safe range [40.0, 60.0]",
    "timestamp": "2025-11-25T10:30:00Z",
    "rejected_value": 70.0
  },
  "qos": 0,
  "retain": false
}
```

### Write Failures

When a write to the heat pump fails:

```json
{
  "topic": "kermi/12345ABC/water_heater/target_temp/set/error",
  "payload": {
    "error": "Modbus write failed: Connection timeout",
    "timestamp": "2025-11-25T10:30:00Z",
    "command_value": 50.0
  },
  "qos": 0,
  "retain": false
}
```

---

## Multi-Instance Support

Multiple heat pumps on same MQTT broker:

```
kermi/12345ABC/...        # Heat pump 1 (serial 12345ABC)
kermi/67890DEF/...        # Heat pump 2 (serial 67890DEF)
kermi/main/...            # Heat pump 3 (configured name "main")
kermi/garage/...          # Heat pump 4 (configured name "garage")
```

Each instance has independent:
- Device ID in all topics
- Availability status
- Home Assistant device in registry

---

## Home Assistant Discovery Topics

Format: `homeassistant/{component}/{device_id}/{object_id}/config`

**Examples**:
```
homeassistant/sensor/kermi_12345abc/outdoor_temp/config
homeassistant/sensor/kermi_12345abc/cop/config
homeassistant/number/kermi_12345abc/water_heater_target/config
homeassistant/climate/kermi_12345abc/main/config
```

**Payload**: Complete HA discovery JSON (see ha-discovery.md)

**Retain**: `true` (required for HA to rediscover after restart)

---

## Security Considerations

### Authentication

- MQTT broker SHOULD require username/password
- Integration MUST support MQTT authentication in config
- Credentials MUST NOT be logged

### Topic Access Control (Optional)

If using MQTT ACLs:
```
# Read-only user (e.g., dashboard)
user:dashboard
  topic read kermi/+/sensors/#
  topic read kermi/+/status/#
  topic read kermi/+/availability

# Control user (e.g., Home Assistant)
user:homeassistant
  topic read kermi/#
  topic write kermi/+/+/+/set
```

### TLS

- MQTT broker SHOULD use TLS (port 8883)
- Integration MUST support TLS configuration
- Certificate validation SHOULD be enabled (but allow disable for self-signed certs in home environments)

---

## Example Session

```
# Service starts
→ kermi/12345ABC/availability: "online" (retained)
→ homeassistant/sensor/kermi_12345abc/outdoor_temp/config: {...} (retained)
→ homeassistant/sensor/kermi_12345abc/cop/config: {...} (retained)
... (more discovery messages)

# First poll
→ kermi/12345ABC/sensors/outdoor_temp: 5.2
→ kermi/12345ABC/sensors/cop: 4.2
→ kermi/12345ABC/status/heat_pump_status: "HEATING"
... (all sensor values)

# User sets DHW temperature via Home Assistant
← kermi/12345ABC/water_heater/target_temp/set: 50.0
[Integration validates, writes to heat pump, reads back]
→ kermi/12345ABC/water_heater/target_temp: 50.0

# Connection lost
→ kermi/12345ABC/availability: "offline" (retained)

# Connection restored
→ kermi/12345ABC/availability: "online" (retained)
→ kermi/12345ABC/sensors/outdoor_temp: 4.8
... (resume polling)
```
