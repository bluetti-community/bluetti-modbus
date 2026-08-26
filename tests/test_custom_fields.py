from enum import Enum, unique

from modbus_connection.model.fields import NumberField, StringField

from bluetti_modbus_lib.fields.custom_fields import BluettiStringField, FieldType, field
from bluetti_modbus_lib.fields.field_extras import (
    DeviceClass,
    FieldCategory,
    FieldStateClass,
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


def test_field_string():
    reg = field(FieldType.STRING, 20, length=8)

    assert isinstance(reg, StringField)
    assert reg.count == 8


def test_field_enum_decodes_the_raw_register_value():
    reg = field(FieldType.ENUM, 30, enum_type=_FakeStatus)

    assert isinstance(reg, NumberField)
    assert reg.decode([1]) is _FakeStatus.FAULT


def test_field_attaches_extras_when_provided():
    reg = field(
        FieldType.UINT16,
        40,
        category=FieldCategory.DIAGNOSTIC,
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.VOLTAGE,
    )

    assert reg.category is FieldCategory.DIAGNOSTIC
    assert reg.state_class is FieldStateClass.MEASUREMENT
    assert reg.device_class is DeviceClass.VOLTAGE


def test_field_without_extras_leaves_them_unset():
    reg = field(FieldType.UINT16, 41)

    assert getattr(reg, "category", None) is None
    assert getattr(reg, "state_class", None) is None
    assert getattr(reg, "device_class", None) is None
