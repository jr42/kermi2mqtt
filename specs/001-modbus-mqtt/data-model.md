# Data Model: Modbus-to-MQTT Integration

**Feature**: 001-modbus-mqtt
**Date**: 2025-11-25
**Purpose**: Define entity models for MQTT bridge layer (py-kermi-xcenter handles Modbus)

---

## Overview

The `py-kermi-xcenter` library already provides:
- ✅ Modbus register mapping
- ✅ Data type conversion
- ✅ Device abstractions (HeatPump, StorageSystem, UniversalModule)
- ✅ Async I/O
- ✅ Connection management

**Our data model focuses on:**
- MQTT topic mapping
- Home Assistant discovery payloads
- Safety validation (additional layer on top of library)
- Multi-instance support (device identification)

---

## Core Entities

### DeviceAttribute

Maps a py-kermi-xcenter device method to an MQTT topic and HA entity.

**Attributes**:
- `device_class`: str - Which py-kermi-xcenter class ("HeatPump", "StorageSystem", "UniversalModule")
- `method_name`: str - Method to call (e.g., "get_outdoor_temperature", "set_hot_water_setpoint_constant")
- `friendly_name`: str - Human-readable name for MQTT/HA (e.g., "Outdoor Temperature")
- `mqtt_topic_suffix`: str - Topic suffix after device ID (e.g., "sensors/outdoor_temp")
- `writable`: bool - Whether this has a setter method
- `ha_component`: str - HA entity type ("sensor", "climate", "switch", "water_heater")
- `ha_config`: dict - HA-specific config (unit, device_class, state_class, etc.)
- `poll_interval`: float | None - Override default poll interval for this attribute (None = use default)

**Example** (read-only sensor):
```python
DeviceAttribute(
    device_class="HeatPump",
    method_name="get_outdoor_temperature",
    friendly_name="Outdoor Temperature",
    mqtt_topic_suffix="sensors/outdoor_temp",
    writable=False,
    ha_component="sensor",
    ha_config={
        "unit_of_measurement": "°C",
        "device_class": "temperature",
        "state_class": "measurement"
    },
    poll_interval=None  # Use default 30s
)
```

**Example** (writable control):
```python
DeviceAttribute(
    device_class="HeatPump",
    method_name="set_hot_water_setpoint_constant",
    friendly_name="Hot Water Setpoint",
    mqtt_topic_suffix="water_heater/target_temp",
    writable=True,
    ha_component="number",  # Or part of water_heater entity
    ha_config={
        "unit_of_measurement": "°C",
        "min": 40.0,
        "max": 60.0,
        "step": 0.5
    },
    poll_interval=None
)
```

---

### KermiDevice

Wrapper around py-kermi-xcenter device instances with MQTT/HA metadata.

**Attributes**:
- `device_id`: str - Unique identifier (serial number or configured name)
- `device_type`: str - Type from library ("heat_pump", "storage_system", "universal_module")
- `xcenter_instance`: HeatPump | StorageSystem | UniversalModule - Actual library device object
- `attributes`: list[DeviceAttribute] - All mapped attributes for this device
- `mqtt_base_topic`: str - Base MQTT topic (e.g., "kermi/12345ABC")
- `available`: bool - Current connection status
- `last_poll`: datetime | None - When last successful poll completed

**Methods**:
```python
async def poll_all(self) -> dict[str, Any]:
    """Poll all get_* methods and return {method_name: value}"""
    results = {}
    for attr in self.attributes:
        if not attr.writable:
            method = getattr(self.xcenter_instance, attr.method_name)
            results[attr.method_name] = await method()
    return results

async def write_attribute(self, method_name: str, value: Any):
    """Call a set_* method with validation"""
    attr = self.find_attribute(method_name)
    if not attr.writable:
        raise ValueError(f"{method_name} is read-only")

    # Validate value (if ha_config has min/max/etc.)
    self.validate_value(attr, value)

    # Call library's setter
    method = getattr(self.xcenter_instance, method_name)
    await method(value)
```

---

### HADiscoveryMessage

Home Assistant MQTT discovery payload for a single entity.

**Attributes**:
- `device_attribute`: DeviceAttribute - The attribute being discovered
- `device_id`: str - Device identifier (for linking entities)
- `config_topic`: str - Full discovery topic path
- `state_topic`: str - Where state is published
- `command_topic`: str | None - Where commands are received (if writable)
- `availability_topic`: str - Shared availability for device
- `device_info`: dict - HA device registry info
- `payload`: dict - Complete JSON payload for discovery

