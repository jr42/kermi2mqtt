# Feature Specification: Modbus-to-MQTT Integration for Kermi Heat Pumps

**Feature Branch**: `001-modbus-mqtt`
**Created**: 2025-11-25
**Status**: Draft
**Input**: User description: "Build a modbus to mqtt integration for kermi heatpumps. it should publish all available datapoints to mqtt to /kermi and support changing user-level settings (e.g. heating/cooling floor heating, warm water one-time heating etc.). The datapoints should be grouped by heatpump devices (interface module, heatpump, water heater, floor heating depending on what is available)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Monitor Heat Pump Status (Priority: P1)

As a home automation user, I want to see current heat pump data (temperatures, operating modes, status) published to MQTT so that I can monitor my heating system in my smart home dashboard.

**Why this priority**: Monitoring is the foundation of any integration. Users need to see their system status before they can control it. This provides immediate value even without control capabilities.

**Independent Test**: Can be fully tested by connecting to the heat pump via Modbus, reading all available datapoints, and verifying they appear under `/kermi/[device-type]/[parameter]` topics in MQTT. Delivers read-only monitoring capability.

**Acceptance Scenarios**:

1. **Given** the integration is running and connected to the heat pump, **When** the heat pump reports a temperature change, **Then** the new temperature value is published to the appropriate MQTT topic within 5 seconds
2. **Given** the integration starts up, **When** it successfully connects to the heat pump, **Then** all available datapoints are discovered and published to MQTT with their current values
3. **Given** multiple device types are present (interface module, heat pump, water heater, floor heating), **When** datapoints are published, **Then** they are organized under separate MQTT topic hierarchies for each device type
4. **Given** the integration is running, **When** a user subscribes to `/kermi/#`, **Then** they receive all heat pump datapoints organized by device and parameter name

---

### User Story 2 - Control User-Level Settings (Priority: P2)

As a home automation user, I want to change user-level heat pump settings (heating/cooling modes, temperature setpoints, one-time water heating) via MQTT so that I can control my heating system from my smart home automations.

**Why this priority**: Control functionality builds on monitoring (P1) and enables automation scenarios. However, it requires careful safety validation to prevent hardware damage.

**Independent Test**: Can be tested by publishing control commands to MQTT topics like `/kermi/[device]/[parameter]/set` and verifying the heat pump responds appropriately. Delivers bidirectional control capability.

**Acceptance Scenarios**:

1. **Given** the integration is running, **When** a user publishes a new temperature setpoint to `/kermi/heating/target_temperature/set`, **Then** the heat pump receives the Modbus write command and the new setpoint is reflected in the heat pump within 10 seconds
2. **Given** a user wants to enable one-time water heating, **When** they publish "ON" to `/kermi/water_heater/one_time_heating/set`, **Then** the water heater activates one-time heating mode
3. **Given** a user attempts to modify a low-level system parameter (pressure, compressor settings), **When** they publish to that parameter's set topic, **Then** the integration rejects the command and logs a safety violation
4. **Given** a control command is sent, **When** the Modbus write completes, **Then** the integration immediately reads back the parameter to confirm the change and publishes the updated value to MQTT

---

### User Story 3 - Device Auto-Discovery (Priority: P3)

As a home automation user, I want the integration to automatically discover which heat pump components are present (interface module, heat pump, water heater, floor heating) so that I only see relevant datapoints for my specific installation.

**Why this priority**: This improves user experience by showing only applicable parameters, but the system can function with all devices exposed initially. It's a refinement feature.

**Independent Test**: Can be tested by connecting to different heat pump configurations and verifying that only present devices and their parameters appear in MQTT. Delivers cleaner, configuration-specific monitoring.

**Acceptance Scenarios**:

1. **Given** a heat pump installation with only heating (no floor heating or dedicated water heater), **When** the integration starts, **Then** only interface module and heat pump topics are published to MQTT
2. **Given** an installation with all components, **When** the integration discovers devices, **Then** separate MQTT topic hierarchies exist for interface module, heat pump, water heater, and floor heating
3. **Given** device discovery fails for a component, **When** the integration logs the detection status, **Then** it continues operating with detected devices and publishes an availability status message to MQTT

---

### User Story 4 - Home Assistant Auto-Discovery (Priority: P4)

As a Home Assistant user, I want the integration to publish MQTT discovery messages so that all heat pump entities automatically appear in Home Assistant with appropriate entity types (climate, sensor, switch, water heater) without manual configuration.

**Why this priority**: While not essential for basic operation, Home Assistant is the most popular home automation platform. Auto-discovery dramatically improves user experience by eliminating manual entity configuration.

**Independent Test**: Can be tested by starting the integration with Home Assistant connected to the same MQTT broker and verifying that climate controls, sensors, and switches automatically appear in Home Assistant's entity list. Delivers zero-configuration Home Assistant integration.

**Acceptance Scenarios**:

