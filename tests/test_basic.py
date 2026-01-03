"""
Basic structural tests for kermi2mqtt.

These tests verify the package structure and basic imports work correctly.
"""



def test_version_exists():
    """Test that package has a version."""
    from kermi2mqtt import __version__

    assert __version__ == "0.1.0"


def test_config_imports():
    """Test that config models can be imported."""
    from kermi2mqtt.config import (
        Config,
        ModbusConfig,
        MQTTConfig,
    )

    assert Config is not None
    assert ModbusConfig is not None
    assert MQTTConfig is not None


def test_model_imports():
    """Test that data models can be imported."""
    from kermi2mqtt.models import DeviceAttribute, KermiDevice

    assert DeviceAttribute is not None
    assert KermiDevice is not None


def test_client_imports():
    """Test that client classes can be imported."""
    from kermi2mqtt.modbus_client import ModbusClient
    from kermi2mqtt.mqtt_client import MQTTClient

    assert ModbusClient is not None
    assert MQTTClient is not None


def test_bridge_imports():
    """Test that bridge class can be imported."""
    from kermi2mqtt.bridge import ModbusMQTTBridge

    assert ModbusMQTTBridge is not None


def test_mappings_imports():
    """Test that attribute mappings can be imported."""
    from kermi2mqtt.mappings import (
        get_heat_pump_attributes,
        get_storage_system_attributes,
    )

    # Verify mappings return lists
    heat_pump_attrs = get_heat_pump_attributes()
    storage_attrs = get_storage_system_attributes()

    assert isinstance(heat_pump_attrs, list)
    assert isinstance(storage_attrs, list)
    assert len(heat_pump_attrs) > 0
    assert len(storage_attrs) > 0


def test_safety_imports():
    """Test that safety validators can be imported."""
    from kermi2mqtt.safety import (
        RangeValidator,
        RateLimiter,
        SafetyValidator,
        create_dhw_validator,
        create_pv_power_validator,
    )

    assert RangeValidator is not None
    assert RateLimiter is not None
    assert SafetyValidator is not None
    assert create_dhw_validator is not None
    assert create_pv_power_validator is not None
