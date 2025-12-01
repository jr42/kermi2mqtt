# Implementation Plan: Modbus-to-MQTT Integration for Kermi Heat Pumps

**Branch**: `001-modbus-mqtt` | **Date**: 2025-11-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-modbus-mqtt/spec.md`

## Summary

Build a Python-based integration that bridges Kermi heat pumps to MQTT for home automation. The service reads all Modbus datapoints from the heat pump and publishes them to MQTT topics organized by device type (interface_module, heatpump, water_heater, floor_heating). It supports bidirectional control for user-level settings while enforcing safety constraints to prevent hardware damage. Home Assistant auto-discovery provides zero-configuration integration. Technical approach leverages async/await for efficiency on resource-constrained hardware.

## Technical Context

**Language/Version**: Python 3.14+
**Primary Dependencies**: kermi-xcenter (Kermi Modbus interface), aiomqtt (async MQTT client), pydantic (configuration validation)
**Storage**: N/A (stateless service, all state in heat pump and MQTT broker)
**Testing**: pytest with pytest-asyncio for async tests, pytest-mock for mocking Modbus/MQTT
**Target Platform**: Linux (Raspberry Pi 3+, x86_64 servers), Docker container support
**Project Type**: Single project (async Python daemon/service)
**Performance Goals**: <50MB memory, <5% CPU on Raspberry Pi 3, <10s startup, <5s datapoint update latency
**Constraints**: Must run continuously 24/7, handle transient network failures, prevent unsafe parameter writes
**Scale/Scope**: Single heat pump per instance, 50-200 Modbus registers depending on configuration, ~100 MQTT topics

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Reliability (NON-NEGOTIABLE)

| Requirement | Implementation Strategy | Status |
|-------------|------------------------|--------|
| Handle network interruptions gracefully | Async reconnection logic with exponential backoff for both Modbus and MQTT | ✅ PASS |
| Polling cycles recover from transient failures | Try/except around poll loop, log errors, continue operation | ✅ PASS |
| MQTT reconnection with exponential backoff | aiomqtt provides built-in reconnection, configure max retries | ✅ PASS |
| Persist state across restarts | Stateless design - heat pump holds truth, MQTT retained messages for discovery | ✅ PASS |

### II. Simplicity

| Requirement | Implementation Strategy | Status |
|-------------|------------------------|--------|
| Favor direct solutions over abstractions | Direct async polling loop, no complex frameworks beyond asyncio | ✅ PASS |
| Minimize dependencies | Only 3 core deps: kermi-xcenter, aiomqtt, pydantic | ✅ PASS |
| Simple configuration with defaults | YAML/TOML config file with sensible defaults for polling interval, topics | ✅ PASS |
| Avoid premature optimization | Start with simple polling, optimize only if profiling shows issues | ✅ PASS |

### III. Efficiency

| Requirement | Implementation Strategy | Status |
|-------------|------------------------|--------|
| Memory <100MB RSS | Python async minimizes thread overhead, single event loop for all I/O | ✅ PASS |
| CPU <5% on RPi3 | Async I/O prevents CPU blocking, poll interval (30s default) spreads load | ✅ PASS |
| Optimize Modbus API calls | Batch register reads where possible, use kermi-xcenter efficiently | ✅ PASS |
| Startup <10s to first MQTT publish | Async connection tasks in parallel, publish immediately after first poll | ✅ PASS |

### IV. Safety (NON-NEGOTIABLE)

| Requirement | Implementation Strategy | Status |
|-------------|------------------------|--------|
| Block low-level parameter writes | Whitelist of writable registers based on Kermi docs, reject all others | ✅ PASS |
| Only expose user-facing settings | Map only safe registers to MQTT /set topics (temp, modes, schedules) | ✅ PASS |
| Limit to manufacturer-approved adjustments | Validate value ranges from Kermi spec before Modbus write | ✅ PASS |
| Read-only for diagnostic parameters | Publish diagnostic data to MQTT without /set topic | ✅ PASS |
| Document safe settings clearly | Include safety.md with explicit writable vs read-only register tables | ⚠️ REQUIRED |

**Overall Gate Status**: ✅ PASS (with requirement to create safety.md documentation)

## Project Structure

### Documentation (this feature)

```text
specs/001-modbus-mqtt/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Research findings (Phase 0)
├── data-model.md        # Entity models (Phase 1)
├── quickstart.md        # Setup guide (Phase 1)
├── safety.md            # Safety documentation (Phase 1)
├── contracts/           # MQTT topic contracts (Phase 1)
│   ├── mqtt-topics.md
│   └── ha-discovery.md
└── checklists/
    └── requirements.md  # Spec validation checklist
