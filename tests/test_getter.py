from bluetti_modbus_lib.devices import (
    AC200L,
    AC500,
    EP500P,
    EP2000,
    FP,
    Balco260,
    Balco500,
    Balcotrans,
    SMeter,
)
from bluetti_modbus_lib.devices.getter import get_device


def test_get_device_ac200l():
    assert isinstance(get_device("ac200l"), AC200L)


def test_get_device_balcotrans():
    assert isinstance(get_device("balcotrans"), Balcotrans)


def test_get_device_ac500():
    assert isinstance(get_device("ac500"), AC500)


def test_get_device_balco260():
    assert isinstance(get_device("balco260"), Balco260)


def test_get_device_balco500():
    assert isinstance(get_device("balco500"), Balco500)


def test_get_device_ep500p():
    assert isinstance(get_device("ep500p"), EP500P)


def test_get_device_fp():
    assert isinstance(get_device("fp"), FP)


def test_fp_is_the_full_balco_set_plus_dc_switch_read_only():
    # A real FridgePower answered the whole Balco 260 profile and then the
    # whole Balco 500 one - BLUETTI's full BalcoXX set, the twelve
    # registers the Balco 260 never fills included (bluetti-registers#38,
    # #40): same fields, same addresses, same widths, plus the DC output
    # switch - and nothing writable, no write having been tested there.
    # The Balco 260's own max_span stays with it out of caution: that
    # device's Modbus stack failed on wide blocks months apart, and one
    # good read at 50 on a sibling proves nothing about that. Catches the
    # generated file drifting from that.
    balco500 = get_device("balco500")
    balco260 = get_device("balco260")
    fp = get_device("fp")
    assert balco500 is not None and balco260 is not None
    assert fp is not None

    assert set(fp.field_names()) >= set(balco500.field_names()) | {"dc_o_switch"}
    assert set(fp.field_names()) >= set(balco260.field_names())
    for name in balco500.field_names():
        assert fp.get_field(name).address == balco500.get_field(name).address, name
        assert fp.get_field(name).count == balco500.get_field(name).count, name
    assert fp.max_span == balco260.max_span == 20
    # Writes tested on a real unit (bluetti-registers#38): the DC output and
    # grid charging switches take them, the SOC thresholds refuse them, the
    # AC output and grid feed-in switches are untried.
    assert {n for n in fp.field_names() if fp.get_field(n).writable} == {
        "dc_o_switch",
        "g_i_switch",
    }
    # The unit's pack voltage is 0.01 V, not the Balco 260's 0.1 (raw 2007
    # = 20.07 V for a 6-cell pack); its per-phase grid power is signed.
    assert fp.get_field("b_v_total").scale == 0.01
    assert fp.get_field("b_v").scale == 0.01
    assert fp.get_field("g_1_i_p").signed and not balco260.get_field("g_1_i_p").signed
    assert fp.get_field("g_i_p_local").signed


def test_ep500p_is_ac500s_register_set_with_read_only_thresholds():
    # EP500P's profile is AC500's register set, read on two real units with
    # the AC500 class (bluetti-registers#35): same fields, same addresses,
    # same decode, including the SOC thresholds at AC200L's addresses -
    # which refuse a write on this device, so they are read-only, unlike
    # Balco 260's. The two output switches are the only writable fields (switched
    # on real hardware); g_i_switch is not, unlike AC500's - it reads a real
    # state there. Catches the generated file drifting from that.
    ac500 = get_device("ac500")
    ep500p = get_device("ep500p")
    assert ac500 is not None
    assert ep500p is not None

    # AC500 gained the same two thresholds later (bluetti-registers#41), so
    # the two sets are now identical, and so are their read plans.
    assert set(ep500p.field_names()) == set(ac500.field_names())
    assert ep500p.register_ranges == ac500.register_ranges

    def writable(device):
        return {n for n in device.field_names() if device.get_field(n).writable}

    assert writable(ac500) == {"ac_o_switch", "dc_o_switch"}
    assert writable(ep500p) == {"ac_o_switch", "dc_o_switch"}


def test_balco500_shares_balco260s_addresses_for_every_field_it_has():
    # Balco 500 is documented under the exact same "BalcoXX" tab as
    # Balco260 in BLUETTI's own official register spec, not a separate
    # section - every field it DOES have should match Balco260's address
    # exactly, same idea as EP2000's own superset test.
    balco260 = get_device("balco260")
    balco500 = get_device("balco500")
    assert balco260 is not None
    assert balco500 is not None

    # Balco260 dropped twelve registers its firmware never populates
    # (bluetti-registers#30, confirmed by BLUETTI) - Balco500 keeps them
    # until its own hardware says otherwise, so they are the only fields
    # allowed to be on Balco500 and not on Balco260.
    only_on_balco500 = set(balco500.field_names()) - set(balco260.field_names())
    assert only_on_balco500 == {
        "ac_o_e_local",
        "ac_o_p_local",
        "b_t_avg",
        "b_time_to_empty",
        "b_time_to_full",
        "d_self_consumption",
        "g_i_e_local",
        "g_i_p_local",
        "g_o_e_local",
        "pv_ac_e_local",
        "pv_ac_p_local",
        "pv_i_e_local",
    }
    for name in set(balco500.field_names()) - only_on_balco500:
        assert balco500.get_field(name).address == balco260.get_field(name).address


def test_balco500_has_only_one_pv_string_unlike_balco260s_four():
    # The official datasheet (Balco_500_datasheet_en_V1.0.pdf, PV Input
    # section) states "MPPT Trackers: 1 / 1" - pv_2/pv_3/pv_4 (Balco260's
    # other 3 PV string inputs) don't apply here. A real error in an
    # earlier version of this device (bluetti-community/bluetti-registers#28)
    # copied Balco260's row wholesale, including all 4.
    balco500 = get_device("balco500")
    assert balco500 is not None

    names = set(balco500.field_names())
    assert "pv_1_i_type" in names
    for n in range(2, 5):
        assert f"pv_{n}_i_type" not in names


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
