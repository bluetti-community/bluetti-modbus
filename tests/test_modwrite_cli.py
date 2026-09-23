"""Tests for bluetti-modwrite: what it refuses, and what it puts on the wire."""

from unittest.mock import patch

import pytest
from modbus_connection import ModbusSerialParams, ModbusTcpParams
from modbus_connection.mock import MockModbusConnection
from probatio import Range

from bluetti_modbus_lib.devices import Balco260
from bluetti_modbus_lib.scripts.bluetti_modwrite import (
    WriteRefused,
    build_parser,
    prepare_write,
    read_field,
    writable_fields,
    write_field,
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


def _field(name: str = "b_soc_high"):
    return Balco260(None).get_field(name)


@pytest.mark.asyncio
async def test_reading_a_field_costs_one_block_read():
    # Not a whole device refresh: that is fifteen block reads on a Balco
    # 260 just to show one number, on a stack that serves one client at a
    # time.
    conn = MockModbusConnection()
    unit = conn.for_unit(1)
    unit.holding[57017] = 90
    reads: list[tuple[int, int]] = []
    original = unit.read_holding_registers

    async def _counted(address: int, count: int) -> list[int]:
        reads.append((address, count))
        return await original(address, count)

    unit.read_holding_registers = _counted  # type: ignore[method-assign]

    with patch("modbus_connection.tmodbus.ModbusConnection", return_value=conn):
        value = await read_field(
            ModbusTcpParams(host="10.0.0.1", port=502), _field(), "tmodbus", 1
        )

    assert value == 90
    assert reads == [(57017, 1)]


@pytest.mark.asyncio
async def test_reading_a_field_closes_the_connection_behind_it():
    # The prompt happens with nothing open - the device would otherwise
    # hold an idle socket for as long as the user takes to answer.
    conn = MockModbusConnection()
    conn.for_unit(1).holding[57017] = 90

    with patch("modbus_connection.tmodbus.ModbusConnection", return_value=conn):
        await read_field(
            ModbusTcpParams(host="10.0.0.1", port=502), _field(), "tmodbus", 1
        )

    assert conn.connected is False


@pytest.mark.asyncio
async def test_writing_puts_the_value_on_the_wire_and_reads_it_back():
    conn = MockModbusConnection()
    conn.for_unit(1).holding[57017] = 90

    with patch("modbus_connection.tmodbus.ModbusConnection", return_value=conn):
        now = await write_field(
            ModbusTcpParams(host="10.0.0.1", port=502),
            "balco260",
            "b_soc_high",
            _field(),
            95,
            "tmodbus",
            1,
            settle=0,
        )

    assert now == 95
    assert conn.for_unit(1).holding[57017] == 95
    assert conn.connected is False


@pytest.mark.asyncio
async def test_a_device_that_serves_the_old_value_for_a_moment_is_read_again():
    # Confirmed on a real Balco 260: writing b_soc_low 15 -> 16 read back
    # 15, and the next command read 16. The setting is applied at once and
    # served late, so one read straight after the write is not the answer.
    conn = MockModbusConnection()
    unit = conn.for_unit(1)
    unit.holding[57017] = 90
    original = unit.read_holding_registers
    stale = [True]

    async def _late(address: int, count: int) -> list[int]:
        if stale[0]:
            stale[0] = False
            return [90]
        return await original(address, count)

    unit.read_holding_registers = _late  # type: ignore[method-assign]

    with patch("modbus_connection.tmodbus.ModbusConnection", return_value=conn):
        now = await write_field(
            ModbusTcpParams(host="10.0.0.1", port=502),
            "balco260",
            "b_soc_high",
            _field(),
            95,
            "tmodbus",
            1,
            settle=0,
        )

    assert now == 95


@pytest.mark.asyncio
async def test_a_value_that_never_appears_is_reported_as_it_reads():
    # Not dressed up as a success: the caller says what the device reports.
    conn = MockModbusConnection()
    unit = conn.for_unit(1)
    unit.holding[57017] = 90

    async def _never_changes(address: int, count: int) -> list[int]:
        return [90]

    unit.read_holding_registers = _never_changes  # type: ignore[method-assign]

    with patch("modbus_connection.tmodbus.ModbusConnection", return_value=conn):
        now = await write_field(
            ModbusTcpParams(host="10.0.0.1", port=502),
            "balco260",
            "b_soc_high",
            _field(),
            95,
            "tmodbus",
            1,
            settle=0,
        )

    assert now == 90


@pytest.mark.asyncio
async def test_writing_addresses_the_unit_id_it_was_given():
    # A device on a shared RS485 bus answers at its own address.
    conn = MockModbusConnection()
    conn.for_unit(7).holding[57017] = 90

    with patch("modbus_connection.tmodbus.ModbusConnection", return_value=conn):
        await write_field(
            ModbusTcpParams(host="10.0.0.1", port=502),
            "balco260",
            "b_soc_high",
            _field(),
            95,
            "tmodbus",
            7,
            settle=0,
        )

    assert conn.for_unit(7).holding[57017] == 95


@pytest.mark.asyncio
async def test_a_serial_line_reads_the_same_way():
    conn = MockModbusConnection()
    conn.for_unit(1).holding[57017] = 90
    params = ModbusSerialParams(device="/dev/ttyUSB0")

    with patch("modbus_connection.tmodbus.ModbusConnection", return_value=conn) as tm:
        assert await read_field(params, _field(), "tmodbus", 1) == 90

    assert tm.call_args.args[0] is params


def test_the_writer_takes_the_same_transport_options_as_the_reader():
    args = build_parser().parse_args(
        [
            "-s",
            "socket://192.168.1.50:8899",
            "-t",
            "ep2000",
            "-f",
            "b_soc_high",
            "-v",
            "95",
        ]
    )

    assert args.serial == "socket://192.168.1.50:8899"
    assert (args.baud, args.parity, args.stopbits, args.unit) == (9600, "N", 1, 1)


def test_the_writer_refuses_host_and_serial_together():
    with pytest.raises(SystemExit):
        build_parser().parse_args(
            [
                "-c",
                "10.0.0.1",
                "-s",
                "/dev/ttyUSB0",
                "-t",
                "ep2000",
                "-f",
                "x",
                "-v",
                "1",
            ]
        )
