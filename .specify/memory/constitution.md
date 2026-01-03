<!--
SYNC IMPACT REPORT
==================
Version Change: 1.0.0 → 1.1.0
Rationale: MINOR bump - Added new core principle (Safety) to protect heat pump hardware

Modified Principles: None

Added Sections:
- Core Principles: IV. Safety (NON-NEGOTIABLE)

Removed Sections: None

Templates Status:
- ✅ .specify/templates/spec-template.md: Reviewed - compatible
- ✅ .specify/templates/plan-template.md: Reviewed - constitution check section present
- ✅ .specify/templates/tasks-template.md: Reviewed - compatible structure
- ✅ All command files: Reviewed - no agent-specific references found

Follow-up TODOs: None
-->

# kermi2mqtt Constitution

## Core Principles

### I. Reliability (NON-NEGOTIABLE)

The system MUST maintain stable operation for continuous IoT/home automation usage. This means:
- Service MUST handle network interruptions gracefully
- Polling cycles MUST recover from transient failures without manual intervention
- MQTT connections MUST implement automatic reconnection with exponential backoff
- State changes MUST be persisted to survive service restarts where appropriate

**Rationale**: As a home automation integration, users depend on kermi2mqtt for critical heating control. Downtime or data loss directly impacts comfort and energy management.

### II. Simplicity

Code and architecture MUST remain straightforward and maintainable:
- Favor direct solutions over abstractions unless complexity is justified
- Dependencies MUST be minimized - only include libraries that provide clear value
- Configuration MUST be simple with sensible defaults
- Avoid premature optimization or generalization

**Rationale**: Simplicity reduces bugs, eases troubleshooting, and allows contributors to understand and modify the codebase quickly. IoT integrations should be approachable for community maintenance.

### III. Efficiency

The system MUST operate reliably on resource-constrained single-board computers (SBCs):
- Memory footprint MUST be minimal (target: <100MB RSS under typical load)
- CPU usage during polling cycles MUST be low (target: <5% average on Raspberry Pi 3)
- Network requests MUST be optimized to reduce API calls to Kermi services
- Startup time MUST be fast (<10 seconds to first MQTT publish)

**Rationale**: Many users run home automation on low-power devices like Raspberry Pi. The service must coexist with other containers/services without resource contention.

### IV. Safety (NON-NEGOTIABLE)

The system MUST NOT expose settings or controls that could damage the heat pump hardware:
- Low-level system parameters MUST NOT be exposed (e.g., pressure, compressor settings, refrigerant controls)
- Only user-facing settings MUST be accessible via MQTT (e.g., temperature setpoints, operating modes, schedules)
- Write operations MUST be limited to safe, manufacturer-approved adjustments
- Read-only access MUST be provided for diagnostic parameters that should not be modified
- Documentation MUST clearly indicate which settings are safe for user modification

**Rationale**: Heat pumps are expensive, safety-critical equipment. Incorrect adjustment of low-level parameters (pressure, compressor speeds, refrigerant flow) can cause physical damage, void warranties, or create safety hazards. The integration must act as a protective barrier, exposing only the settings that Kermi's own user interfaces would allow homeowners to modify.

## Development Standards

### Code Quality

- All code MUST pass linting and formatting checks before commit
- Public functions and modules MUST include docstrings explaining purpose and parameters
- Error messages MUST be actionable (tell users what went wrong and how to fix it)
- Logging MUST use appropriate levels (DEBUG for traces, INFO for state changes, ERROR for failures)

### Observability

- All external API calls MUST be logged with timing information
- MQTT publish/subscribe operations MUST be logged at INFO level
- Health check endpoints or status reporting MUST be provided
- Metrics collection (optional) should be supported for advanced users

### Testing Requirements

- Core polling logic MUST have unit tests
- MQTT message formatting MUST have unit tests
- Integration tests are RECOMMENDED for critical user journeys
- Test coverage requirements are NOT mandated but encouraged for complex logic
- Tests SHOULD mock external dependencies (Kermi API, MQTT broker)

**Note**: Given the IoT integration nature, comprehensive test coverage may be challenging. Focus testing on business logic rather than I/O boundaries.

## Governance

### Amendment Process

1. Constitution changes MUST be documented in this file
2. Version MUST be bumped according to semantic versioning:
   - MAJOR: Backward-incompatible principle changes
   - MINOR: New principles or material expansions
   - PATCH: Clarifications, wording improvements
3. Constitution changes SHOULD be reviewed by maintainers if project has multiple contributors
4. After amendment, dependent templates MUST be validated for consistency

### Compliance

- Pull requests SHOULD reference constitution principles when making architectural decisions
- Complex features MUST justify any deviations from simplicity principle
- Performance-impacting changes MUST consider efficiency principle and document resource usage
- Features exposing heat pump controls MUST demonstrate compliance with safety principle

### Living Document

This constitution is intended to evolve with the project. If principles become outdated or new concerns emerge, amendments are encouraged rather than working around stated principles.

**Version**: 1.1.0 | **Ratified**: 2025-11-25 | **Last Amended**: 2025-11-25
