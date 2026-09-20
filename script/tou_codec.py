"""Codec for the Balco family's time-of-use (TOU) scheduler records and the
two registers behind its working modes - the BLUETTI app's own internal
register space, NOT the documented Modbus TCP map.

Provisional: a companion to a hardware test on a Balco 260, not a library
feature. Nothing here talks to a device; `balco_modes_probe.py` (next to
this file) does, and only on an owner's explicit go.

Everything below is transcribed from the decompiled BLUETTI Android app
3.1.4 (`net.poweroak.bluetticloud`):

- `ui.connectv2.bean.DeviceTouTime.timeToRegs()` - the wire format of one
  scheduler record: a 5-register, 80-bit field packed least-significant
  bit first (register k holds bits 16k..16k+15, bit 0 = bit 0 of register
  0), followed by two plain registers. Field layout, in bit offsets:

      secondsOfDay     0..16   (17 bits, 0..86399)
      weekMask        17..23   ( 7 bits, Sunday = 0x01 ... Saturday = 0x40)
      dayOfMonthMask  24..54   (31 bits, bit 0 = the 1st)
      monthMask       55..66   (12 bits, bit 0 = January)
      regType         67..68   ( 2 bits)
      targetId        69..76   ( 8 bits)
      timeType        77..79   ( 3 bits)
      +5  targetReg            the internal register the record writes
      +6  targetValue          the value it writes there

  A record is therefore "at secondsOfDay, on the days the three masks
  allow, write targetValue to targetReg" - a generic scheduler. The app
  recognises AC_SWITCH (2011) and DC_SWITCH (2012) as targets
  (`isAC()`/`isDC()`); which register a power plan targets is set by the
  port picked in the UI (`PortFilterSpec.getTargetReg()`), not read yet.
- `ui.connectv2.tools.ProtocolAddrV2`: TOU_CTRL_ENABLE = 26000, TOU_CTRL =
  26001 (table start), WORKING_MODE = 2005, EMS_CTRL_MODE_SET = 2241,
  SOC_SET_LOW = 2075, SOC_SET_HIGH = 2083.
- `ui.connect.activity.DeviceBalcoTimePlanAddActivity`: one UI time range
  occupies 14 registers (`startAddr + position * 14`) - two records, a
  start and an end, told apart by timeType. Which timeType value means
  which was NOT decompiled (`executeNewPlan$3` failed in JADX), so the
  period helpers here take both values explicitly: the first thing a real
  device has to say. The three repeat types fill the masks as
  `executeNewPlan()` does: once = all three masks 0; weekly = the chosen
  days, every day of the month (0x7FFFFFFF), every month (0xFFF); dates =
  every weekday (0x7F), the chosen days and their month - the app keeps
  only the month holding the most selected dates.
- `ui.connectv2.tools.TouTimeCtrlParser.parseTouTimeExt()`: the device
  sends these registers with their two bytes swapped relative to the rest
  of the protocol (`littleEndianToBigEndian` on the way in), hence
  `swap_bytes()` and `decode_table(..., byte_order="auto")`.
- `ui.connect.WorkingMode`: the values of register 2005; three constants
  overlap (ZERO_UPS is also 3, V2_STANDARD_UPS_OFFLINE is also 4) and the
  app picks the reading by protocol version and device category - the
  Balco fragment only ever writes 1, 2 and 3.
- `ui.connectv2.tools.EmsCtrlMode` via `applyAiCtrlMode()`: 2241 <- 8
  enables the AI mode, <- 0 disables it (the app also calls the cloud's
  `aiModelEnabled` - writing 8 locally gives the mode without the
  scheduler behind it). 3/4/5 are voltkeeper's names, not confirmed here.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import IntEnum

# ProtocolAddrV2 - the app's internal register space.
WORKING_MODE = 2005
AC_SWITCH = 2011
DC_SWITCH = 2012
SOC_SET_LOW = 2075
SOC_SET_HIGH = 2083
EMS_CTRL_MODE_SET = 2241
TOU_CTRL_ENABLE = 26000
TOU_CTRL = 26001

RECORD_REGISTERS = 7
BITFIELD_REGISTERS = 5
PERIOD_REGISTERS = 2 * RECORD_REGISTERS  # one UI time range = start + end

SECONDS_PER_DAY = 86400

# Sunday first, as TouTimeCtrlParser.weekMask() has it.
SUNDAY, MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY = (
    1 << i for i in range(7)
)
EVERY_WEEKDAY = 0x7F
EVERY_DAY_OF_MONTH = 0x7FFFFFFF
EVERY_MONTH = 0xFFF

# (name, bit offset, width) - DeviceTouTime.timeToRegs(), in order.
_FIELDS: tuple[tuple[str, int, int], ...] = (
    ("seconds_of_day", 0, 17),
    ("week_mask", 17, 7),
    ("day_of_month_mask", 24, 31),
    ("month_mask", 55, 12),
    ("reg_type", 67, 2),
    ("target_id", 69, 8),
    ("time_type", 77, 3),
)


class WorkingMode(IntEnum):
    """Register 2005. Aliases are the app's overlapping constants."""

    CUSTOMIZED_UPS = 1  # "custom"
    PV_PRIORITY_UPS = 2  # "self_use"
    STANDARD_UPS = 3  # "backup" - the Balco fragment's reading of 3
    ZERO_UPS = 3  # alias: the same value under another protocol/category
    TIME_CTRL_UPS = 4
    V2_STANDARD_UPS_OFFLINE = 4  # alias, same caveat
    V2_TIME_CTRL_UPS = 5
    SELF_CONSUMPTION_EXPORT = 11


