# Multi-stage build for minimal final image
FROM python:3.12-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Build wheel
RUN pip install --no-cache-dir build && \
    python -m build --wheel

# Final stage
FROM python:3.12-slim

# Create non-root user
RUN useradd --create-home --shell /bin/bash kermi && \
    mkdir -p /app /config && \
    chown -R kermi:kermi /app /config

WORKDIR /app

# Install runtime dependencies only
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && \
    rm -rf /tmp/*.whl

# Create health check marker (used by Kubernetes probes)
RUN touch /tmp/healthy && chown kermi:kermi /tmp/healthy

# Switch to non-root user
USER kermi

# Configuration volume
VOLUME ["/config"]

# Default environment
ENV CONFIG_PATH=/config/config.yaml

# Health check (for Docker standalone - Kubernetes uses probes instead)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD test -f /tmp/healthy

# Entry point
ENTRYPOINT ["kermi2mqtt"]
CMD ["--config", "/config/config.yaml"]
