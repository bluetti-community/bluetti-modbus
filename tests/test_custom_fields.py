from enum import Enum, unique

from modbus_connection.model.fields import FloatField, NumberField, StringField

from bluetti_modbus_lib.fields.custom_fields import BluettiStringField, FieldType, field


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