class EmsCtrlMode(IntEnum):
    """Register 2241. Only DISABLE and AI are read from the app's code."""

    DISABLE = 0
    CLOUD = 3
    LOCAL = 4
    DYNAMIC_PRICE = 5
    AI = 8


def _check_width(name: str, value: int, width: int) -> None:
    if not 0 <= value < (1 << width):
        raise ValueError(f"{name}={value} does not fit in {width} bits")


def _check_register(name: str, value: int) -> None:
    if not 0 <= value <= 0xFFFF:
        raise ValueError(f"{name}={value} is not a 16-bit register value")


@dataclass(frozen=True)
class TouEvent:
    """One 7-register scheduler record - DeviceTouTime's wire fields."""

    seconds_of_day: int
    week_mask: int = 0
    day_of_month_mask: int = 0
    month_mask: int = 0
    reg_type: int = 0
    target_id: int = 0
    time_type: int = 0
    target_reg: int = 0
    target_value: int = 0

    def __post_init__(self) -> None:
        for name, _offset, width in _FIELDS:
            _check_width(name, getattr(self, name), width)
        if self.seconds_of_day >= SECONDS_PER_DAY:
            raise ValueError(f"seconds_of_day={self.seconds_of_day} is past 23:59:59")
        _check_register("target_reg", self.target_reg)
        _check_register("target_value", self.target_value)

    @property
    def hour(self) -> int:
        return self.seconds_of_day // 3600

    @property
    def minute(self) -> int:
        return (self.seconds_of_day % 3600) // 60

    @property
    def is_ac(self) -> bool:
        return self.target_reg == AC_SWITCH

    @property
    def is_dc(self) -> bool:
        return self.target_reg == DC_SWITCH

    def to_registers(self) -> list[int]:
        """The 7 registers, exactly as timeToRegs() lays them out."""
        packed = 0
        for name, offset, _width in _FIELDS:
            packed |= getattr(self, name) << offset
        regs = [(packed >> (16 * k)) & 0xFFFF for k in range(BITFIELD_REGISTERS)]
        return [*regs, self.target_reg, self.target_value]

    @classmethod
    def from_registers(cls, regs: Sequence[int]) -> TouEvent:
        """The inverse of to_registers(); raises if a field is out of range."""
        if len(regs) != RECORD_REGISTERS:
            raise ValueError(
                f"a record is {RECORD_REGISTERS} registers, got {len(regs)}"
            )
        for k, reg in enumerate(regs):
            _check_register(f"register {k}", reg)
        packed = 0
        for k in range(BITFIELD_REGISTERS):
            packed |= regs[k] << (16 * k)
        fields = {
            name: (packed >> offset) & ((1 << width) - 1)
            for name, offset, width in _FIELDS
        }
        return cls(**fields, target_reg=regs[5], target_value=regs[6])

    def describe(self) -> str:
        """One human line: when, on which days, what it writes."""
        days = "".join(
            n if self.week_mask & (1 << i) else "-" for i, n in enumerate("SMTWTFS")
        )
        target = {AC_SWITCH: "AC_SWITCH", DC_SWITCH: "DC_SWITCH"}.get(
            self.target_reg, str(self.target_reg)
        )
        return (
            f"{self.hour:02d}:{self.minute:02d} week={days} "
            f"dom=0x{self.day_of_month_mask:08x} month=0x{self.month_mask:03x} "
            f"type={self.time_type} reg_type={self.reg_type} id={self.target_id} "
            f"-> {target} = {self.target_value}"
        )


