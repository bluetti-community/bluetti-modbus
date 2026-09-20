"""Tests for script/tou_codec.py - the Balco TOU scheduler record codec.

The reference here is a line-by-line port of the decompiled Java
(DeviceTouTime.timeToRegs() and its setBits helper, BLUETTI app 3.1.4):
two 64-bit longs filled bit by bit, then five 16-bit registers read back
bit by bit. The codec's arithmetic form has to agree with it on every
input, not just on the documented examples.
"""

import datetime as dt
import importlib.util
import random
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "tou_codec", Path(__file__).parents[1] / "script" / "tou_codec.py"
)
assert _SPEC is not None and _SPEC.loader is not None
tou = importlib.util.module_from_spec(_SPEC)
# dataclasses resolve `from __future__ import annotations` through
# sys.modules[cls.__module__] - a spec-loaded module has to be registered.
sys.modules[_SPEC.name] = tou
_SPEC.loader.exec_module(tou)


def _java_set_bits(j_arr: list[int], value: int, offset: int, width: int) -> None:
    # timeToRegs$setBits, verbatim.
    for i3 in range(width):
        j2 = (value >> i3) & 1
        i4 = offset + i3
        if i4 >= 64:
            i5 = i4 - 64
            if j2 == 1:
                j_arr[1] = (1 << i5) | j_arr[1]
        elif j2 == 1:
            j_arr[0] = j_arr[0] | (1 << i4)


def _java_time_to_regs(e) -> list[int]:
    # timeToRegs(), verbatim - including the two-long split at bit 64.
    j_arr = [0, 0]
    _java_set_bits(j_arr, e.seconds_of_day, 0, 17)
    _java_set_bits(j_arr, e.week_mask, 17, 7)
    _java_set_bits(j_arr, e.day_of_month_mask, 24, 31)
    _java_set_bits(j_arr, e.month_mask, 55, 12)
    _java_set_bits(j_arr, e.reg_type, 67, 2)
    _java_set_bits(j_arr, e.target_id, 69, 8)
    _java_set_bits(j_arr, e.time_type, 77, 3)
    i_arr = [0] * 5
    for i in range(5):
        i2 = i * 16
        i3 = 0
        for i4 in range(16):
            i5 = i2 + i4
            if i5 < 64:
                j = j_arr[0]
            else:
                j = j_arr[1]
                i5 -= 64
            i3 |= ((j >> i5) & 1) << i4
        i_arr[i] = 65535 & i3
    return i_arr


def _random_event(rng: random.Random):
    return tou.TouEvent(
        seconds_of_day=rng.randrange(tou.SECONDS_PER_DAY),
        week_mask=rng.randrange(1 << 7),
        day_of_month_mask=rng.randrange(1 << 31),
        month_mask=rng.randrange(1 << 12),
        reg_type=rng.randrange(1 << 2),
        target_id=rng.randrange(1 << 8),
        time_type=rng.randrange(1 << 3),
        target_reg=rng.randrange(1 << 16),
        target_value=rng.randrange(1 << 16),
    )


def test_bitfield_matches_the_decompiled_java_on_random_records():
    rng = random.Random(20260920)
    for _ in range(2000):
        event = _random_event(rng)
        assert event.to_registers()[:5] == _java_time_to_regs(event)


def test_every_field_alone_lands_where_the_layout_says():
    # Hand-computed from the bit offsets: register k holds bits 16k..16k+15.
    cases = [
        ({"seconds_of_day": 86399}, [0x517F, 0x0001, 0, 0, 0]),  # 0x1517F, 17 bits
        ({"seconds_of_day": 0, "week_mask": 0x7F}, [0, 0x00FE, 0, 0, 0]),  # bits 17-23
        (
            {"seconds_of_day": 0, "day_of_month_mask": 0x7FFFFFFF},
            [0, 0xFF00, 0xFFFF, 0x007F, 0],
        ),  # bits 24-54
        (
            {"seconds_of_day": 0, "month_mask": 0xFFF},
            [0, 0, 0, 0xFF80, 0x0007],
        ),  # 55-66
        ({"seconds_of_day": 0, "reg_type": 3}, [0, 0, 0, 0, 0x0018]),  # bits 67-68
        ({"seconds_of_day": 0, "target_id": 0xFF}, [0, 0, 0, 0, 0x1FE0]),  # bits 69-76
        ({"seconds_of_day": 0, "time_type": 7}, [0, 0, 0, 0, 0xE000]),  # bits 77-79
    ]
    for fields, expected in cases:
        event = tou.TouEvent(**fields)
        assert event.to_registers()[:5] == expected, fields
        assert _java_time_to_regs(event) == expected, fields


