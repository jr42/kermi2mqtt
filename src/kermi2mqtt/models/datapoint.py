"""
Device attribute model - maps py-kermi-xcenter methods to MQTT topics.
"""

from enum import IntEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DeviceAttribute(BaseModel):
    """
    Maps a py-kermi-xcenter device method to an MQTT topic and HA entity.

    Based on research findings (research.md section 2b):
    - HeatPump has 28 get_* methods
    - StorageSystem has 36 get_* methods
    - get_all_readable_values() returns complete dict for efficient polling
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    device_class: str = Field(..., description="Device class name (HeatPump, StorageSystem)")
    method_name: str = Field(..., description="Method to call (e.g., get_outdoor_temperature)")
    friendly_name: str = Field(..., description="Human-readable name")
    mqtt_topic_suffix: str = Field(
        ..., description="Topic suffix after device ID (e.g., sensors/outdoor_temp)"
    )
    writable: bool = Field(False, description="Whether this has a setter method")
    ha_component: str = Field(
        ...,
        description="HA entity type (sensor, climate, switch, water_heater, number, binary_sensor)",
    )
    ha_config: dict[str, Any] = Field(
        default_factory=dict,
        description="HA-specific config (unit, device_class, state_class, min, max, etc.)",
    )
    poll_interval: float | None = Field(
        default=None, description="Override default poll interval for this attribute"
    )
    value_enum: type[IntEnum] | None = Field(
        default=None,
        description="Enum type for translating numeric values (e.g., HeatPumpStatus)",
    )
