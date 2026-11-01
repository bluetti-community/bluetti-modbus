from bluetti_modbus_lib.devices.ep2000 import EP2000


def test_only_the_switches_tested_on_hardware_are_writable():
    # The schema declares many EP2000 settings writeable (switches, limits,
    # EMS controls); only the AC output and feed-in switches have taken a
    # write on a real unit (bluetti-registers#42), so only they are written.
    device = EP2000(None)

    writable = {n for n in device.field_names() if device.get_field(n).writable}

    assert writable == {"ac_o_switch", "g_o_switch"}
