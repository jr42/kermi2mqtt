"""
Unit tests for StorageSystem attribute filtering logic.

Tests the filtering rules that prevent publishing irrelevant sensors
to MQTT and Home Assistant.
"""


from kermi2mqtt.bridge import _should_publish_attribute
from kermi2mqtt.models.datapoint import DeviceAttribute


def test_heating_only_filtered_on_dhw():
    """Heating-only attributes should always be filtered on DHW devices."""
    attr = DeviceAttribute(
        device_class="StorageSystem",
        method_name="heating_actual",
        friendly_name="Heating Actual",
        mqtt_topic_suffix="sensors/heating_actual",
        writable=False,
        ha_component="sensor",
        ha_config={},
    )

    # Should ALWAYS filter on DHW device (regardless of value)
    assert not _should_publish_attribute("storage_dhw", attr, 0.0)
    assert not _should_publish_attribute("storage_dhw", attr, 25.5)

    # Should always publish on heating device (regardless of value)
    assert _should_publish_attribute("storage_heating", attr, 0.0)
    assert _should_publish_attribute("storage_heating", attr, 25.5)


def test_dhw_only_filtered_on_heating():
    """DHW-only attributes should always be filtered on heating devices."""
    attr = DeviceAttribute(
        device_class="StorageSystem",
        method_name="hot_water_actual",
        friendly_name="Hot Water Actual",
        mqtt_topic_suffix="sensors/hot_water_actual",
        writable=False,
        ha_component="sensor",
        ha_config={},
    )

    # Should ALWAYS filter on heating device (regardless of value)
    assert not _should_publish_attribute("storage_heating", attr, 0.0)
    assert not _should_publish_attribute("storage_heating", attr, 44.7)

    # Should always publish on DHW device (regardless of value)
    assert _should_publish_attribute("storage_dhw", attr, 0.0)
    assert _should_publish_attribute("storage_dhw", attr, 44.7)


def test_shared_sensors_always_publish():
    """Shared sensors should publish on both device types."""
    attr = DeviceAttribute(
        device_class="StorageSystem",
        method_name="t1_temperature",
        friendly_name="T1 Temperature",
        mqtt_topic_suffix="sensors/t1_temp",
        writable=False,
        ha_component="sensor",
        ha_config={},
    )

    # Should publish on both device types regardless of value
    assert _should_publish_attribute("storage_heating", attr, 0.0)
    assert _should_publish_attribute("storage_dhw", attr, 0.0)
    assert _should_publish_attribute("storage_heating", attr, 25.5)
    assert _should_publish_attribute("storage_dhw", attr, 44.7)


def test_binary_sensors_filtered_correctly():
    """Binary sensors should be filtered based on device type."""
    attr = DeviceAttribute(
        device_class="StorageSystem",
        method_name="cooling_mode_active",
        friendly_name="Cooling Mode Active",
        mqtt_topic_suffix="binary_sensors/cooling_active",
        writable=False,
        ha_component="binary_sensor",
        ha_config={},
    )

    # Should ALWAYS filter on DHW device (cooling is heating-only attribute)
    assert not _should_publish_attribute("storage_dhw", attr, False)
    assert not _should_publish_attribute("storage_dhw", attr, True)

    # Should always publish on heating device (regardless of value)
    assert _should_publish_attribute("storage_heating", attr, False)
    assert _should_publish_attribute("storage_heating", attr, True)