```

### Source Code (repository root)

```text
kermi2mqtt/
├── src/
│   └── kermi2mqtt/
│       ├── __init__.py
│       ├── __main__.py          # Entry point (python -m kermi2mqtt)
│       ├── config.py            # Configuration loading (pydantic models)
│       ├── modbus_client.py     # Kermi Modbus interface (wraps kermi-xcenter)
│       ├── mqtt_client.py       # MQTT interface (wraps aiomqtt)
│       ├── bridge.py            # Main coordination logic (poll loop, publish)
│       ├── ha_discovery.py      # Home Assistant MQTT discovery payloads
│       ├── safety.py            # Safety validation (writable register whitelist)
│       └── models/
│           ├── __init__.py
│           ├── register.py      # Modbus register definitions
│           ├── datapoint.py     # Datapoint (register + metadata)
│           └── device.py        # Device grouping (interface_module, etc.)
│
├── tests/
│   ├── unit/
│   │   ├── test_config.py
│   │   ├── test_safety.py
│   │   ├── test_ha_discovery.py
│   │   └── test_models.py
│   ├── integration/
│   │   ├── test_modbus_mqtt_flow.py
│   │   └── test_reconnection.py
│   └── fixtures/
│       ├── config_samples.yaml
│       └── mock_register_data.py
│
├── config.example.yaml          # Example configuration file
├── pyproject.toml               # Project metadata (PEP 621), dependencies
├── README.md                    # User-facing docs
├── Dockerfile                   # Container image
├── docker-compose.yaml          # Development/deployment compose file
│
└── .github/
    └── workflows/
        ├── test.yml             # Run pytest on PR/push
        ├── lint.yml             # ruff, mypy, black
        └── release.yml          # Build/publish Docker image + PyPI package
