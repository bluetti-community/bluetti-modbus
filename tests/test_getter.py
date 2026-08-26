from bluetti_modbus_lib.devices import EP2000, Balco260
from bluetti_modbus_lib.devices.getter import get_device


def test_get_device_balco260():
    assert isinstance(get_device("balco260"), Balco260)


def test_get_device_ep2000():
    assert isinstance(get_device("ep2000"), EP2000)


def test_get_device_unknown_type_returns_none():
    assert get_device("not-a-real-device") is None
