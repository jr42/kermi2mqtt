# Safety Documentation

**Feature**: 001-modbus-mqtt
**Date**: 2025-11-25
**Purpose**: Document safety constraints and writable parameter boundaries

---

## Safety Philosophy

The `py-kermi-xcenter` library maintainer has already performed safety analysis - **only user-safe parameters have setter methods exposed**. Our integration inherits this safety by design.

**What py-kermi-xcenter Does NOT Expose**:
- ❌ Compressor speed control
- ❌ Refrigerant valve positions
- ❌ System pressure adjustments
- ❌ Low-level hardware parameters
- ❌ Firmware configuration

**What IS Exposed (User-Safe)**:
- ✅ Temperature setpoints
- ✅ Operating modes
- ✅ Hot water controls
- ✅ Solar/PV integration
- ✅ Heating circuit controls

---

## Writable Parameters

### Hot Water Setpoint

**Method**: `set_hot_water_setpoint_constant(temperature: float)`

**Safe Range**: 40.0°C to 60.0°C

**Rationale**:
- **Below 40°C**: Risk of Legionella bacteria growth in domestic hot water
- **Above 60°C**: Risk of scalding, increased energy consumption, equipment stress

**Validation**:
```python
if not (40.0 <= temperature <= 60.0):
    raise ValueError("DHW temperature must be 40-60°C")
```

---

### PV Modulation Power

**Method**: `set_pv_modulation_power(watts: int)`

**Safe Range**: 0W to rated maximum (typically 3000-5000W depending on model)

**Rationale**:
- Controls heat pump behavior based on available solar power
- Library enforces maximum based on heat pump capabilities
- Cannot damage equipment (heat pump will limit actual consumption)

**Validation**:
```python
if watts < 0:
    raise ValueError("PV power cannot be negative")
# Upper bound enforced by library based on device capabilities
```

---

## Read-Only Parameters (Diagnostic)

These provide system insight but **cannot be modified**:

### Temperatures
- Outdoor temperature
- Supply temperature
- Return temperature
- Hot water temperature
- Buffer temperatures

### Performance Metrics
- Coefficient of Performance (COP)
- Thermal power output
- Electrical power consumption
- Energy totals

### Status
- Operating mode (read-only view)
- Compressor status
- Pump status
- Error codes

**Why Read-Only**: Modifying these could damage hardware or void warranty. Heat pump firmware controls these based on physical sensors and safety logic.

---

## Safety Validation Layer

Our integration adds **additional validation** on top of the library:

### Range Validation

```python
class RangeValidator:
    def __init__(self, min_val: float, max_val: float, parameter_name: str):
        self.min_val = min_val
        self.max_val = max_val
        self.parameter_name = parameter_name

    def validate(self, value: float) -> tuple[bool, str]:
        if not (self.min_val <= value <= self.max_val):
            return False, (
                f"{self.parameter_name} value {value} outside safe range "
                f"[{self.min_val}, {self.max_val}]"
            )
        return True, "OK"

# Usage
dhw_validator = RangeValidator(40.0, 60.0, "DHW temperature")
is_valid, error = dhw_validator.validate(user_input)
```

### Rate Limiting

Prevent rapid repeated commands that could stress equipment:

```python
class RateLimiter:
    def __init__(self, min_interval_seconds: float = 60.0):
        self.min_interval = min_interval_seconds
        self.last_write = {}

    def can_write(self, parameter: str) -> tuple[bool, str]:
        now = time.time()
        last = self.last_write.get(parameter, 0)

        if now - last < self.min_interval:
            remaining = self.min_interval - (now - last)
            return False, f"Rate limit: wait {remaining:.0f}s before changing {parameter}"

        self.last_write[parameter] = now
        return True, "OK"
```

---

## Error Handling

### Invalid Commands

When MQTT command violates safety rules:

```
1. Log security event with rejected value
2. Publish error to MQTT `{command_topic}/error`
3. Do NOT write to heat pump
4. Return immediately
```

### Write Failures

When library raises exception during write:

```
1. Log exception with context
2. Publish error to MQTT
3. Do NOT retry automatically (could indicate hardware issue)
4. Continue monitoring (read operations)
```

---

## User Warnings

### Configuration File Comment

```yaml
# config.yaml

# WARNING: Only modify settings you understand!
# Incorrect setpoints can:
# - Waste energy (too high DHW temperature)
# - Create health risks (too low DHW temperature → Legionella)
# - Reduce equipment lifespan (frequent mode changes)
#
# When in doubt, use manufacturer's recommended settings.
```

### Log Messages

```
INFO: DHW setpoint changed from 45.0°C to 50.0°C via MQTT
WARNING: DHW setpoint change rejected: 70.0°C exceeds maximum (60.0°C)
ERROR: Failed to write DHW setpoint: Modbus timeout
```

---

## Safe Operation Guidelines

### For Users

1. **Start with defaults**: Don't change settings unless you understand them
2. **Small adjustments**: Change temperatures by 1-2°C increments
3. **Observe behavior**: Wait 30+ minutes to see effect of changes
4. **DHW temperature**: Keep between 50-55°C for balance of safety and efficiency
5. **Don't automate aggressively**: Avoid frequent setpoint changes

### For Developers

1. **Validate everything**: Never trust MQTT input
2. **Log all writes**: Audit trail for troubleshooting
3. **Rate limit**: Prevent command flooding
4. **Fail safe**: On error, stop writing (continue reading)
5. **Document boundaries**: Make safety ranges visible in HA UI (min/max attributes)

---

## Compliance with Constitution

This integration complies with **Safety (NON-NEGOTIABLE)** principle:

✅ **Low-level parameters NOT exposed**: py-kermi-xcenter doesn't expose dangerous registers
✅ **Only user-facing settings accessible**: Temperature setpoints, modes only
✅ **Write operations limited**: Only manufacturer-approved adjustments
✅ **Read-only diagnostic access**: All sensor data readable but not writable
✅ **Documentation clear**: This file + code comments indicate writable vs read-only

---

## Incident Response

### If User Reports Equipment Damage

1. **Collect logs**: Full log output showing commands sent
2. **Check validation**: Did our validation pass or fail?
3. **Library behavior**: What did py-kermi-xcenter actually send to device?
4. **Timeline**: When did issue start vs when command sent?
5. **Report upstream**: If library passed invalid command, report to py-kermi-xcenter maintainer

### If Safety Violation Detected

1. **Immediate**: Log security event
2. **Block command**: Reject at validation layer
3. **Alert**: If enabled, send notification to admin
4. **Document**: Add to this file if new attack vector discovered

---

## Future Safety Enhancements

Potential additions (not required for v1.0):

- **Command whitelist**: Configuration option to disable specific setters entirely
- **Audit log**: Separate file tracking all writes with timestamps and sources
- **Confirmation mode**: Require two identical commands within time window
- **Hardware interlocks**: Read equipment error states before allowing writes
- **User permissions**: Different MQTT users with different write permissions
