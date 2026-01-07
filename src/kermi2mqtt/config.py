"""
Configuration loading and validation using Pydantic.
"""

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator


class ModbusConfig(BaseModel):
    """Modbus connection configuration."""

    host: str = Field(..., description="Modbus TCP host or RTU device path")
    port: int = Field(502, description="Modbus TCP port")
    mode: Literal["tcp", "rtu"] = Field("tcp", description="Connection mode")

    # RTU-specific settings
    device: str | None = Field(None, description="Serial device path for RTU")
    baudrate: int | None = Field(None, description="Serial baudrate for RTU")
    parity: str | None = Field(None, description="Serial parity for RTU")
    stopbits: int | None = Field(None, description="Serial stop bits for RTU")

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port is in valid range."""
        if not 1 <= v <= 65535:
            raise ValueError(f"Port must be 1-65535, got {v}")
        return v


class HttpConfig(BaseModel):
    """HTTP API connection configuration."""

    host: str = Field(..., description="x-center hostname or IP address")
    port: int = Field(80, description="HTTP port")
    password: str | None = Field(None, description="Optional password (last 4 digits of serial)")
    timeout: float = Field(10.0, description="Request timeout in seconds", ge=1.0, le=60.0)

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port is in valid range."""
        if not 1 <= v <= 65535:
            raise ValueError(f"Port must be 1-65535, got {v}")
        return v


class MQTTConfig(BaseModel):
    """MQTT broker configuration."""

    host: str = Field(..., description="MQTT broker hostname")
    port: int = Field(1883, description="MQTT broker port")
    username: str | None = Field(None, description="MQTT username (optional)")
    password: str | None = Field(None, description="MQTT password (optional)")

    # TLS/SSL settings
    tls_enabled: bool = Field(False, description="Enable TLS/SSL encryption")
    tls_insecure: bool = Field(False, description="Disable certificate verification (insecure)")
    ca_certs: str | None = Field(None, description="Path to CA certificate file")
    certfile: str | None = Field(None, description="Path to client certificate")
    keyfile: str | None = Field(None, description="Path to client private key")

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port is in valid range."""
        if not 1 <= v <= 65535:
            raise ValueError(f"Port must be 1-65535, got {v}")
        return v


class StorageSystemConfig(BaseModel):
    """Storage system configuration for disambiguation."""

    purpose: Literal["heating", "dhw", "combined"] = Field(
        ..., description="Storage system purpose"
    )
    name: str = Field(..., description="Human-readable name")


class IntegrationConfig(BaseModel):
    """Integration behavior configuration."""

    connection_type: Literal["http", "modbus"] = Field(
        "http", description="Connection type: 'http' (recommended) or 'modbus'"
    )
    device_id: str | None = Field(None, description="Device identifier (auto-detected if not set)")
    base_topic: str = Field("kermi", description="MQTT base topic prefix")
    poll_interval: float = Field(30.0, description="Polling interval in seconds", ge=10.0, le=300.0)
    ha_discovery_enabled: bool = Field(
        True, description="Enable Home Assistant MQTT discovery (disable for n8n/ioBroker/etc.)"
    )
    ha_discovery_prefix: str = Field("homeassistant", description="Home Assistant discovery prefix")
    storage_systems: dict[int, StorageSystemConfig] = Field(
        default_factory=dict, description="Storage system configuration (optional)"
    )


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field("INFO", description="Log level")
    file: str | None = Field(None, description="Log file path (optional)")


class SafetyConfig(BaseModel):
    """Safety settings."""

    command_rate_limit: float = Field(60.0, description="Minimum seconds between commands", ge=0.0)
    enable_validation: bool = Field(True, description="Enable safety validation for writes")


class AdvancedConfig(BaseModel):
    """Advanced settings."""

    modbus_reconnect_delay: float = Field(2.0, ge=0.1, le=60.0)
    modbus_max_reconnect_delay: float = Field(30.0, ge=1.0, le=300.0)
    mqtt_reconnect_delay: float = Field(1.0, ge=0.1, le=60.0)
    mqtt_max_reconnect_delay: float = Field(60.0, ge=1.0, le=300.0)
    mqtt_qos_state: int = Field(1, ge=0, le=2)
    mqtt_qos_command: int = Field(1, ge=0, le=2)
    mqtt_retain_discovery: bool = Field(True)
    mqtt_retain_state: bool = Field(False)


class Config(BaseModel):
    """Complete application configuration."""

    modbus: ModbusConfig | None = Field(None, description="Modbus configuration (required if connection_type='modbus')")
    http: HttpConfig | None = Field(None, description="HTTP configuration (required if connection_type='http')")
    mqtt: MQTTConfig
    integration: IntegrationConfig = Field(default_factory=IntegrationConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    advanced: AdvancedConfig = Field(default_factory=AdvancedConfig)


def load_config(config_path: str | Path) -> Config:
    """
    Load and validate configuration from YAML file.

    Environment variables can override MQTT credentials:
    - MQTT_USERNAME: Override mqtt.username
    - MQTT_PASSWORD: Override mqtt.password

    Backward compatibility:
    - If only 'modbus' is provided and connection_type is 'http', auto-creates http config
    - If 'modbus' is provided without 'http', defaults to connection_type='modbus'

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Validated Config object

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid
        yaml.YAMLError: If YAML parsing fails
    """
    config_file = Path(config_path)

    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with config_file.open("r") as f:
        config_dict = yaml.safe_load(f)

    if config_dict is None:
        raise ValueError(f"Empty configuration file: {config_path}")

    # Apply environment variable overrides for MQTT credentials
    if "mqtt" not in config_dict:
        config_dict["mqtt"] = {}

    if mqtt_username := os.environ.get("MQTT_USERNAME"):
        config_dict["mqtt"]["username"] = mqtt_username
    if mqtt_password := os.environ.get("MQTT_PASSWORD"):
        config_dict["mqtt"]["password"] = mqtt_password

    # Backward compatibility: if only modbus is provided
    if "modbus" in config_dict and "http" not in config_dict:
        # Check if connection_type is explicitly set to http
        integration = config_dict.get("integration", {})
        conn_type = integration.get("connection_type", "modbus")  # Default to modbus for backward compat

        if conn_type == "http":
            # Auto-create http config from modbus host
            modbus_cfg = config_dict["modbus"]
            config_dict["http"] = {
                "host": modbus_cfg.get("host"),
                "port": 80,  # HTTP default
                "password": None,
                "timeout": 10.0,
            }
        else:
            # Ensure connection_type defaults to modbus for backward compatibility
            if "integration" not in config_dict:
                config_dict["integration"] = {}
            config_dict["integration"]["connection_type"] = "modbus"

    try:
        config = Config(**config_dict)
    except Exception as e:
        raise ValueError(f"Invalid configuration: {e}") from e

    # Validate that required config is present for connection type
    conn_type = config.integration.connection_type
    if conn_type == "http" and config.http is None:
        raise ValueError("HTTP configuration required when connection_type='http'")
    if conn_type == "modbus" and config.modbus is None:
        raise ValueError("Modbus configuration required when connection_type='modbus'")

    return config