def swap_bytes(regs: Iterable[int]) -> list[int]:
    """Each register's two bytes exchanged - what parseTouTimeExt() undoes."""
    out = []
    for reg in regs:
        _check_register("register", reg)
        out.append(((reg & 0xFF) << 8) | (reg >> 8))
    return out


def _plausible(event: TouEvent) -> bool:
    # The three calendar shapes executeNewPlan() produces - once, weekly,
    # dates - are the only way to tell the two byte orders apart: every
    # field is masked to its width on decode, so a swapped record still
    # "fits", it just carries a calendar the app would never write.
    week, dom, month = event.week_mask, event.day_of_month_mask, event.month_mask
    if (week, dom, month) == (0, 0, 0):
        return True
    if dom == EVERY_DAY_OF_MONTH and month == EVERY_MONTH:
        return True
    single_month = month != 0 and month & (month - 1) == 0
    return week == EVERY_WEEKDAY and dom != 0 and single_month


def decode_table(
    regs: Sequence[int], *, byte_order: str = "auto"
) -> tuple[list[TouEvent], str]:
    """Split a run of registers into records.

    byte_order: "as-is", "swapped" (each register's bytes exchanged first,
    the device's own emission order per the app's parser) or "auto" -
    try "as-is" then "swapped", keep the first whose every record has one
    of the three calendar shapes the app writes (see _plausible). An
    explicit order is decoded as given, shape or not. Returns the events
    and the order used. All-zero records are unused slots and are left out.
    """
    if len(regs) % RECORD_REGISTERS:
        raise ValueError(f"{len(regs)} registers is not a whole number of records")
    if byte_order not in ("auto", "as-is", "swapped"):
        raise ValueError(f"byte_order {byte_order!r} is not auto, as-is or swapped")
    orders = ("as-is", "swapped") if byte_order == "auto" else (byte_order,)
    last_error: Exception | None = None
    for order in orders:
        words = swap_bytes(regs) if order == "swapped" else list(regs)
        try:
            events = [
                TouEvent.from_registers(words[i : i + RECORD_REGISTERS])
                for i in range(0, len(words), RECORD_REGISTERS)
                if any(words[i : i + RECORD_REGISTERS])
            ]
        except ValueError as err:
            last_error = err
            continue
        if byte_order != "auto" or all(_plausible(e) for e in events):
            return events, order
        last_error = ValueError(
            f"records decoded {order} have no app-written calendar shape"
        )
    raise ValueError(f"no byte order decodes this table: {last_error}")


def seconds(hour: int, minute: int, second: int = 0) -> int:
    if not (0 <= hour < 24 and 0 <= minute < 60 and 0 <= second < 60):
        raise ValueError(f"{hour:02d}:{minute:02d}:{second:02d} is not a time of day")
    return hour * 3600 + minute * 60 + second


def week_mask(*days: int) -> int:
    """Days as Monday=0 ... Sunday=6 (Python's weekday()) -> the app's mask."""
    mask = 0
    for day in days:
        if not 0 <= day <= 6:
            raise ValueError(f"weekday {day} is not 0 (Monday) .. 6 (Sunday)")
        mask |= 1 << ((day + 1) % 7)  # Sunday is bit 0
    return mask


