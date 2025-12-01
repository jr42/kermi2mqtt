"""
Configuration loading and validation using Pydantic.
"""

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

    device_id: str | None = Field(
        None, description="Device identifier (auto-detected if not set)"
    )
    base_topic: str = Field("kermi", description="MQTT base topic prefix")
    poll_interval: float = Field(
        30.0, description="Polling interval in seconds", ge=10.0, le=300.0
    )
    ha_discovery_prefix: str = Field(
        "homeassistant", description="Home Assistant discovery prefix"
    )
    storage_systems: dict[int, StorageSystemConfig] = Field(
        default_factory=dict, description="Storage system configuration (optional)"
    )


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        "INFO", description="Log level"
    )
    file: str | None = Field(None, description="Log file path (optional)")


class SafetyConfig(BaseModel):
    """Safety settings."""

    command_rate_limit: float = Field(
        60.0, description="Minimum seconds between commands", ge=0.0
    )
    enable_validation: bool = Field(
        True, description="Enable safety validation for writes"
    )


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

    modbus: ModbusConfig
    mqtt: MQTTConfig
    integration: IntegrationConfig = Field(default_factory=IntegrationConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    advanced: AdvancedConfig = Field(default_factory=AdvancedConfig)


def load_config(config_path: str | Path) -> Config:
    """
    Load and validate configuration from YAML file.

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

    try:
        return Config(**config_dict)
    except Exception as e:
        raise ValueError(f"Invalid configuration: {e}") from e