**Factory Method**:
```python
@classmethod
def from_device_attribute(
    cls,
    attr: DeviceAttribute,
    device: KermiDevice,
    availability_topic: str
) -> "HADiscoveryMessage":
    """Generate HA discovery message from device attribute"""

    device_id_clean = device.device_id.replace(" ", "_").lower()
    object_id = attr.mqtt_topic_suffix.replace("/", "_")

    config_topic = f"homeassistant/{attr.ha_component}/{device_id_clean}/{object_id}/config"
    state_topic = f"{device.mqtt_base_topic}/{attr.mqtt_topic_suffix}"
    command_topic = f"{state_topic}/set" if attr.writable else None

    payload = {
        "name": attr.friendly_name,
        "unique_id": f"{device_id_clean}_{object_id}",
        "state_topic": state_topic,
        "availability_topic": availability_topic,
        "device": {
            "identifiers": [device_id_clean],
            "name": f"Kermi {device.device_type.title()}",
            "manufacturer": "Kermi",
            "model": "x-center"
        },
        **attr.ha_config  # Merge in unit, device_class, etc.
    }

    if command_topic:
        payload["command_topic"] = command_topic

    return cls(
        device_attribute=attr,
        device_id=device.device_id,
        config_topic=config_topic,
        state_topic=state_topic,
        command_topic=command_topic,
        availability_topic=availability_topic,
        device_info=payload["device"],
        payload=payload
    )
```

---

### MQTTStateMessage

Published state value for an attribute.

**Attributes**:
- `topic`: str - Full MQTT topic
- `value`: Any - Current value (will be JSON-serialized)
- `timestamp`: datetime - When value was read
- `retain`: bool - Whether to retain this message

**Example**:
```python
MQTTStateMessage(
    topic="kermi/12345ABC/sensors/outdoor_temp",
    value=5.2,
    timestamp=datetime.now(),
    retain=False  # Sensor values don't need retention
)
```

---

### SafetyValidator

Additional validation layer on top of py-kermi-xcenter's setters.

**Attributes**:
- `attribute_name`: str - Which DeviceAttribute this applies to
- `validation_rules`: list[Callable[[Any], tuple[bool, str]]] - Validation functions
- `block_reason`: str | None - If blocked entirely, why?

**Methods**:
```python
def validate(self, value: Any) -> tuple[bool, str]:
    """
    Validate a value before passing to library setter.
    Returns (is_valid, error_message)
    """
    if self.block_reason:
        return False, self.block_reason

    for rule in self.validation_rules:
        is_valid, error = rule(value)
        if not is_valid:
            return False, error

    return True, "OK"
```

**Built-in Validators**:
```python
def range_validator(min_val: float, max_val: float):
    def validate(value: Any) -> tuple[bool, str]:
        if not (min_val <= value <= max_val):
            return False, f"Value {value} outside range [{min_val}, {max_val}]"
        return True, "OK"
    return validate

def enum_validator(allowed_values: list[Any]):
    def validate(value: Any) -> tuple[bool, str]:
        if value not in allowed_values:
            return False, f"Value {value} not in {allowed_values}"
        return True, "OK"
    return validate
```

**Example Usage**:
```python
SafetyValidator(
    attribute_name="set_hot_water_setpoint_constant",
    validation_rules=[
        range_validator(40.0, 60.0)  # Prevent Legionella (<40) and scalding (>60)
    ],
    block_reason=None
)
```

---

## Data Flow

### Startup Sequence

```
1. Load configuration (MQTT broker, Modbus host, device ID)
2. Connect to MQTT broker
3. Create KermiModbusClient and device instances (HeatPump, etc.)
4. For each device:
   a. Create KermiDevice wrapper
   b. Generate DeviceAttribute list (from method introspection or config)
   c. Create HADiscoveryMessage for each attribute
   d. Publish discovery messages to MQTT (retained)
5. Publish device availability=online
6. Start polling loop
```

### Polling Loop

