"""Tests for bluetti-modwrite's validation, the part that runs before any I/O."""

import pytest
from probatio import Range

from bluetti_modbus_lib.devices import Balco260
from bluetti_modbus_lib.scripts.bluetti_modwrite import (
    WriteRefused,
    prepare_write,
    writable_fields,
)


def _device() -> Balco260:
    return Balco260(None)


def test_writable_fields_are_the_ones_the_profile_declares():
    assert writable_fields(_device()) == [
        "ac_o_switch",
        "g_i_switch",
        "g_o_switch",
        "b_soc_low",
        "b_soc_high",
    ]


def test_an_unknown_field_is_refused_and_names_the_writable_ones():
    with pytest.raises(WriteRefused, match="not a field of this device") as err:
        prepare_write(_device(), "b_soc_maximum", "90", allow_ac_output=False)

    assert "b_soc_high" in str(err.value)


def test_a_read_only_field_is_refused_and_names_the_writable_ones():
    with pytest.raises(WriteRefused, match="read-only") as err:
        prepare_write(_device(), "b_soc", "90", allow_ac_output=False)

    assert "b_soc_high" in str(err.value)


def test_a_value_outside_the_declared_range_is_refused_with_the_bounds():
    # Balco260's b_soc_low is Range(5, 90) - the device's own limits, so
    # they are reported rather than discovered by the device rejecting it.
    device = _device()
    assert isinstance(device.get_field("b_soc_low").writable, Range)

    with pytest.raises(WriteRefused, match="outside what") as err:
        prepare_write(device, "b_soc_low", "95", allow_ac_output=False)

    assert "5" in str(err.value)
    assert "90" in str(err.value)


def test_a_value_inside_the_range_is_accepted():
    field, value = prepare_write(_device(), "b_soc_low", "20", allow_ac_output=False)

    assert field.address == 57016
    assert value == 20


def test_a_value_that_is_not_a_number_is_refused():
    with pytest.raises(WriteRefused, match="whole number"):
        prepare_write(_device(), "b_soc_low", "twenty", allow_ac_output=False)


def test_the_ac_output_switch_needs_its_own_flag():
    with pytest.raises(WriteRefused, match="AC output switch"):
        prepare_write(_device(), "ac_o_switch", "1", allow_ac_output=False)

    field, value = prepare_write(_device(), "ac_o_switch", "1", allow_ac_output=True)
    assert (field.address, value) == (57001, 1)


def test_an_enum_field_takes_a_member_name_or_its_number(monkeypatch):
    # No shipped profile declares a writable enum yet (a mode or selector
    # would be the first), so the parsing is exercised on a field made
    # writable here - the same object field() builds for one.
    from enum import IntEnum

    from bluetti_modbus_lib.fields import FieldType
    from bluetti_modbus_lib.fields import field as make_field

    class Mode(IntEnum):
        STANDARD = 0
        BACKUP = 3

    device = _device()
    reg = make_field(FieldType.ENUM, 2005, enum_type=Mode, writable=True)
    monkeypatch.setattr(
        device, "get_field", lambda name: reg if name == "mode" else None
    )

    assert (
        prepare_write(device, "mode", "BACKUP", allow_ac_output=False)[1] is Mode.BACKUP
    )
    assert prepare_write(device, "mode", "3", allow_ac_output=False)[1] is Mode.BACKUP


def test_an_unknown_enum_value_lists_what_the_field_accepts(monkeypatch):
    from enum import IntEnum

    from bluetti_modbus_lib.fields import FieldType
    from bluetti_modbus_lib.fields import field as make_field

    class Mode(IntEnum):
        STANDARD = 0
        BACKUP = 3

    device = _device()
    reg = make_field(FieldType.ENUM, 2005, enum_type=Mode, writable=True)
    monkeypatch.setattr(
        device, "get_field", lambda name: reg if name == "mode" else None
    )

    with pytest.raises(WriteRefused, match="not one of this field's values") as err:
        prepare_write(device, "mode", "TURBO", allow_ac_output=False)

    assert "BACKUP=3" in str(err.value)
