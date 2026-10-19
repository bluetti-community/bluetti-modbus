from bluetti_modbus_lib.devices.ep2000 import EP2000


def test_only_the_grid_feed_in_switch_is_writable():
    # The schema declares many EP2000 settings writeable (switches, limits,
    # EMS controls); only the feed-in switch has taken a write on a real
    # unit (bluetti-registers#42), so it is the only one the library writes.
    device = EP2000(None)

    writable = {n for n in device.field_names() if device.get_field(n).writable}

    assert writable == {"g_o_switch"}
