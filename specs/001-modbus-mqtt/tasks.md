# Tasks: Modbus-to-MQTT Integration for Kermi Heat Pumps

**Input**: Design documents from `/specs/001-modbus-mqtt/`
**Prerequisites**: plan.md (required), spec.md (required), data-model.md, contracts/, research.md, safety.md, quickstart.md

**Tests**: Tests are NOT explicitly requested in the specification, so they are optional.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/kermi2mqtt/`, `tests/` at repository root
- Paths shown below use single project structure from plan.md

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create Python project structure with src/kermi2mqtt/ layout per plan.md
- [ ] T002 Initialize pyproject.toml with Python 3.14+ and PEP 621 metadata
- [ ] T003 [P] Add dependencies: py-kermi-xcenter, aiomqtt, pydantic to pyproject.toml
- [ ] T004 [P] Create .github/workflows/test.yml for pytest automation
- [ ] T005 [P] Create .github/workflows/lint.yml for ruff, mypy, black
- [ ] T006 [P] Create .github/workflows/release.yml for Docker + PyPI publishing
- [ ] T007 [P] Create Dockerfile for Linux/ARM64 (Raspberry Pi) deployment
- [ ] T008 [P] Create docker-compose.yaml for development environment
- [ ] T009 Create config.example.yaml with Modbus, MQTT, and integration settings
- [ ] T010 Create README.md with quickstart instructions from specs/001-modbus-mqtt/quickstart.md

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T011 Create src/kermi2mqtt/__init__.py with version info
- [ ] T012 Create src/kermi2mqtt/config.py with pydantic models for ModbusConfig, MQTTConfig, IntegrationConfig
- [ ] T013 Implement configuration loading from YAML file in src/kermi2mqtt/config.py
- [ ] T014 Create src/kermi2mqtt/models/__init__.py
- [ ] T015 [P] Create src/kermi2mqtt/models/datapoint.py with DeviceAttribute model from data-model.md
- [ ] T016 [P] Create src/kermi2mqtt/models/device.py with KermiDevice wrapper model
- [ ] T017 Create src/kermi2mqtt/safety.py with SafetyValidator and range_validator functions per safety.md
- [ ] T018 Create src/kermi2mqtt/modbus_client.py with KermiModbusClientWrapper class wrapping py-kermi-xcenter
- [ ] T019 Implement async connection management in modbus_client.py with exponential backoff per research.md
- [ ] T020 Create src/kermi2mqtt/mqtt_client.py with aiomqtt wrapper and reconnection logic
- [ ] T021 Implement MQTT publish/subscribe methods in mqtt_client.py with QoS handling per contracts/mqtt-topics.md
- [ ] T022 Create src/kermi2mqtt/__main__.py with argument parsing and main entry point
- [ ] T023 Implement signal handling (SIGTERM, SIGINT) for graceful shutdown in __main__.py per research.md
- [X] T023a Research StorageSystem disambiguation method from py-kermi-xcenter (check for type/purpose attributes or use unit ID conventions) per research.md section 2b
- [X] T023b Create specs/001-modbus-mqtt/safety.md documenting safe py-kermi-xcenter API methods, validation ranges, and blocked operations per constitution IV and plan.md

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Monitor Heat Pump Status (Priority: P1) 🎯 MVP

**Goal**: Read all Modbus datapoints and publish to MQTT under `/kermi/{device_id}/` hierarchy

**Independent Test**: Connect to heat pump via Modbus, poll all datapoints, verify they appear in MQTT under correct topics

### Implementation for User Story 1

- [ ] T024 [P] [US1] Document attribute-to-MQTT mapping strategy in data-model.md (decide: dynamic discovery via introspection vs static registry of known attributes)
- [ ] T025 [P] [US1] Implement AttributeRegistry in src/kermi2mqtt/models/attributes.py that maps py-kermi-xcenter device attributes to MQTT topics using strategy from T024
- [ ] T026 [US1] Create src/kermi2mqtt/bridge.py with poll_and_publish async function for reading all get_* methods
- [ ] T027 [US1] Implement device serial number detection in bridge.py using py-kermi-xcenter device info methods
- [ ] T028 [US1] Implement MQTT topic generation in bridge.py: `/kermi/{device_id}/{category}/{parameter}` per contracts/mqtt-topics.md
- [ ] T029 [US1] Implement polling loop with configurable interval (30s default) in bridge.py using asyncio.sleep
- [ ] T030 [US1] Add availability topic publishing (`online`/`offline`) in bridge.py per contracts/mqtt-topics.md
- [ ] T031 [US1] Implement error handling and logging for poll failures in bridge.py with exponential backoff
- [ ] T032 [US1] Add TaskGroup coordination in __main__.py to run Modbus polling + MQTT publishing concurrently per research.md
- [ ] T033 [US1] Test with mosquitto_sub to verify all sensor topics appear under `/kermi/#`

