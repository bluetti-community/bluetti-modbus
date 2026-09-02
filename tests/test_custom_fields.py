from enum import Enum, unique

import pytest
from modbus_connection.model.fields import FloatField, NumberField, StringField

from bluetti_modbus_lib.fields.custom_fields import (
    BluettiStringField,
    FieldType,
    bit_flag,
    field,
    reference_offset_current,
)


@unique
class _FakeStatus(Enum):
    OK = 0
    FAULT = 1


def test_bluetti_string_field_round_trips_ascii():
    f = BluettiStringField(0, count=4, stride=0, writable=False, force_fc16=False)

    words = f.encode("SN123")
    assert f.decode(words) == "SN123"


def test_bluetti_string_field_decode_strips_null_padding():
    f = BluettiStringField(0, count=4, stride=0, writable=False, force_fc16=False)

    # "AB" packed little-endian into a single word, the rest zero-padded.
    words = [0x4241, 0x0000, 0x0000, 0x0000]
    assert f.decode(words) == "AB"


def test_field_uint16_and_int16():
    unsigned = field(FieldType.UINT16, 10)
    signed = field(FieldType.INT16, 11)

    assert isinstance(unsigned, NumberField)
    assert unsigned.signed is False
    assert isinstance(signed, NumberField)
    assert signed.signed is True


def test_field_uint32():
    reg = field(FieldType.UINT32, 12, scale=0.1)

    assert isinstance(reg, NumberField)
    assert reg.count == 2


def test_field_uint64_decodes_a_real_serial_number():
    reg = field(FieldType.UINT64, 50206)

    assert isinstance(reg, NumberField)
    assert reg.count == 4
    # Confirmed by BLUETTI support: registers 50206-50209 combine, little
    # endian, into the serial number's numeric part.
    assert reg.decode([0x39FD, 0xF249, 0x025F, 0x0000]) == 2611110033917


def test_field_float32():
    reg = field(FieldType.FLOAT32, 13)

    assert isinstance(reg, FloatField)
    assert reg.count == 2


def test_field_string():
    reg = field(FieldType.STRING, 20, length=8)

    assert isinstance(reg, StringField)
    assert reg.count == 8


def test_field_enum_decodes_the_raw_register_value():
    reg = field(FieldType.ENUM, 30, enum_type=_FakeStatus)

    assert isinstance(reg, NumberField)
    assert reg.decode([1]) is _FakeStatus.FAULT


def test_reference_offset_current_decodes_magnitude_around_the_reference():
    # Raw values captured from a real device (issue #8): while charging at
    # ~1000W solar in, b_c read 30335 and b_c_total (already correct) read
    # 33.4A at the same moment - the fixed formula should land close to that.
    reg = reference_offset_current(51220, reference=30000)

    assert isinstance(reg, NumberField)
    assert reg.decode([30335]) == pytest.approx(33.5)
    # Below the reference (discharging) decodes to the same kind of magnitude.
    assert reg.decode([29500]) == pytest.approx(50.0)
    assert reg.decode([30000]) == 0


def test_bit_flag_decodes_only_the_named_bit():
    # d_status (S Meter, 55111): bit0/1 "reserved" per the official spec,
    # bit2 online status.
    reg = bit_flag(55111, bit=2)

    assert isinstance(reg, NumberField)
    assert reg.decode([0]) is False
    assert reg.decode([0b100]) is True
    # Reserved bits set alongside bit2 don't change the result - only bit2
    # is examined, nothing is assumed about the rest.
    assert reg.decode([0b111]) is True
    assert reg.decode([0b011]) is False