```
async def poll_and_publish(device: KermiDevice, mqtt_client):
    while True:
        try:
            # Poll all read methods
            values = await device.poll_all()

            # Publish each to MQTT
            for attr in device.attributes:
                if not attr.writable and attr.method_name in values:
                    topic = f"{device.mqtt_base_topic}/{attr.mqtt_topic_suffix}"
                    value = values[attr.method_name]
                    await mqtt_client.publish(topic, json.dumps(value))

            # Mark device available
            if not device.available:
                device.available = True
                await mqtt_client.publish(f"{device.mqtt_base_topic}/availability", "online")

        except Exception as e:
            logger.error(f"Poll failed: {e}")
            device.available = False
            await mqtt_client.publish(f"{device.mqtt_base_topic}/availability", "offline")
            await asyncio.sleep(backoff_delay)
        else:
            await asyncio.sleep(device.poll_interval)
```

### Command Handling

```
async def on_mqtt_command(topic: str, payload: str):
    # Parse topic to find device and attribute
    # Example: "kermi/12345ABC/water_heater/target_temp/set" → device=12345ABC, attr=set_hot_water_setpoint_constant

    device = find_device_by_id(device_id)
    attr = find_attribute_by_topic(topic)

    # Validate
    validator = get_safety_validator(attr.method_name)
    is_valid, error = validator.validate(payload)
    if not is_valid:
        logger.warning(f"Validation failed: {error}")
        await mqtt_client.publish(f"{topic}/error", error)
        return

    # Execute
    try:
        await device.write_attribute(attr.method_name, payload)

        # Read back and publish confirmation
        getter = attr.method_name.replace("set_", "get_")
        if hasattr(device.xcenter_instance, getter):
            value = await getattr(device.xcenter_instance, getter)()
            await mqtt_client.publish(topic.replace("/set", ""), json.dumps(value))
    except Exception as e:
        logger.error(f"Write failed: {e}")
        await mqtt_client.publish(f"{topic}/error", str(e))
```

---

## Pydantic Models (Implementation Reference)

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any, Callable

class DeviceAttribute(BaseModel):
    device_class: str
    method_name: str
    friendly_name: str
    mqtt_topic_suffix: str
    writable: bool = False
    ha_component: str
    ha_config: dict[str, Any] = Field(default_factory=dict)
    poll_interval: float | None = None

class KermiDevice(BaseModel):
    device_id: str
    device_type: str
    xcenter_instance: Any  # HeatPump | StorageSystem | UniversalModule
    attributes: list[DeviceAttribute]
    mqtt_base_topic: str
    available: bool = True
    last_poll: datetime | None = None

    class Config:
        arbitrary_types_allowed = True  # For xcenter_instance

class HADiscoveryMessage(BaseModel):
    device_attribute: DeviceAttribute
    device_id: str
    config_topic: str
    state_topic: str
    command_topic: str | None
    availability_topic: str
    device_info: dict[str, Any]
    payload: dict[str, Any]

class MQTTStateMessage(BaseModel):
    topic: str
    value: Any
    timestamp: datetime
    retain: bool = False

class SafetyValidator(BaseModel):
    attribute_name: str
    validation_rules: list[Callable[[Any], tuple[bool, str]]]
    block_reason: str | None = None

    class Config:
        arbitrary_types_allowed = True  # For Callable
```

---

## Attribute Registry (Configuration)

Instead of hardcoding register mappings, we define attribute mappings:

```yaml
# config/attributes.yaml
heat_pump:
  sensors:
    - method: get_outdoor_temperature
      name: Outdoor Temperature
      topic_suffix: sensors/outdoor_temp
      ha_component: sensor
      ha_config:
        unit_of_measurement: "°C"
        device_class: temperature
        state_class: measurement

    - method: get_cop_total
      name: Coefficient of Performance
      topic_suffix: sensors/cop
      ha_component: sensor
      ha_config:
        device_class: power_factor
        state_class: measurement

  controls:
    - method: set_hot_water_setpoint_constant
      name: Hot Water Setpoint
      topic_suffix: water_heater/target_temp
      writable: true
      ha_component: number
      ha_config:
        unit_of_measurement: "°C"
        min: 40
        max: 60
        step: 0.5
      safety:
        validation: range
        params: [40, 60]
```

This approach:
- Leverages py-kermi-xcenter's abstractions
- Focuses on MQTT/HA mapping (our responsibility)
- Avoids duplicating register knowledge
- Keeps safety validation explicit and auditable
