"""
kermi2mqtt - Modbus-to-MQTT bridge for Kermi heat pumps.

A Python async service that bridges Kermi heat pumps to MQTT for home automation,
with Home Assistant auto-discovery support.
"""

__version__ = "0.0.1"
__author__ = "kermi2mqtt contributors"
__license__ = "Apache-2.0"

from kermi2mqtt.bridge import ModbusMQTTBridge
from kermi2mqtt.config import Config, load_config
from kermi2mqtt.modbus_client import ModbusClient
from kermi2mqtt.mqtt_client import MQTTClient

__all__ = [
    "Config",
    "load_config",
    "ModbusClient",
    "MQTTClient",
    "ModbusMQTTBridge",
    "__version__",
]