def test_outdoor_temp_filtered_on_dhw():
    """Outdoor temperature sensors should only publish on heating units."""
    attr_t4 = DeviceAttribute(
        device_class="StorageSystem",
        method_name="t4_temperature",
        friendly_name="Outdoor Temperature (T4)",
        mqtt_topic_suffix="sensors/t4_temp",
        writable=False,
        ha_component="sensor",
        ha_config={},
    )

    attr_avg = DeviceAttribute(
        device_class="StorageSystem",
        method_name="outdoor_temperature_avg",
        friendly_name="Outdoor Temperature Average",
        mqtt_topic_suffix="sensors/outdoor_temp_avg",
        writable=False,
        ha_component="sensor",
        ha_config={},
    )

    # Should ALWAYS filter on DHW device (outdoor sensors physically on heating unit)
    assert not _should_publish_attribute("storage_dhw", attr_t4, 0.0)
    assert not _should_publish_attribute("storage_dhw", attr_avg, 0.0)
    assert not _should_publish_attribute("storage_dhw", attr_t4, 6.1)
    assert not _should_publish_attribute("storage_dhw", attr_avg, 6.2)

    # Should always publish on heating device (regardless of value)
    assert _should_publish_attribute("storage_heating", attr_t4, 0.0)
    assert _should_publish_attribute("storage_heating", attr_t4, 6.1)
    assert _should_publish_attribute("storage_heating", attr_avg, 0.0)
    assert _should_publish_attribute("storage_heating", attr_avg, 6.2)


def test_heat_pump_not_filtered():
    """HeatPump devices should not have any filtering applied."""
    attr = DeviceAttribute(
        device_class="HeatPump",
        method_name="outdoor_temperature",
        friendly_name="Outdoor Temperature",
        mqtt_topic_suffix="sensors/outdoor_temp",
        writable=False,
        ha_component="sensor",
        ha_config={},
    )

    # Heat pump should publish all attributes regardless of value
    assert _should_publish_attribute("heat_pump", attr, 0.0)
    assert _should_publish_attribute("heat_pump", attr, 4.2)


def test_none_values_not_published():
    """None values should always be filtered (no data available)."""
    attr = DeviceAttribute(
        device_class="StorageSystem",
        method_name="t1_temperature",
        friendly_name="T1 Temperature",
        mqtt_topic_suffix="sensors/t1_temp",
        writable=False,
        ha_component="sensor",
        ha_config={},
    )

    # None should be treated as "no data" and filtered
    # (Actually RULE 1 checks "value not in (..., None)" so it returns False first)
    assert not _should_publish_attribute("storage_heating", attr, None)
    assert not _should_publish_attribute("storage_dhw", attr, None)


def test_combined_unit_scenario():
    """Test strict device type filtering (heating-only vs DHW-only attributes)."""
    heating_attr = DeviceAttribute(
        device_class="StorageSystem",
        method_name="heating_actual",
        friendly_name="Heating Actual",
        mqtt_topic_suffix="sensors/heating_actual",
        writable=False,
        ha_component="sensor",
        ha_config={},
    )

    dhw_attr = DeviceAttribute(
        device_class="StorageSystem",
        method_name="hot_water_actual",
        friendly_name="Hot Water Actual",
        mqtt_topic_suffix="sensors/hot_water_actual",
        writable=False,
        ha_component="sensor",
        ha_config={},
    )

    # Heating device should publish heating attrs but NOT DHW attrs
    assert _should_publish_attribute("storage_heating", heating_attr, 25.5)
    assert _should_publish_attribute("storage_heating", heating_attr, 0.0)
    assert not _should_publish_attribute("storage_heating", dhw_attr, 44.7)
    assert not _should_publish_attribute("storage_heating", dhw_attr, 0.0)

    # DHW device should publish DHW attrs but NOT heating attrs
    assert _should_publish_attribute("storage_dhw", dhw_attr, 44.7)
    assert _should_publish_attribute("storage_dhw", dhw_attr, 0.0)
    assert not _should_publish_attribute("storage_dhw", heating_attr, 25.5)
    assert not _should_publish_attribute("storage_dhw", heating_attr, 0.0)


