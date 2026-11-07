from bluetti_modbus_lib.devices.ep2000 import EP2000


def test_only_the_fields_tested_on_hardware_are_writable():
    # The schema declares many EP2000 settings writeable (switches, limits,
    # EMS controls); only these have taken a write on a real unit
    # (bluetti-registers#42), so only they are written.
    device = EP2000(None)

    writable = {n for n in device.field_names() if device.get_field(n).writable}

    assert writable == {
        "ac_o_switch",
        "g_i_switch",
        "g_o_switch",
        "b_soc_low",
        "b_soc_high",
    }


def test_soc_limits_keep_the_range_of_the_app():
    device = EP2000(None)

    for name in ("b_soc_low", "b_soc_high"):
        writable = device.get_field(name).writable
        assert (writable.min, writable.max) == (5, 100)