1. **Given** Home Assistant is connected to the MQTT broker, **When** the integration starts, **Then** discovery messages are published to `homeassistant/[component]/[node_id]/[object_id]/config` for all heat pump entities
2. **Given** the heat pump has heating/cooling capability, **When** discovery runs, **Then** a climate entity appears in Home Assistant with temperature control and mode selection
3. **Given** the heat pump has a water heater, **When** discovery runs, **Then** a water_heater entity appears in Home Assistant with temperature control and operation modes
4. **Given** temperature sensors exist on the heat pump, **When** discovery runs, **Then** sensor entities appear in Home Assistant with appropriate device classes (temperature, energy, power) and units of measurement
5. **Given** controllable switches exist (one-time heating, circulation pump), **When** discovery runs, **Then** switch entities appear in Home Assistant
6. **Given** the integration loses connection to the heat pump, **When** availability status changes, **Then** all Home Assistant entities show as unavailable

---

### Edge Cases

- What happens when the Modbus connection is lost mid-operation? (System should attempt reconnection with exponential backoff, maintain last-known values in MQTT with availability=offline)
- How does the system handle invalid control values (e.g., temperature setpoint outside valid range)? (Validate before writing to Modbus, reject with error message published to error topic)
- What happens if multiple control commands are sent simultaneously to the same parameter? (Queue commands sequentially with timeout, report any conflicts)
- How does the integration behave if the heat pump is in an error state? (Continue monitoring, publish error codes to MQTT, prevent control commands until error is cleared)
- What happens when the MQTT broker becomes unavailable? (Buffer recent values locally with size limit, reconnect automatically, republish buffered state on reconnection)
- How does Home Assistant discovery handle duplicate integrations? (Use unique device identifiers based on heat pump serial number or MAC address)
- What happens if Home Assistant restarts while the integration is running? (Discovery messages should be retained in MQTT so Home Assistant rediscovers entities automatically)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST connect to Kermi heat pumps via Modbus TCP/RTU protocol
- **FR-002**: System MUST read all available datapoints from the heat pump at a configurable polling interval (default: 30 seconds)
- **FR-003**: System MUST publish all datapoints to MQTT under the `/kermi` base topic
- **FR-004**: System MUST organize datapoints by device type (interface_module, heatpump, water_heater, floor_heating) in the MQTT topic hierarchy
- **FR-005**: System MUST support bidirectional communication: publishing sensor data and accepting control commands via MQTT
- **FR-006**: System MUST allow users to modify user-level settings (heating/cooling modes, temperature setpoints, schedules, one-time heating)
- **FR-007**: System MUST prevent modification of low-level system parameters (pressure, compressor settings, refrigerant controls) per Safety principle
- **FR-008**: System MUST validate control commands before writing to Modbus (range checks, data type validation)
- **FR-009**: System MUST read back modified parameters after write operations to confirm changes
- **FR-010**: System MUST publish device availability status to MQTT (online/offline per device)
- **FR-011**: System MUST handle Modbus connection failures gracefully with automatic reconnection
- **FR-012**: System MUST handle MQTT broker disconnections gracefully with automatic reconnection
- **FR-013**: System MUST log all control operations (who changed what, when) for troubleshooting
- **FR-014**: System MUST support discovery of which device types are present in the installation
- **FR-015**: System MUST provide clear documentation indicating which parameters are safe for user modification
- **FR-016**: System MUST publish meaningful error messages to MQTT when operations fail
- **FR-017**: System MUST start automatically on system boot and restart on crashes (resilience)
- **FR-018**: System MUST support configuration via file (Modbus connection details, MQTT broker settings, polling intervals)
- **FR-019**: System MUST publish Home Assistant MQTT discovery messages on startup for automatic entity creation
- **FR-020**: System MUST map heat pump capabilities to appropriate Home Assistant entity types (climate for HVAC control, water_heater for DHW, sensor for read-only values, switch for on/off controls)
- **FR-021**: System MUST include device information in discovery messages (manufacturer, model, identifiers, connections)
- **FR-022**: System MUST use retain flag for discovery messages so Home Assistant can rediscover entities after restart
- **FR-023**: System MUST provide unique entity identifiers to prevent conflicts with other integrations
- **FR-024**: System MUST link all entities to a single device in Home Assistant representing the heat pump system

### Key Entities

