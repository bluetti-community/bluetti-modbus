from enum import Enum, unique
from typing import Any

from modbus_connection.model import (
    RegisterField,
    WriteValidator,
    enum,
    float32,
    int32,
    uint32,
)
from modbus_connection.model.fields import NumberField, StringField


class BluettiStringField(StringField):
    def decode(self, words: list[int], scale_exponent: int | None = None) -> str:
        raw = b"".join((w & 0xFFFF).to_bytes(2, "little") for w in words)
        return raw.decode("ascii", errors="ignore").rstrip("\x00")

    def encode(self, value: Any, scale_exponent: int | None = None) -> list[int]:
        length = self.count
        raw = str(value).encode("ascii", errors="ignore")[: length * 2]
        raw = raw.ljust(length * 2, b"\x00")
        return [int.from_bytes(raw[i : i + 2], "little") for i in range(0, len(raw), 2)]


def uint16(
    address: int,
    *,
    scale: float = 1.0,
    writable: bool | WriteValidator = False,
    unit: str | None = None,
) -> NumberField[Any]:
    return NumberField(
        address,
        scale=scale,
        word_order="little",
        signed=False,
        writable=writable,
        unit=unit,
    )


def int16(
    address: int,
    *,
    scale: float = 1.0,
    writable: bool | WriteValidator = False,
    unit: str | None = None,
) -> NumberField[Any]:
    return NumberField(
        address,
        scale=scale,
        word_order="little",
        signed=True,
        writable=writable,
        unit=unit,
    )


def bluetti_string(
    address: int,
    length: int,
) -> BluettiStringField:
    return BluettiStringField(
        address,
        count=length,
        stride=0,
        writable=False,
        force_fc16=False,
    )


def reference_offset_current(
    address: int,
    *,
    reference: int,
    unit: str = "A",
) -> NumberField[Any]:
    """A current reported as a magnitude relative to a fixed reference point.

    Confirmed by BLUETTI support for ``b_c`` (address 51220): raw values
    below the reference mean discharging, above mean charging, but only the
    magnitude is available at this register - the direction isn't encoded
    here (see https://github.com/bluetti-community/bluetti-modbus/issues/8).
    """
    return NumberField(
        address,
        convert=lambda raw: abs(raw - reference) * 0.1,
        word_order="little",
        unit=unit,
    )


def dotted_version(address: int) -> NumberField[Any]:
    """A firmware/protocol version packed as major*10000 + minor*100 + patch.

    Confirmed against real hardware across 4 independent samples on a
    Balco 260 (BMS, ARM, DSP, and IoT module firmware versions, all
    matching what the Bluetti app shows) - see
    https://github.com/bluetti-community/bluetti-registers/pull/11 for the
    "version" content type this applies to.
    """

    def decode(raw: int) -> str:
        major = raw // 10000
        minor = (raw // 100) % 100
        patch = raw % 100
        return f"{major}.{minor:02d}.{patch:02d}"

    return NumberField(
        address,
        count=2,
        convert=decode,
        word_order="little",
    )


def bit_flag(address: int, *, bit: int) -> NumberField[Any]:
    """A single documented bit inside an otherwise-undocumented register.

    Only the named bit's meaning is decoded - every other bit is left alone
    (not assumed to be always 0), so this only exists for registers where
    the official spec documents exactly one bit and marks the rest
    "reserved" (unlike this library's more complex, genuinely multi-bit
    status/bitmap registers, which stay raw uints - see e.g. bluetti-
    registers' UNDECODED_BITMAP_FIELDS).
    """
    return NumberField(
        address,
        convert=lambda raw: bool(raw & (1 << bit)),
        word_order="little",
    )


def nibble(address: int, *, high: bool) -> NumberField[Any]:
    """One documented 4-bit nibble (0-15) of an otherwise packed register.

    Like bit_flag() but for a 4-bit count instead of a single bit - see its
    docstring. pv_dc_count/pv_ac_count (Balco260/EP2000, both address 50267,
    "PV connection quantity per inverter") are the confirmed case: bit0-3 is
    the low nibble (high=False), bit4-7 is the high nibble (high=True), per
    the official register spec's own remark column.
    """
    shift = 4 if high else 0
    return NumberField(
        address,
        convert=lambda raw: (raw >> shift) & 0xF,
        word_order="little",
    )


def uint64(
    address: int,
    *,
    writable: bool | WriteValidator = False,
    unit: str | None = None,
) -> NumberField[Any]:
    return NumberField(
        address,
        count=4,
        word_order="little",
        signed=False,
        writable=writable,
        unit=unit,
    )


@unique
class FieldType(Enum):
    INT16 = "int16"
    UINT16 = "uint16"
    INT32 = "int32"
    UINT32 = "uint32"
    UINT64 = "uint64"
    FLOAT32 = "float32"
    STRING = "str"
    ENUM = "enum"


def field(
    t: FieldType,
    address: int,
    *,
    scale: float = 1.0,
    writable: bool | WriteValidator = False,
    unit: str | None = None,
    length: int = 1,
    count: int = 1,
    enum_type: type[Enum] | None = None,
) -> RegisterField[Any]:
    match t:
        case FieldType.INT16:
            return int16(address, scale=scale, writable=writable, unit=unit)
        case FieldType.UINT16:
            return uint16(address, scale=scale, writable=writable, unit=unit)
        case FieldType.INT32:
            return int32(
                address, scale=scale, writable=writable, unit=unit, word_order="little"
            )
        case FieldType.UINT32:
            return uint32(
                address, scale=scale, writable=writable, unit=unit, word_order="little"
            )
        case FieldType.UINT64:
            return uint64(address, writable=writable, unit=unit)
        case FieldType.FLOAT32:
            return float32(
                address, scale=scale, writable=writable, unit=unit, word_order="little"
            )
        case FieldType.STRING:
            return bluetti_string(address, length)
        case FieldType.ENUM:
            # Every real caller (balco260.py) passes enum_type for
            # FieldType.ENUM - the None default only exists because the
            # other FieldTypes don't use this parameter at all.
            assert enum_type is not None, "FieldType.ENUM requires enum_type"
            return enum(address, enum_type, count=count, word_order="little")
