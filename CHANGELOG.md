# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.4] — 2026-07-06

Chart-feature release. No runtime/daemon changes — the Python package and
Docker image are functionally identical to 0.1.3; the version was bumped for
the unified release across package, image, and Helm chart.

### Added

- Optional `priorityClassName` value on the Helm chart, rendered into the
  Deployment pod spec when set (empty by default = no change). Lets operators
  assign a Kubernetes scheduling priority class — e.g. to protect a
  household-critical bridge from preemption on a busy cluster.

## [0.1.3] — 2026-04-19

### Added

- HTTP health-check server with three endpoints (`/healthz`, `/readyz`,
  `/status`) bound by default to `0.0.0.0:8080`. Liveness additionally
  requires that a poll cycle has completed within `stale_after_seconds`
  so that wedged sockets (where `is_connected` lies) are detected.
  ([#3](https://github.com/jr42/kermi2mqtt/issues/3))
- New `health:` config section (`enabled`, `host`, `port`,
  `stale_after_seconds`).
- `has_ever_connected` flag on MQTT / HTTP / Modbus clients, used to gate
  `/readyz` so pods stay out of a Service until the first real connect.
- Explicit `aiohttp>=3.9.0` dependency (previously transitive via
  `kermi-xcenter`).
- Optional opt-in `Service` in the Helm chart (`service.enabled`) for
  scraping `/status` from outside the pod.

### Changed

- **Helm chart behaviour change**: `livenessProbe`, `readinessProbe`, and
  `startupProbe` are now enabled by default and point at the new
  endpoints. Pods will be restarted by Kubernetes on persistent
  connectivity failure (~2.5 min of `/healthz` 503s at default
  settings). Set `config.health.enabled: false` to restore the previous
  no-probes behaviour.
- Bridge now tracks `last_successful_poll_monotonic` on every successful
  end-to-end poll cycle.

### Fixed

- `__version__` in `src/kermi2mqtt/__init__.py` was stuck at `"0.0.1"`;
  now tracks the package version.
