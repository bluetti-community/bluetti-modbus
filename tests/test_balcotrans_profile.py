"""What the Balco Transfer Hub profile is, and is not.

Read from four probe runs on two hubs in opposite states, one charging a
power station through its socket and one feeding the grid, each value
checked against the BLUETTI app (bluetti-registers#29).
"""

from bluetti_modbus_lib.devices.balcotrans import Balcotrans


def _device() -> Balcotrans:
    return Balcotrans(None)


def test_the_hub_serves_no_writable_register():
    # The whole settings block (57001-57017) is unanswered on this
    # firmware, so the profile is read-only - a paired S Meter does not
    # change that either.
    device = _device()

    assert not any(
        device.get_field(name).writable  # type: ignore[union-attr]
        for name in device.field_names()
    )


def test_the_inverter_total_is_signed():
    # 50008 read fcae ffff while the app showed 851 W of charging: -850 W.
    # Direction as well as magnitude, which an unsigned field would lose.
    field = _device().get_field("d_inverter_total")

    assert field is not None
    assert field.decode([0xFCAE, 0xFFFF]) == -850


def test_the_fields_confirmed_against_the_app_are_there():
    device = _device()

    addresses = {name: device.get_field(name).address for name in device.field_names()}  # type: ignore[union-attr]

    assert addresses["ac_1_o_p"] == 50245  # the charging flow, 851 W exact
    assert addresses["g_1_i_p"] == 50235  # the feed-in flow
    assert addresses["d_inverter_1_status"] == 50255  # 2 charging, 5 feeding
    assert addresses["b_soc_total"] == 51004  # the connected station's SOC
    assert addresses["pv_i_p_total"] == 50004  # the station's PV
    assert addresses["d_ver_arm"] == 50210


def test_the_registers_that_never_moved_are_left_out():
    # Energy counters, the totals that stayed at zero in both states, the
    # pack block (the hub has no battery of its own) and the blocks the
    # firmware does not serve at all.
    names = set(_device().field_names())

    assert not names & {
        "ac_o_e_total",
        "pv_i_e_total",
        "g_i_e_total",
        "g_o_e_total",
        "g_i_p_total",
        "pv_i_p_local",
        "b_soc",
        "b_v",
        "b_type",
        "d_num_battery_packs",
        "d_iot_ver",
        "ac_o_switch",
        "g_i_switch",
        "g_o_switch",
        "b_soc_low",
        "b_soc_high",
    }


def test_every_read_covers_exactly_one_field():
    # A hub answers a block read with a word inserted partway through and
    # the rest shifted one register late: asked for 5 registers at 50210 it
    # returned [63089, 4584, 2, 7550, 4585] where the same addresses read
    # one at a time give [63089, 4584, 7550, 4585, 499]
    # (bluetti-registers#29). Every reading that matched the app was taken
    # field by field, so that is how the profile reads it.
    device = _device()
    fields = {
        (f.address, f.count)
        for f in (device.get_field(n) for n in device.field_names())
        if f is not None
    }

    assert set(device._build_plan().blocks["holding"]) == fields


def test_the_battery_voltage_is_the_stations_own_scale():
    # Raw 5350 is 53.50 V, the connected station's pack - not 535 V.
    field = _device().get_field("b_v_total")

    assert field is not None
    assert field.decode([5350]) == 53.5
