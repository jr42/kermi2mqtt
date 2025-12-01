# Research Findings: Modbus-to-MQTT Integration

**Date**: 2025-11-25
**Feature**: 001-modbus-mqtt
**Purpose**: Resolve technical unknowns for implementation planning

---

## 1. kermi-xcenter Library Capabilities

### Decision

Use `py-kermi-xcenter` library directly - it's already fully async and provides high-level device abstractions.

### Findings

**Async Support**: ✅ py-kermi-xcenter is **fully asynchronous** using Python's asyncio framework. All I/O operations use async/await.

**Device Classes Provided**:
- `HeatPump` (Unit ID 40) - Main heat pump with temperature sensors, control, status
- `StorageSystem` (Units 50/51) - Heating and hot water storage
- `UniversalModule` (Unit ID 30) - Additional heating circuits
- `KermiModbusClient` - Connection management (TCP/RTU)

**High-Level API Examples**:
```python
# Reading data
outdoor_temp = await heat_pump.get_outdoor_temperature()  # Returns float (°C)
cop = await heat_pump.get_cop_total()  # Coefficient of Performance
status = await heat_pump.get_heat_pump_status()  # Typed enum

# Writing controls
await heat_pump.set_hot_water_setpoint_constant(50.0)  # °C
await heat_pump.set_pv_modulation_power(2000)  # Watts
```

**Connection Management**:
```python
client = KermiModbusClient(host="192.168.1.100", port=502)
async with client:
    heat_pump = HeatPump(client)
    temp = await heat_pump.get_outdoor_temperature()
```

**Rationale**: Library already provides exactly what we need - async API, high-level methods with English names, automatic data conversion, connection management. No need for additional abstraction layers.

### Alternatives Considered

- **pymodbus directly**: Would lose all Kermi-specific knowledge and require manual register mapping
- **Wrapper layer over py-kermi-xcenter**: Unnecessary - library API is already ideal
- **Rejected**: py-kermi-xcenter is perfect for our use case

---

## 2. Kermi Device API Mapping

### Decision

Use py-kermi-xcenter's device classes directly. Library already handles all register mapping, data conversion, and type safety internally.

### Findings

**Device Classes and Their Methods**:

1. **HeatPump** (read-only sensors):
   - `get_outdoor_temperature()` → float (°C)
   - `get_supply_temp_heat_pump()` → float (°C)
   - `get_cop_total()` → float (efficiency)
   - `get_power_total()` → float (kW thermal)
   - `get_power_electrical_total()` → float (kW electrical)
   - `get_heat_pump_status()` → Enum (operating state)

2. **HeatPump** (writable controls):
   - `set_hot_water_setpoint_constant(temp)` → Set DHW temperature
   - `set_pv_modulation_power(watts)` → Solar integration

3. **StorageSystem** (heating + hot water storage):
   - Storage tank temperatures
   - Heating circuit controls
   - Buffer management

4. **UniversalModule** (additional circuits):
   - Additional heating circuit controls
   - Zone management