```

**Structure Decision**: Single Python project using modern packaging (PEP 621 via pyproject.toml). Source in `src/kermi2mqtt/` layout for proper editable installs. Async architecture with single event loop coordinating Modbus polling and MQTT publishing. Docker support for easy deployment on SBCs.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations - all constitution requirements met by proposed architecture.

---

## Phase 0: Research & Resolution

### Research Tasks

Based on Technical Context, the following research is needed:

1. **kermi-xcenter library capabilities**
   - Question: Does kermi-xcenter support async/await or only synchronous Modbus operations?
   - Why: If sync-only, need strategy to integrate with asyncio event loop (run_in_executor)

2. **Kermi Modbus register mapping**
   - Question: Complete list of registers, addresses, data types, and read/write permissions
   - Why: Core data model depends on accurate register definitions for safety validation

2a. **Device unique identifier**
   - Question: Does Kermi expose serial number or unique identifier via Modbus?
   - Why: Enables multi-instance support, unique MQTT topics, and proper HA device identification

3. **Python 3.14+ async best practices**
   - Question: Task groups, exception handling patterns, graceful shutdown for long-running services
   - Why: Ensure robust async architecture following modern Python idioms

4. **Home Assistant MQTT discovery format**
   - Question: Exact payload schemas for climate, water_heater, sensor, switch, binary_sensor entities
   - Why: Must match HA expectations for zero-config integration

5. **Exponential backoff strategy**
   - Question: Standard parameters (initial delay, max delay, backoff factor) for IoT reconnection
   - Why: Balance between fast recovery and not hammering failed endpoints

### Research Execution

_Research tasks will be dispatched to exploration agents. Findings consolidated in research.md._

**Output**: research.md with decisions, rationale, and alternatives for each question above

---

## Phase 1: Design & Contracts

**Prerequisites**: research.md complete with all decisions finalized

### Deliverables

1. **data-model.md**: Entity models and relationships
   - DeviceAttribute (kermi_xcenter attribute + metadata: unit, read/write, data type)
   - AttributeMapping (maps py-kermi-xcenter device attributes to MQTT topics)
   - Device (device_type, serial_number, available_attributes[], discovery_method)
   - DeviceTypeMapping (maps spec terminology to library classes and MQTT prefixes)
   - SafetyRule (method_name, writable: bool, value_range, validation_rules)
   - HADiscoveryPayload (component, config_topic, state_topic, command_topic)

2. **contracts/mqtt-topics.md**: MQTT topic structure specification
   - State topics: `/kermi/{device_type}/{parameter}`
   - Command topics: `/kermi/{device_type}/{parameter}/set`
   - Availability: `/kermi/{device_type}/availability`
   - Discovery: `homeassistant/{component}/{node_id}/{object_id}/config`

3. **contracts/ha-discovery.md**: Home Assistant discovery payload examples
   - Climate entity payload (heating/cooling control)
   - Water heater entity payload
   - Sensor entity payloads (temperature, energy, power)
   - Switch entity payloads
   - Device metadata linking

4. **safety.md**: Safety documentation
   - Table of py-kermi-xcenter API methods with safety classification:
     * User-Safe Methods: `set_hot_water_setpoint_constant()`, `set_pv_modulation_power()`, etc.
     * Read-Only Methods: All `get_*` methods (temperature sensors, status, COP, etc.)
     * Blocked Methods: Document any low-level control methods (if exposed by library)
   - Validation ranges for each writable method (temperature bounds, power limits)
   - Explicit warning: "This integration only exposes user-facing controls equivalent to the heat pump's physical interface"
   - Rationale: py-kermi-xcenter already implements safety by design (only exposes safe parameters)
   - Note: No manual register mapping needed - library handles all Modbus safety internally

5. **quickstart.md**: User setup guide
   - Installation (pip install, Docker)
   - Configuration file setup (Modbus connection, MQTT broker)
   - Modbus TCP configuration (default): host, port
   - Modbus RTU configuration (advanced): serial device, baudrate, parity, stopbits
   - Note: RTU requires pyserial and is non-default (TCP is recommended)
   - Running the service (systemd, Docker Compose)
   - Verification (subscribe to MQTT topics, check Home Assistant)
   - Troubleshooting common issues

### Design Workflow

1. Extract entities from spec.md functional requirements
2. Create device type mapping between spec terminology and py-kermi-xcenter classes (based on research.md)
3. Resolve StorageSystem disambiguation strategy (research.md section 2b)
4. Define attribute-to-MQTT topic mapping strategy (dynamic vs static registry)
5. Design MQTT topic hierarchy following Home Assistant conventions
6. Create discovery payload templates for each entity type
7. Document safety constraints with py-kermi-xcenter method whitelists

**Output**: data-model.md, contracts/, safety.md, quickstart.md

---

## Phase 2: Agent Context Update

**Prerequisites**: Phase 1 complete

Run agent context update script to make this plan's technologies discoverable:

```bash
.specify/scripts/bash/update-agent-context.sh claude
```

This updates `.claude/context.md` (or equivalent for other agents) with:
- Python 3.14+ as primary language
- kermi-xcenter, aiomqtt, pydantic as dependencies
- Async/await patterns for I/O-bound operations
- pytest + pytest-asyncio for testing
- GitHub Actions for CI/CD

**Output**: Updated agent-specific context file

---

## Next Steps

After Phase 2 completion, proceed to task generation:

```bash
/speckit.tasks
```

This will create `tasks.md` with concrete implementation steps organized by user story (P1: Monitor, P2: Control, P3: Auto-discovery, P4: HA Discovery).