**Checkpoint**: At this point, User Story 1 should be fully functional - read-only monitoring working

---

## Phase 4: User Story 2 - Control User-Level Settings (Priority: P2)

**Goal**: Accept MQTT commands on `/set` topics, validate safety, write to heat pump, confirm changes

**Independent Test**: Publish commands to `/kermi/{device_id}/*/set` topics, verify heat pump responds and confirmation published

### Implementation for User Story 2

- [ ] T034 [P] [US2] Add writable attribute definitions to attributes registry with safety validation rules
- [ ] T035 [P] [US2] Implement command topic subscription in mqtt_client.py for `/kermi/+/+/+/set` pattern
- [ ] T036 [US2] Create command handler in bridge.py to parse incoming MQTT commands and map to device attributes
- [ ] T037 [US2] Implement safety validation in bridge.py using SafetyValidator before calling set_* methods
- [ ] T038 [US2] Add range validation for DHW setpoint (40-60°C) per safety.md
- [ ] T039 [US2] Implement write operation in bridge.py calling py-kermi-xcenter set_* methods
- [ ] T040 [US2] Add read-back confirmation after write in bridge.py to verify change took effect
- [ ] T041 [US2] Implement error topic publishing for validation failures: `{topic}/set/error` per contracts/mqtt-topics.md
- [ ] T042 [US2] Add command logging with timestamp, parameter, old/new values in bridge.py per FR-013
- [ ] T043 [US2] Test DHW setpoint change via MQTT and verify confirmation published

**Checkpoint**: At this point, User Stories 1 AND 2 should both work - full bidirectional control

---

## Phase 5: User Story 3 - Device Auto-Discovery (Priority: P3)

**Goal**: Detect which device types (HeatPump, StorageSystem, UniversalModule) are present and only publish relevant topics

**Independent Test**: Connect to different configurations, verify only present devices publish topics

### Implementation for User Story 3

- [ ] T044 [P] [US3] Add device detection logic in modbus_client.py attempting to instantiate HeatPump, StorageSystem, UniversalModule
- [ ] T045 [P] [US3] Implement discovery method testing (try calling a test method on each device type)
- [ ] T046 [US3] Create device registry in bridge.py to track which devices were successfully detected
- [ ] T047 [US3] Modify attribute registry loading to filter attributes based on detected devices
- [ ] T048 [US3] Update polling loop to only poll attributes from detected devices
- [ ] T049 [US3] Add device availability status per device type in bridge.py
- [ ] T050 [US3] Test with heat pump lacking certain components, verify only relevant topics appear

**Checkpoint**: Device discovery working - cleaner topic structure for varied installations

---

## Phase 6: User Story 4 - Home Assistant Auto-Discovery (Priority: P4)

**Goal**: Publish HA MQTT discovery messages on startup for automatic entity creation with correct types

**Independent Test**: Start integration with HA connected, verify entities appear automatically in HA device registry

### Implementation for User Story 4

- [ ] T051 [P] [US4] Create src/kermi2mqtt/ha_discovery.py with HADiscoveryMessage model from data-model.md
- [ ] T052 [P] [US4] Implement discovery payload generation for sensor entities in ha_discovery.py per contracts/ha-discovery.md
- [ ] T053 [P] [US4] Implement discovery payload generation for number entities (DHW setpoint) in ha_discovery.py
- [ ] T054 [P] [US4] Implement discovery payload generation for switch entities in ha_discovery.py
- [ ] T055 [US4] Create device info structure with identifiers, manufacturer, model in ha_discovery.py
- [ ] T056 [US4] Implement discovery message publishing in bridge.py with retain=true per FR-022
- [ ] T057 [US4] Add discovery topic pattern: `homeassistant/{component}/{device_id}/{object_id}/config` per contracts/ha-discovery.md
- [ ] T058 [US4] Ensure all entities link to same device via identifiers in device info per FR-024
- [ ] T059 [US4] Test HA restart scenario - verify entities persist via retained discovery messages per edge case requirements
- [ ] T060 [US4] Verify climate/water_heater entities appear if py-kermi-xcenter supports required methods