def test_all_heating_only_attributes():
    """Verify all heating-only attributes are always filtered on DHW devices."""
    heating_only_names = [
        "heating_setpoint",
        "heating_actual",
        "heating_circuit_setpoint",
        "heating_circuit_actual",
        "heating_circuit_status",
        "heating_circuit_operating_mode",
        "cooling_actual",
        "cooling_mode_active",
        "t4_temperature",
        "outdoor_temperature_avg",
    ]

    for method_name in heating_only_names:
        attr = DeviceAttribute(
            device_class="StorageSystem",
            method_name=method_name,
            friendly_name=method_name.replace("_", " ").title(),
            mqtt_topic_suffix=f"sensors/{method_name}",
            writable=False,
            ha_component="sensor",
            ha_config={},
        )

        # Should ALWAYS filter on DHW device (regardless of value)
        assert not _should_publish_attribute("storage_dhw", attr, 0.0), \
            f"{method_name} with value 0.0 should be filtered on storage_dhw"
        assert not _should_publish_attribute("storage_dhw", attr, 25.5), \
            f"{method_name} with non-zero value should be filtered on storage_dhw"

        # Should always publish on heating device (regardless of value)
        assert _should_publish_attribute("storage_heating", attr, 0.0), \
            f"{method_name} with value 0.0 should publish on storage_heating"
        assert _should_publish_attribute("storage_heating", attr, 25.5), \
            f"{method_name} with non-zero value should publish on storage_heating"


def test_all_dhw_only_attributes():
    """Verify all DHW-only attributes are always filtered on heating devices."""
    dhw_only_names = [
        "hot_water_setpoint",
        "hot_water_actual",
        "hot_water_setpoint_constant",
    ]

    for method_name in dhw_only_names:
        attr = DeviceAttribute(
            device_class="StorageSystem",
            method_name=method_name,
            friendly_name=method_name.replace("_", " ").title(),
            mqtt_topic_suffix=f"sensors/{method_name}",
            writable=False,
            ha_component="sensor",
            ha_config={},
        )

        # Should ALWAYS filter on heating device (regardless of value)
        assert not _should_publish_attribute("storage_heating", attr, 0.0), \
            f"{method_name} with value 0.0 should be filtered on storage_heating"
        assert not _should_publish_attribute("storage_heating", attr, 48.0), \
            f"{method_name} with non-zero value should be filtered on storage_heating"

        # Should always publish on DHW device (regardless of value)
        assert _should_publish_attribute("storage_dhw", attr, 0.0), \
            f"{method_name} with value 0.0 should publish on storage_dhw"
        assert _should_publish_attribute("storage_dhw", attr, 48.0), \
            f"{method_name} with non-zero value should publish on storage_dhw"


def test_temperature_sanity_checks():
    """Verify obviously wrong temperature values are filtered."""
    attr = DeviceAttribute(
        device_class="StorageSystem",
        method_name="outdoor_temperature_avg",
        friendly_name="Outdoor Temperature Average",
        mqtt_topic_suffix="sensors/outdoor_temp_avg",
        writable=False,
        ha_component="sensor",
        ha_config={},
    )

    # Normal temperature values should pass
    assert _should_publish_attribute("storage_heating", attr, 20.5)
    assert _should_publish_attribute("storage_heating", attr, -10.0)
    assert _should_publish_attribute("storage_heating", attr, 45.0)

    # Extreme but valid temperatures should pass
    assert _should_publish_attribute("storage_heating", attr, -49.0)
    assert _should_publish_attribute("storage_heating", attr, 99.0)

    # Obviously wrong temperatures should be filtered
    assert not _should_publish_attribute("storage_heating", attr, 5553.7), \
        "Temperature 5553.7°C should be filtered (clearly wrong)"
    assert not _should_publish_attribute("storage_heating", attr, 150.0), \
        "Temperature 150°C should be filtered (too hot)"
    assert not _should_publish_attribute("storage_heating", attr, -100.0), \
        "Temperature -100°C should be filtered (too cold)"
    assert not _should_publish_attribute("storage_heating", attr, 1000.0), \
        "Temperature 1000°C should be filtered (way too hot)"


def test_non_temperature_sensors_not_affected():
    """Verify non-temperature sensors are not affected by sanity checks."""
    attr = DeviceAttribute(
        device_class="StorageSystem",
        method_name="operating_hours_circuit_pump",
        friendly_name="Circuit Pump Operating Hours",
        mqtt_topic_suffix="sensors/circuit_pump_hours",
        writable=False,
        ha_component="sensor",
        ha_config={},
    )

    # Large values should be allowed for operating hours (not temperature)
    assert _should_publish_attribute("storage_heating", attr, 10000)
    assert _should_publish_attribute("storage_heating", attr, 50000)