def test_the_two_plain_registers_follow_the_bitfield():
    event = tou.TouEvent(seconds_of_day=0, target_reg=tou.AC_SWITCH, target_value=1)
    assert event.to_registers() == [0, 0, 0, 0, 0, 2011, 1]
    assert event.is_ac and not event.is_dc


def test_round_trip_on_random_records():
    rng = random.Random(7)
    for _ in range(2000):
        event = _random_event(rng)
        assert tou.TouEvent.from_registers(event.to_registers()) == event


def test_fields_that_do_not_fit_are_refused():
    with pytest.raises(ValueError, match="seconds_of_day"):
        tou.TouEvent(seconds_of_day=tou.SECONDS_PER_DAY)
    with pytest.raises(ValueError, match="week_mask"):
        tou.TouEvent(seconds_of_day=0, week_mask=0x80)
    with pytest.raises(ValueError, match="time_type"):
        tou.TouEvent(seconds_of_day=0, time_type=8)
    with pytest.raises(ValueError, match="target_value"):
        tou.TouEvent(seconds_of_day=0, target_value=0x10000)
    with pytest.raises(ValueError, match="7 registers"):
        tou.TouEvent.from_registers([0] * 6)


def test_hour_and_minute_read_like_the_app_getters():
    event = tou.TouEvent(seconds_of_day=tou.seconds(23, 59, 59))
    assert (event.hour, event.minute) == (23, 59)
    with pytest.raises(ValueError):
        tou.seconds(24, 0)


def test_week_mask_puts_sunday_on_bit_0():
    assert tou.week_mask(6) == tou.SUNDAY == 0x01
    assert tou.week_mask(0) == tou.MONDAY == 0x02
    assert tou.week_mask(5) == tou.SATURDAY == 0x40
    assert tou.week_mask(*range(7)) == tou.EVERY_WEEKDAY
    with pytest.raises(ValueError):
        tou.week_mask(7)


def test_decode_table_honours_an_explicit_byte_order():
    rng = random.Random(3)
    events = [_random_event(rng) for _ in range(3)]
    regs = [r for e in events for r in e.to_registers()]

    assert tou.decode_table(regs, byte_order="as-is") == (events, "as-is")
    assert tou.decode_table(tou.swap_bytes(regs), byte_order="swapped") == (
        events,
        "swapped",
    )
    with pytest.raises(ValueError, match="byte_order"):
        tou.decode_table(regs, byte_order="little")


def test_decode_table_auto_picks_the_order_that_yields_app_calendars():
    weekly = tou.weekly(
        tou.seconds(6, 30),
        tou.seconds(8, 0),
        week=tou.MONDAY,
        target_reg=tou.AC_SWITCH,
        start_value=1,
        end_value=0,
        time_type_start=1,
        time_type_end=2,
    )
    regs = weekly.to_registers()

    assert tou.decode_table(regs) == ([weekly.start, weekly.end], "as-is")
    assert tou.decode_table(tou.swap_bytes(regs)) == (
        [weekly.start, weekly.end],
        "swapped",
    )


def test_decode_table_auto_refuses_a_table_with_no_app_calendar_shape():
    # A random calendar is neither once, weekly nor dates - auto cannot
    # tell which order it came in and says so rather than guessing.
    stray = tou.TouEvent(seconds_of_day=60, week_mask=0x03, month_mask=0x005)
    with pytest.raises(ValueError, match="calendar shape"):
        tou.decode_table(stray.to_registers())


