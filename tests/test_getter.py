from bluetti_modbus_lib.devices import Balco260, SMeter
from bluetti_modbus_lib.devices.getter import get_device


def test_get_device_balco260():
    assert isinstance(get_device("balco260"), Balco260)


def test_balco260_serial_and_firmware_version_addresses():
    # Confirmed addresses from BLUETTI support - see bluetti-registers#11.
    device = get_device("balco260")
    assert device is not None

    assert device.get_field("d_serial").address == 50206
    assert device.get_field("d_ver_arm").address == 50210
    assert device.get_field("d_ver_dsp").address == 50212


def test_get_device_smeter():
    assert isinstance(get_device("smeter"), SMeter)


def test_get_device_unknown_type_returns_none():
    assert get_device("not-a-real-device") is None
