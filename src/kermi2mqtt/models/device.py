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
    - IFM (Unit 0) - x-center gateway with network info
    - HeatPump (Unit 40) - research.md shows 28 get_* methods
    - StorageSystem (Units 50/51) - research.md shows 36 get_* methods
    - Auto-detection of purpose (heating vs DHW) via data inspection
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    device_id: str = Field(..., description="Unique device identifier")
    device_type: str = Field(
        ..., description="Device type (ifm, heat_pump, storage_heating, storage_dhw)"
    )
    unit_id: int = Field(..., description="Modbus unit ID (0, 40, 50, 51)")
    xcenter_instance: Any = Field(..., description="Actual py-kermi-xcenter device object")
    attributes: list[DeviceAttribute] = Field(
        default_factory=list, description="All mapped attributes"
    )
    mqtt_base_topic: str = Field(..., description="Base MQTT topic for this device")
    available: bool = Field(default=True, description="Current connection status")
    last_poll: datetime | None = Field(
        default=None, description="When last successful poll completed"
    )

    # Device metadata (populated from HTTP API get_device_info)
    serial_number: str | None = Field(default=None, description="Device serial number")
    model_name: str | None = Field(default=None, description="Device model name")
    software_version: str | None = Field(default=None, description="Device firmware version")

    @property
    def ha_device_identifier(self) -> str:
        """
        Get Home Assistant device identifier based on serial number.

        Falls back to device_id if serial not available.
        """
        if self.serial_number:
            # Sanitize serial for use as identifier (remove dashes, spaces)
            sanitized = self.serial_number.replace("-", "").replace(" ", "").lower()
            return f"kermi_{sanitized}"
        return f"kermi_{self.device_id}"

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
