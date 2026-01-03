"""
Kermi device wrapper - wraps py-kermi-xcenter device instances with metadata.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from kermi2mqtt.models.datapoint import DeviceAttribute


class KermiDevice(BaseModel):
    """
    Wrapper around py-kermi-xcenter device instances with MQTT/HA metadata.

    Supports:
    - HeatPump (Unit 40) - research.md shows 28 get_* methods
    - StorageSystem (Units 50/51) - research.md shows 36 get_* methods
    - Auto-detection of purpose (heating vs DHW) via data inspection
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    device_id: str = Field(..., description="Unique device identifier")
    device_type: str = Field(
        ..., description="Device type (heat_pump, storage_heating, storage_dhw)"
    )
    unit_id: int = Field(..., description="Modbus unit ID (40, 50, 51, etc.)")
    xcenter_instance: Any = Field(..., description="Actual py-kermi-xcenter device object")
    attributes: list[DeviceAttribute] = Field(
        default_factory=list, description="All mapped attributes"
    )
    mqtt_base_topic: str = Field(..., description="Base MQTT topic for this device")
    available: bool = Field(default=True, description="Current connection status")
    last_poll: datetime | None = Field(
        default=None, description="When last successful poll completed"
    )

    def get_mqtt_topic(self, attribute: DeviceAttribute) -> str:
        """
        Get full MQTT topic for an attribute.

        Args:
            attribute: Device attribute

        Returns:
            Full MQTT topic path
        """
        return f"{self.mqtt_base_topic}/{attribute.mqtt_topic_suffix}"

    def get_availability_topic(self) -> str:
        """
        Get MQTT availability topic for this device.

        Returns:
            Availability topic path
        """
        return f"{self.mqtt_base_topic}/availability"
