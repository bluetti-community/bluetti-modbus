from bluetti_modbus_lib.devices import Balco260


def test_field_names_and_get_sensors_are_the_same_view():
    device = Balco260(None)

    assert list(device.field_names()) == list(device.get_sensors())
    assert len(list(device.field_names())) > 0


def test_get_field_returns_the_registered_field():
    device = Balco260(None)
    name = next(iter(device.field_names()))

    assert device.get_field(name) is not None


def test_get_field_returns_none_for_unknown_field():
    device = Balco260(None)

    assert device.get_field("not_a_real_field") is None


def test_values_is_empty_before_any_update():
    device = Balco260(None)

    assert device.values == {}


def test_values_returns_a_copy_not_a_live_reference():
    device = Balco260(None)

    values = device.values
    values["injected"] = 1

    assert "injected" not in device.values
