from bluetti_modbus_lib.devices import AC500, EP2000, Balco260, Balco500, SMeter
from bluetti_modbus_lib.devices.getter import get_device


def test_get_device_ac500():
    assert isinstance(get_device("ac500"), AC500)


def test_get_device_balco260():
    assert isinstance(get_device("balco260"), Balco260)


def test_get_device_balco500():
    assert isinstance(get_device("balco500"), Balco500)


def test_balco500_field_set_is_identical_to_balco260():
    # Unlike EP2000 (a superset) or AC500 (a narrower, independently
    # confirmed set), Balco 500 is documented under the exact same "BalcoXX"
    # tab as Balco260 in BLUETTI's own official register spec - not a
    # separate section. Every field name and address should match exactly,
    # not just overlap.
    balco260 = get_device("balco260")
    balco500 = get_device("balco500")
    assert balco260 is not None
    assert balco500 is not None

    assert set(balco260.field_names()) == set(balco500.field_names())
    for name in balco260.field_names():
        assert balco500.get_field(name).address == balco260.get_field(name).address


def test_balco500_writable_fields_stay_read_only_pending_confirmation():
    # Same policy as EP2000: unconfirmed against real hardware, so nothing
    # here is marked writable yet, even though the schema documents these
    # as writable on Balco260 (see import.py's own device-name gate).
    device = get_device("balco500")
    assert device is not None

    for name in ("ac_o_switch", "g_i_switch", "g_o_switch", "b_soc_low", "b_soc_high"):
        assert device.get_field(name).writable is False


def test_get_device_ep2000():
    assert isinstance(get_device("ep2000"), EP2000)


def test_ep2000_shares_balco260s_confirmed_addresses():
    # EP2000's register map is a strict superset of Balco260's, sourced from
    # BLUETTI's own official register spec (bluetti-registers PR ingesting
    # bluetti-official/bluetti-modbus-tcp-slave's Cassandra Protocol doc) -
    # every address the two devices share should decode identically.
    balco260 = get_device("balco260")
    ep2000 = get_device("ep2000")
    assert balco260 is not None
    assert ep2000 is not None

    for name in balco260.field_names():
        balco_field = balco260.get_field(name)
        ep2000_field = ep2000.get_field(name)
        assert ep2000_field is not None, f"EP2000 is missing {name}"
        assert ep2000_field.address == balco_field.address


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