@dataclass(frozen=True)
class TouPeriod:
    """One UI time range: the start record and the end record, 14 registers."""

    start: TouEvent
    end: TouEvent

    def to_registers(self) -> list[int]:
        return [*self.start.to_registers(), *self.end.to_registers()]

    @classmethod
    def from_registers(cls, regs: Sequence[int]) -> TouPeriod:
        if len(regs) != PERIOD_REGISTERS:
            raise ValueError(
                f"a period is {PERIOD_REGISTERS} registers, got {len(regs)}"
            )
        return cls(
            TouEvent.from_registers(regs[:RECORD_REGISTERS]),
            TouEvent.from_registers(regs[RECORD_REGISTERS:]),
        )


def _period(
    *,
    start_seconds: int,
    end_seconds: int,
    week: int,
    day_of_month: int,
    month: int,
    target_reg: int,
    start_value: int,
    end_value: int,
    time_type_start: int,
    time_type_end: int,
    reg_type: int,
    target_id: int,
) -> TouPeriod:
    common = {
        "week_mask": week,
        "day_of_month_mask": day_of_month,
        "month_mask": month,
        "reg_type": reg_type,
        "target_id": target_id,
        "target_reg": target_reg,
    }
    return TouPeriod(
        TouEvent(
            start_seconds, time_type=time_type_start, target_value=start_value, **common
        ),
        TouEvent(
            end_seconds, time_type=time_type_end, target_value=end_value, **common
        ),
    )


def once(
    start_seconds: int,
    end_seconds: int,
    *,
    target_reg: int,
    start_value: int,
    end_value: int,
    time_type_start: int,
    time_type_end: int,
    reg_type: int = 0,
    target_id: int = 0,
) -> TouPeriod:
    """repeatType 0 - a single occurrence: all three calendar masks 0."""
    return _period(
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        week=0,
        day_of_month=0,
        month=0,
        target_reg=target_reg,
        start_value=start_value,
        end_value=end_value,
        time_type_start=time_type_start,
        time_type_end=time_type_end,
        reg_type=reg_type,
        target_id=target_id,
    )


def weekly(
    start_seconds: int,
    end_seconds: int,
    *,
    week: int,
    target_reg: int,
    start_value: int,
    end_value: int,
    time_type_start: int,
    time_type_end: int,
    reg_type: int = 0,
    target_id: int = 0,
) -> TouPeriod:
    """repeatType 1 - the chosen weekdays, every day of the month, every month."""
    _check_width("week", week, 7)
    return _period(
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        week=week,
        day_of_month=EVERY_DAY_OF_MONTH,
        month=EVERY_MONTH,
        target_reg=target_reg,
        start_value=start_value,
        end_value=end_value,
        time_type_start=time_type_start,
        time_type_end=time_type_end,
        reg_type=reg_type,
        target_id=target_id,
    )


def on_dates(
    start_seconds: int,
    end_seconds: int,
    *,
    dates: Iterable[dt.date],
    target_reg: int,
    start_value: int,
    end_value: int,
    time_type_start: int,
    time_type_end: int,
    reg_type: int = 0,
    target_id: int = 0,
) -> TouPeriod:
    """repeatType 2 - specific dates: every weekday, their days, their month.

    The wire format holds ONE month mask for all the day bits, and the app
    silently keeps only the month with the most selected dates; this
    refuses dates spread over several months instead.
    """
    dates = list(dates)
    if not dates:
        raise ValueError("at least one date is needed")
    months = {d.month for d in dates}
    if len(months) != 1:
        raise ValueError(
            f"dates span months {sorted(months)}; a record holds one month "
            "(the app keeps only the most populated one)"
        )
    day_mask = 0
    for d in dates:
        day_mask |= 1 << (d.day - 1)
    return _period(
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        week=EVERY_WEEKDAY,
        day_of_month=day_mask,
        month=1 << (months.pop() - 1),
        target_reg=target_reg,
        start_value=start_value,
        end_value=end_value,
        time_type_start=time_type_start,
        time_type_end=time_type_end,
        reg_type=reg_type,
        target_id=target_id,
    )


def period_address(position: int) -> int:
    """Where UI time range number `position` (0-based) starts in the table."""
    if position < 0:
        raise ValueError("position is 0-based")
    return TOU_CTRL + position * PERIOD_REGISTERS
