from bluetti_modbus_lib.devices import EP2000, Balco260

# bluetti-registers documents each of these as spanning 2 registers - see
# import.py's WIDE_UINT_FIELDS for why field() previously silently dropped
# the second one (correct for a value under 65536, silently wrong above it).
_WIDE_FIELDS = (
    "g_i_p_local",
    "ac_o_p_local",
    "pv_i_p_local",
    "pv_ac_p_local",
    "g_i_e_local",
    "g_o_e_local",
    "ac_o_e_local",
    "pv_i_e_local",
    "pv_ac_e_local",
    "b_protect",
    "b_alarm_portable",
)


def test_balco260_wide_uint_fields_read_both_registers():
    device = Balco260(None)

    for name in _WIDE_FIELDS:
        field = device.get_field(name)
        assert field is not None, name
        assert field.count == 2, f"{name} should span 2 registers"


def test_ep2000_shares_the_same_fix():
    # EP2000 shares these exact field names/addresses with Balco260 (see
    # test_ep2000_shares_balco260s_confirmed_addresses) - fixed "for free"
    # by the same content+name-driven generator rule.
    device = EP2000(None)

    for name in _WIDE_FIELDS:
        field = device.get_field(name)
        assert field is not None, name
        assert field.count == 2, f"{name} should span 2 registers"


def test_ep2000_only_sunspec_style_fields_are_left_untouched():
    # Deliberately NOT widened: these are EP2000-exclusive, SunSpec/DER-
    # style registers (unconfirmed against real hardware) - possibly a
    # mantissa+scale-factor pair rather than one plain wide integer, so
    # widening them the same way would be a guess, not a verified fix.
    device = EP2000(None)

    for name in (
        "g_1_p_active",
        "g_1_p_reactive",
        "g_1_p_apparent",
        "d_p_active_target_l1",
        "d_export_limit",
        "d_storage_set_point",
        "b_p",
    ):
        field = device.get_field(name)
        assert field is not None, name
        assert field.count == 1, f"{name} was widened unexpectedly"


def test_g_i_p_local_decodes_both_registers_little_endian():
    # Direct proof the fix produces the right number, not just the right
    # count: a value that only fits across 2 registers (100_000 W - clearly
    # synthetic, but demonstrates the low+high combination that a value
    # under 65536 could never distinguish from the old, silently-truncated
    # behaviour).
    device = Balco260(None)
    field = device.get_field("g_i_p_local")
    assert field is not None

    low = 100_000 & 0xFFFF
    high = 100_000 >> 16
    assert field.decode([low, high]) == 100_000


def test_b_error_stays_truncated_to_one_register_for_now():
    # b_error is documented as 3 registers (bluetti-registers'
    # MULTI_REGISTER_FIELD_LENGTHS), but there's no 3-register FieldType and
    # it's an already-undecoded raw bitmap with no displayed value to check
    # a fix against - left as a known, separate limitation.
    device = Balco260(None)
    field = device.get_field("b_error")
    assert field is not None
    assert field.count == 1