- **Modbus Register**: Represents a data point on the heat pump (address, data type, read/write permissions, unit of measurement, scaling factor)
- **Device Type**: Logical grouping of registers (interface_module, heatpump, water_heater, floor_heating) that organize MQTT topics
- **Datapoint**: A named parameter with current value, timestamp, and availability status (e.g., "outdoor_temperature", "heating_mode")
- **Control Command**: A user-initiated change request with parameter name, target value, and validation rules
- **Safety Rule**: A constraint that prevents modification of dangerous parameters (pressure, compressor, refrigerant settings)
- **Discovery Message**: Home Assistant MQTT discovery payload containing entity configuration (entity type, device class, unit, state topic, command topic, availability topic)
- **Entity Mapping**: Association between Modbus datapoints and Home Assistant entity types (temperature sensor → sensor with device_class=temperature, HVAC control → climate entity)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can view all heat pump datapoints in their MQTT-enabled home automation system within 60 seconds of integration startup
- **SC-002**: Datapoint updates from the heat pump appear in MQTT within 5 seconds of the configured polling interval
- **SC-003**: Control commands sent via MQTT are applied to the heat pump within 10 seconds with confirmation published back to MQTT
- **SC-004**: The integration maintains 99% uptime over 30 days (handles transient network failures without manual intervention)
- **SC-005**: Integration operates continuously on resource-constrained hardware (Raspberry Pi 3) with less than 50MB memory usage
- **SC-006**: 100% of low-level system parameters (pressure, compressor, refrigerant) are blocked from modification with clear error messages
- **SC-007**: Users can successfully control at least 5 common user-level settings (heating mode, cooling mode, temperature setpoints, one-time water heating, schedules)
- **SC-008**: Device discovery correctly identifies which components are present in 95% of installations
- **SC-009**: Integration startup completes within 15 seconds and begins publishing data immediately
- **SC-010**: All control operations are logged with timestamp, parameter name, old value, and new value for troubleshooting
- **SC-011**: Home Assistant users can add the integration without any manual MQTT configuration (zero-config experience via discovery)
- **SC-012**: All heat pump entities appear in Home Assistant within 30 seconds of integration startup with correct entity types and device classes
- **SC-013**: Climate entity in Home Assistant successfully controls heat pump temperature and mode with state updates appearing within 10 seconds

## Assumptions

1. **Modbus Access**: Users have network access to their Kermi heat pump's Modbus interface (TCP or RTU via serial-to-network adapter)
2. **MQTT Broker**: Users have an MQTT broker running (Mosquitto, Home Assistant embedded broker, etc.) that the integration can connect to
3. **Authentication**: Kermi heat pump Modbus interface does not require authentication (standard for local network access), but MQTT broker may require credentials
4. **Polling Acceptable**: Heat pump state changes infrequently enough that polling every 30 seconds (default) is sufficient (vs. event-driven updates)
5. **Vendor Documentation**: Kermi Modbus specification document provides complete register map with addresses, data types, and access permissions
6. **User Responsibility**: Users running the integration understand basic home automation concepts and can configure MQTT and Modbus connection parameters
7. **Home Assistant Compatibility**: MQTT discovery follows Home Assistant conventions (topic structure, payload format, entity types)
8. **Single Heat Pump**: The integration connects to one heat pump system (multiple devices within that system are supported)
9. **Discovery Prefix**: Home Assistant uses default MQTT discovery prefix of `homeassistant` (configurable if needed)
10. **Retained Messages**: MQTT broker supports retained messages for discovery payloads

## Dependencies

1. **External**: Kermi heat pump with Modbus TCP/RTU interface enabled
2. **External**: MQTT broker (e.g., Mosquitto, Home Assistant) accessible on the network with retained message support
3. **External**: Kermi Modbus specification document (register addresses, data types, safety constraints)
4. **External**: Network connectivity between integration host, heat pump, and MQTT broker
5. **External**: Home Assistant MQTT discovery specification (for P4 auto-discovery feature)

## Scope

### In Scope

- Reading all Modbus datapoints from Kermi heat pumps and publishing to MQTT
- Writing user-level settings via MQTT control topics
- Device auto-discovery (interface module, heatpump, water heater, floor heating)
- Safety enforcement preventing low-level parameter modification
- Connection resilience (auto-reconnect for Modbus and MQTT)
- Configuration via file (connection settings, polling intervals)
- Logging of control operations for troubleshooting
- Home Assistant MQTT discovery with appropriate entity types:
  - Climate entity for heating/cooling control
  - Water heater entity for domestic hot water control
  - Sensor entities for temperature, energy, power readings
  - Switch entities for on/off controls (one-time heating, pumps)
  - Binary sensor entities for status indicators
- Device grouping in Home Assistant (all entities linked to single heat pump device)
- Unique identifiers preventing conflicts between multiple integrations

### Out of Scope

- Graphical user interface (users interact via MQTT and their existing home automation dashboards)
- Historical data storage (users should use their home automation platform's recorder or InfluxDB)
- Advanced analytics or machine learning on heat pump data
- Support for non-Kermi heat pumps (other manufacturers have different Modbus implementations)
- RESTful API (MQTT is the integration protocol)
- Mobile application (users use existing home automation apps)
- Modbus-to-modbus bridging for multiple heat pumps (single heat pump per integration instance)
- Discovery for non-Home Assistant platforms (OpenHAB, Domoticz have different discovery mechanisms)
- Custom Home Assistant cards or frontend components (users can create dashboards with standard entity cards)