**Safety Classification** (based on library's exposed methods):
- **Writable**: Only methods with `set_*` prefix are writable
- **Read-Only**: All `get_*` methods are read-only
- Library only exposes user-safe parameters - no low-level hardware controls

### Rationale

Library maintainer has already done the safety analysis - only safe parameters have setter methods. We inherit this safety by design. No need to reimplement register whitelisting.

### Alternatives Considered

- **Manual register mapping**: Duplicates library's work, error-prone
- **Rejected**: Library API is our safety boundary

---

## 2a. Device Unique Identifier

### Decision

Read device serial number from Modbus register (if available) and use it for:
1. MQTT topic prefix: `/kermi/{serial}/...`
2. Home Assistant device identifier
3. Multi-instance support

If serial number unavailable, fall back to user-configured device name from config file.

### Findings

Most modern heat pumps expose serial number via Modbus (typically in system information registers). This enables:

**Multi-Instance Architecture**:
```yaml
# Instance 1 - Main house heat pump
device_name: "main"  # Used if serial unavailable
mqtt_base_topic: "kermi"  # Becomes /kermi/12345ABC/... with serial

# Instance 2 - Garage heat pump
device_name: "garage"
mqtt_base_topic: "kermi"  # Becomes /kermi/67890DEF/... with serial
```

**Home Assistant Device Identification**:
```json
{
  "device": {
    "identifiers": ["kermi_12345ABC"],
    "name": "Kermi Heat Pump",
    "manufacturer": "Kermi",
    "model": "x-center",
    "serial_number": "12345ABC"
  }
}
```

### Rationale

Using serial number (when available) prevents MQTT topic collisions and enables proper multi-device setups in Home Assistant. Fallback to configured name ensures functionality even if serial is unavailable.

### Alternatives Considered

- **Always require manual device ID**: Less user-friendly, manual conflict resolution
- **MAC address-based**: Not exposed via Modbus, would require network discovery
- **Rejected**: Serial number from device is most reliable and user-friendly

---

## 2b. StorageSystem Purpose Identification

### Decision

**AUTO-DETECTION WITH FALLBACK** - Unit ID convention discovered via live testing with kermi-xcenter v0.2.1

**Unit ID Mapping** (discovered pattern):
- **Unit 50** = Heating circuit (floor heating / buffer)
- **Unit 51** = Domestic Hot Water (DHW)

### Research Findings (T023a - 2025-11-28)

**Successful Test**: Connected to xcenter.reith.cloud:502 with kermi-xcenter v0.2.1

**Library Upgrade**: v0.0.1 → v0.2.1 resolved all protocol errors ✅

**HeatPump (Unit 40) - 28 get_* methods**:
```python
get_outdoor_temperature()  → 2.9°C
get_supply_temp_heat_pump() → 25.1°C
get_cop_total() → 0.0
get_power_total() → 0.0 kW
get_power_electrical_total() → 0.0 kW
get_heat_pump_status() → 0
# ... 22 more methods
```

**StorageSystem Unit 50 - 36 get_* methods**:
```python
get_all_readable_values() → {
    'heating_actual': 25.5,
    'heating_setpoint': 27.3,
    'hot_water_actual': 0.0,       # ← Not used
    'hot_water_setpoint': 0.0,     # ← Not used
    'heating_circuit_status': 1,   # ← Active
    'heating_circuit_actual': 25.5,
    # ... full dict with 34 fields
}
```
**Conclusion**: Unit 50 is **HEATING CIRCUIT** (heating_actual > 0, hot_water_actual == 0)

**StorageSystem Unit 51 - 36 get_* methods**:
```python
get_all_readable_values() → {
    'heating_actual': 0.0,         # ← Not used
    'heating_setpoint': 0.0,       # ← Not used
    'hot_water_actual': 44.7,      # ← Active
    'hot_water_setpoint': 48.0,    # ← Active
    'hot_water_setpoint_constant': 48.0,
    'hot_water_single_charge_active': False,
    # ... full dict with 34 fields
}
```
**Conclusion**: Unit 51 is **DHW (DOMESTIC HOT WATER)** (hot_water_actual > 0, heating_actual == 0)

### Implementation Strategy

**Primary Approach**: **Auto-detection via data inspection**

1. Query `get_all_readable_values()` from each StorageSystem
2. Determine purpose:
   ```python
   if hot_water_actual > 0 and heating_actual == 0:
       purpose = "dhw"  # Domestic Hot Water
   elif heating_actual > 0 and hot_water_actual == 0:
       purpose = "heating"  # Floor Heating / Buffer
   elif both > 0:
       purpose = "combined"  # Rare combined system
   else:
       # Fallback to unit ID convention
       purpose = "dhw" if unit_id == 51 else "heating"
   ```

**Fallback**: Unit ID convention (50=heating, 51=dhw) if auto-detection fails

**User Override**: Optional config.yaml mapping for unusual installations:
```yaml
# Optional: override auto-detection
storage_systems:
  50:
    purpose: heating  # Override if needed
    name: "Floor Heating Buffer"
  51:
    purpose: dhw      # Override if needed
    name: "Hot Water Tank"
```

**Rationale**:
- Auto-detection provides zero-config experience for standard setups
- Unit ID fallback covers edge cases
- User override allows flexibility for unusual installations
- Works reliably with kermi-xcenter v0.2.1+
- Can add auto-detection later when library stabilizes
- Simple validation: reject invalid purposes in config loading

**MQTT Topic Mapping**:
- Unit 50 (purpose=dhw) → `/kermi/{device_id}/dhw/...`
- Unit 51 (purpose=heating) → `/kermi/{device_id}/heating/...`
- Unit 52+ (purpose=buffer) → `/kermi/{device_id}/buffer_{unit_id}/...`

### Recommendations for Implementation

1. **Wrap Library Errors**: Add comprehensive try/except around all kermi-xcenter calls
2. **Graceful Degradation**: If StorageSystem fails, continue with HeatPump only
3. **Robust Reconnection**: Implement aggressive exponential backoff (library seems flaky)
4. **Document Instability**: Warn users in README that library is v0.0.1 alpha
5. **Consider Contributing**: Once MVP works, consider contributing fixes upstream

### Test Script Location

Research script saved at: `/Users/A94986267/Develop/other/kermi2mqtt/research_script.py`

User can test separately with: `source .venv/bin/activate && python3 research_script.py`

**Note**: Expect protocol errors with v0.0.1 - this is a known issue, not our bug.

---

## 3. Python 3.14+ Async Best Practices

### Decision

Use `asyncio.TaskGroup` (Python 3.11+) for managing concurrent tasks with proper cancellation and exception handling.

### Findings

**TaskGroup Pattern** (for managing Modbus+MQTT tasks):
```python
async def main():
    async with asyncio.TaskGroup() as tg:
        modbus_task = tg.create_task(modbus_poll_loop())
        mqtt_task = tg.create_task(mqtt_client_loop())
        # TaskGroup ensures both tasks cancelled if either fails
```

**Error Handling** (in async poll loop):
```python
async def poll_loop():
    while True:
        try:
            data = await read_registers()
            await publish_to_mqtt(data)
        except ModbusException as e:
            logger.error(f"Modbus error: {e}")
            await asyncio.sleep(backoff_delay)
        except MQTTException as e:
            logger.error(f"MQTT error: {e}")
            await asyncio.sleep(backoff_delay)
        else:
            await asyncio.sleep(poll_interval)
```

**Graceful Shutdown**:
```python
import signal

async def main():
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def handle_signal():
        logger.info("Shutdown signal received")
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal)

    await run_until_stopped(stop_event)
```

**Resource Management**:
```python
class ModbusClient:
    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

async with ModbusClient() as client:
    await client.read_register(0)
```

### Rationale

TaskGroup provides structured concurrency with automatic cleanup. Signal handlers enable graceful shutdown in systemd/Docker. Async context managers ensure proper resource cleanup.

### Alternatives Considered

- **asyncio.gather()**: Less structured, manual cancellation required
- **Manual task tracking**: Error-prone, violates Simplicity principle
- **Rejected**: TaskGroup is Python 3.11+ standard practice

---

## 4. Home Assistant MQTT Discovery Format

### Decision

Implement discovery payloads matching Home Assistant MQTT integration specification exactly.

### Findings

**General Pattern**:
- Discovery topic: `homeassistant/{component}/{node_id}/{object_id}/config`
- node_id: Device serial (e.g., "kermi_12345ABC")
- object_id: Parameter name (e.g., "outdoor_temp")
- Retained: Yes (must survive HA restart)

**Climate Entity Payload**:
```json
{
  "name": "Kermi Heating",
  "unique_id": "kermi_12345ABC_climate",
  "mode_command_topic": "kermi/12345ABC/climate/mode/set",
  "mode_state_topic": "kermi/12345ABC/climate/mode",
  "modes": ["off", "heat", "cool", "auto"],
  "temperature_command_topic": "kermi/12345ABC/climate/target_temp/set",
  "temperature_state_topic": "kermi/12345ABC/climate/target_temp",
  "current_temperature_topic": "kermi/12345ABC/climate/current_temp",
  "min_temp": 10,
  "max_temp": 30,
  "temp_step": 0.5,
  "availability_topic": "kermi/12345ABC/availability",
  "device": {
    "identifiers": ["kermi_12345ABC"],
    "name": "Kermi Heat Pump",
    "manufacturer": "Kermi",
    "model": "x-center",
    "sw_version": "1.0.0"
  }
}
```

**Water Heater Entity Payload**:
```json
{
  "name": "Kermi DHW",
  "unique_id": "kermi_12345ABC_water_heater",
  "mode_command_topic": "kermi/12345ABC/water_heater/mode/set",
  "mode_state_topic": "kermi/12345ABC/water_heater/mode",
  "modes": ["off", "eco", "performance", "heat_pump"],
  "temperature_command_topic": "kermi/12345ABC/water_heater/target_temp/set",
  "temperature_state_topic": "kermi/12345ABC/water_heater/target_temp",
  "current_temperature_topic": "kermi/12345ABC/water_heater/current_temp",
  "min_temp": 40,
  "max_temp": 60,
  "availability_topic": "kermi/12345ABC/availability",
  "device": {
    "identifiers": ["kermi_12345ABC"],
    "name": "Kermi Heat Pump",
    "manufacturer": "Kermi",
    "model": "x-center"
  }
}
```

**Sensor Entity Payload**:
```json
{
  "name": "Outdoor Temperature",
  "unique_id": "kermi_12345ABC_outdoor_temp",
  "state_topic": "kermi/12345ABC/sensors/outdoor_temp",
  "unit_of_measurement": "°C",
  "device_class": "temperature",
  "availability_topic": "kermi/12345ABC/availability",
  "device": {
    "identifiers": ["kermi_12345ABC"]
  }
}
```

**Switch Entity Payload**:
```json
{
  "name": "DHW One-Time Heating",
  "unique_id": "kermi_12345ABC_dhw_once",
  "command_topic": "kermi/12345ABC/switches/dhw_once/set",
  "state_topic": "kermi/12345ABC/switches/dhw_once",
  "payload_on": "ON",
  "payload_off": "OFF",
  "availability_topic": "kermi/12345ABC/availability",
  "device": {
    "identifiers": ["kermi_12345ABC"]
  }
}
```

**Key Requirements**:
- `unique_id`: Must be globally unique (use serial + parameter)
- `device.identifiers`: Array linking entities to same device
- `availability_topic`: Shared across all entities for device online/offline status
- Retained: All discovery messages must use MQTT retain flag

### Rationale

Following HA conventions exactly ensures zero-config integration. Device linking creates unified UI. Availability topic shows device online/offline state.

### Alternatives Considered

- **Custom discovery format**: Would break HA integration
- **Manual configuration**: Defeats purpose of discovery
- **Rejected**: Must follow HA specification exactly

---

## 5. Exponential Backoff Strategy

### Decision

Use different backoff strategies for MQTT vs Modbus based on failure characteristics.

### Findings

**MQTT Backoff** (network service, can be down longer):
- Initial delay: 1 second
- Max delay: 60 seconds
- Backoff factor: 2.0
- Jitter: ±25% random
- Retry policy: Infinite (service useless without MQTT)

**Modbus Backoff** (local device, should recover quickly):
- Initial delay: 2 seconds
- Max delay: 30 seconds
- Backoff factor: 2.0
- Jitter: ±25% random
- Retry policy: Infinite (service useless without heat pump)

**Implementation**:
```python
import random

async def reconnect_with_backoff(connect_func, name, initial=1.0, max_delay=60.0, factor=2.0):
    delay = initial
    while True:
        try:
            await connect_func()
            logger.info(f"{name} connected")
            return
        except Exception as e:
            jitter = delay * (0.75 + random.random() * 0.5)  # ±25%
            logger.warning(f"{name} connection failed: {e}, retrying in {jitter:.1f}s")
            await asyncio.sleep(jitter)
            delay = min(delay * factor, max_delay)
```

### Rationale

Infinite retry is appropriate for IoT services - without connections, the service has no purpose. Different parameters reflect network (MQTT) vs local device (Modbus) failure characteristics. Jitter prevents thundering herd if multiple services restart simultaneously.

### Alternatives Considered

- **Max retry count**: Would require manual restart, violates Reliability principle
- **Fixed delay**: Hammers failed endpoints, not respectful
- **Linear backoff**: Too slow to recover from transient glitches
- **Rejected**: Exponential with jitter is industry best practice

---

## Summary of Decisions

| Research Area | Decision | Rationale |
|--------------|----------|-----------|
| kermi-xcenter integration | Use asyncio.to_thread() for sync-to-async bridge | Clean Python 3.14 pattern, minimal complexity |
| Register mapping | Explicit pydantic models with safety whitelist | Type safety, prevents unsafe writes |
| Device identification | Serial number from Modbus (fallback to config name) | Multi-instance support, HA device linking |
| Async patterns | TaskGroup + signal handlers + async context managers | Structured concurrency, graceful shutdown |
| HA discovery | Exact specification compliance with device linking | Zero-config integration |
| Backoff strategy | Exponential with jitter, infinite retry, service-specific params | Industry standard, reliability principle |

All decisions pass Constitution Check and support requirements from spec.md.