**Checkpoint**: Home Assistant zero-config integration complete - all entities auto-discovered

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T061 [P] Add comprehensive docstrings to all public functions and classes
- [ ] T062 [P] Create tests/fixtures/mock_register_data.py with sample heat pump data
- [ ] T063 [P] Create tests/unit/test_config.py for configuration loading
- [ ] T064 [P] Create tests/unit/test_safety.py for validation logic
- [ ] T065 [P] Create tests/unit/test_ha_discovery.py for discovery payload generation
- [ ] T066 Implement rate limiting for commands in bridge.py per safety.md (60s minimum between changes)
- [ ] T067 Add memory profiling to verify <50MB RSS target per SC-005
- [ ] T068 Add startup time measurement to verify <10s target per SC-009
- [ ] T069 Verify poll latency meets <5s update target per SC-002
- [ ] T070 Run linting (ruff, mypy, black) and fix any issues
- [ ] T071 Update README.md with actual Docker image name and PyPI package name
- [ ] T072 Run quickstart.md validation manually to ensure instructions work
- [ ] T073 [P] Create systemd service file (kermi2mqtt.service) with Restart=always and RestartSec=10s for auto-restart per FR-017
- [ ] T074 [P] Update docker-compose.yaml with restart: unless-stopped policy for resilience per FR-017

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - User stories CAN proceed in parallel if staffed
  - Or sequentially in priority order (P1 → P2 → P3 → P4)
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1 - Monitor)**: No dependencies on other stories - can start after Foundational
- **User Story 2 (P2 - Control)**: Builds on US1 (needs polling infrastructure) but independently testable
- **User Story 3 (P3 - Auto-Discovery)**: Can start after Foundational - refines US1/US2 behavior
- **User Story 4 (P4 - HA Discovery)**: Depends on US1 for sensor data, US2 for controls, but can implement discovery independently

### Within Each User Story

- Tasks marked [P] within a story can run in parallel
- Setup/config tasks before core logic
- Core implementation before error handling
- Story complete before moving to next priority

### Parallel Opportunities

- **Phase 1 (Setup)**: Tasks T003-T010 can all run in parallel (different files)
- **Phase 2 (Foundational)**: Tasks T015-T016 can run in parallel (different model files)
- **User Story 1**: Tasks T024-T025 can run in parallel (attributes definition)
- **User Story 2**: Tasks T034-T035 can run in parallel (writable attributes + subscription)
- **User Story 3**: Tasks T044-T045 can run in parallel (device detection logic)
- **User Story 4**: Tasks T051-T054 can run in parallel (discovery payloads for different entity types)
- **Phase 7 (Polish)**: Tasks T061-T065 can run in parallel (docs and tests), T073-T074 can run in parallel (deployment configs)

---

## Parallel Example: User Story 1

```bash
# Launch attribute mapping tasks together:
Task T024: "Define device attribute mappings"
Task T025: "Create attribute registry loader"

# After T024-T025 complete, these can run in parallel:
Task T027: "Implement device serial number detection"
Task T028: "Implement MQTT topic generation"
Task T031: "Implement error handling and logging"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T010)
2. Complete Phase 2: Foundational (T011-T023) - **CRITICAL BLOCKER**
3. Complete Phase 3: User Story 1 (T024-T033)
4. **STOP and VALIDATE**: Test monitoring with mosquitto_sub
5. Deploy/demo if ready - **Users can monitor their heat pump!**

### Incremental Delivery

1. **Foundation**: Complete Setup + Foundational → Core infrastructure ready
2. **MVP** (US1): Add monitoring → Test independently → Deploy/Demo (read-only monitoring works!)
3. **Control** (US2): Add bidirectional control → Test independently → Deploy/Demo (full control enabled!)
4. **Refinement** (US3): Add device discovery → Test independently → Deploy/Demo (cleaner UI for varied configs)
5. **HA Integration** (US4): Add auto-discovery → Test independently → Deploy/Demo (zero-config HA experience!)

Each story adds value without breaking previous stories.

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (T001-T023)
2. Once Foundational done (T023 complete):
   - Developer A: User Story 1 (T024-T033) - Monitoring
   - Developer B: User Story 2 (T034-T043) - Control (may need to coordinate with A on bridge.py)
   - Developer C: User Story 4 (T051-T060) - HA Discovery (independent of B)
3. User Story 3 (T044-T050) - Auto-Discovery can be done by any developer after US1 completes
4. Stories integrate and test independently

---

## Notes

- [P] tasks = different files, no dependencies on incomplete work
- [Story] label (US1, US2, etc.) maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- **Tests are optional** - specification does not require TDD approach
- Focus on making each user story a complete, deployable increment
- Avoid: vague tasks, same-file conflicts, cross-story dependencies that break independence

---

## Task Count Summary

- **Total Tasks**: 76
- **Phase 1 (Setup)**: 10 tasks
- **Phase 2 (Foundational)**: 15 tasks ⚠️ BLOCKS ALL USER STORIES (includes T023a research + T023b safety.md)
- **Phase 3 (US1 - Monitor)**: 10 tasks 🎯 MVP
- **Phase 4 (US2 - Control)**: 10 tasks
- **Phase 5 (US3 - Auto-Discovery)**: 7 tasks
- **Phase 6 (US4 - HA Discovery)**: 10 tasks
- **Phase 7 (Polish)**: 14 tasks (includes T073-T074 auto-restart)

**Parallel Opportunities**: 25 tasks marked [P] can run in parallel within their phases

**Suggested MVP Scope**: Phases 1-3 (T001-T033 + T023a-T023b) = 35 tasks for read-only monitoring

**Full Feature Scope**: All 76 tasks for complete integration with HA auto-discovery