def test_decode_table_skips_empty_slots_and_refuses_ragged_input():
    event = tou.TouEvent(seconds_of_day=60)
    regs = [0] * 7 + event.to_registers() + [0] * 7

    decoded, _ = tou.decode_table(regs, byte_order="as-is")

    assert decoded == [event]
    with pytest.raises(ValueError, match="whole number"):
        tou.decode_table([0] * 8)


def test_swap_bytes_exchanges_each_register_s_two_bytes():
    assert tou.swap_bytes([0x1234, 0x00FF]) == [0x3412, 0xFF00]
    assert tou.swap_bytes(tou.swap_bytes([0xABCD])) == [0xABCD]


def test_weekly_fills_the_masks_as_the_app_does():
    period = tou.weekly(
        tou.seconds(6, 0),
        tou.seconds(8, 30),
        week=tou.week_mask(0, 1, 2, 3, 4),
        target_reg=tou.DC_SWITCH,
        start_value=1,
        end_value=0,
        time_type_start=1,
        time_type_end=2,
    )
    assert period.start.week_mask == 0b0111110
    assert period.start.day_of_month_mask == tou.EVERY_DAY_OF_MONTH
    assert period.start.month_mask == tou.EVERY_MONTH
    assert (period.start.time_type, period.end.time_type) == (1, 2)
    assert (period.start.target_value, period.end.target_value) == (1, 0)
    assert period.end.is_dc
    assert len(period.to_registers()) == 14
    assert tou.TouPeriod.from_registers(period.to_registers()) == period


def test_once_leaves_every_mask_at_zero():
    period = tou.once(
        0,
        60,
        target_reg=2011,
        start_value=1,
        end_value=0,
        time_type_start=1,
        time_type_end=2,
    )
    assert (
        period.start.week_mask,
        period.start.day_of_month_mask,
        period.start.month_mask,
    ) == (
        0,
        0,
        0,
    )


def test_on_dates_encodes_one_month_and_refuses_two():
    period = tou.on_dates(
        0,
        60,
        dates=[dt.date(2026, 10, 1), dt.date(2026, 10, 31)],
        target_reg=2011,
        start_value=1,
        end_value=0,
        time_type_start=1,
        time_type_end=2,
    )
    assert period.start.week_mask == tou.EVERY_WEEKDAY
    assert period.start.day_of_month_mask == (1 << 0) | (1 << 30)
    assert period.start.month_mask == 1 << 9
    with pytest.raises(ValueError, match="span months"):
        tou.on_dates(
            0,
            60,
            dates=[dt.date(2026, 10, 1), dt.date(2026, 11, 1)],
            target_reg=2011,
            start_value=1,
            end_value=0,
            time_type_start=1,
            time_type_end=2,
        )


def test_period_address_steps_by_fourteen():
    assert tou.period_address(0) == 26001
    assert tou.period_address(3) == 26001 + 42
    with pytest.raises(ValueError):
        tou.period_address(-1)


def test_working_mode_aliases_and_ems_values():
    assert tou.WorkingMode(3) is tou.WorkingMode.STANDARD_UPS
    assert tou.WorkingMode.ZERO_UPS is tou.WorkingMode.STANDARD_UPS
    assert tou.WorkingMode.V2_STANDARD_UPS_OFFLINE is tou.WorkingMode.TIME_CTRL_UPS
    assert tou.EmsCtrlMode.AI == 8 and tou.EmsCtrlMode.DISABLE == 0


def test_describe_is_one_readable_line():
    event = tou.TouEvent(
        seconds_of_day=tou.seconds(6, 30),
        week_mask=tou.MONDAY | tou.FRIDAY,
        target_reg=tou.AC_SWITCH,
        target_value=1,
    )
    assert event.describe() == (
        "06:30 week=-M---F- dom=0x00000000 month=0x000 type=0 reg_type=0 id=0 -> AC_SWITCH = 1"
    )
