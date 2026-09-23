import argparse
import asyncio
from enum import Enum
from typing import Any

from modbus_connection import ModbusConnection as _BaseModbusConnection
from modbus_connection import ModbusSerialParams, ModbusTcpParams
from modbus_connection.model import RegisterField
from probatio import Range

from ..base_devices import BluettiDevice
from ..devices.getter import get_device
from ..modbus import Backend
from ._connection_args import (
    add_connection_arguments,
    check_connection_arguments,
    connection_params,
)

# A write counterpart to bluetti-modread, after the bluetti-modwrite
# Patrick762 shipped in his own bluetti-modbus-lib (25bb444, 2026-09-13):
# same flags (-c/-p/-t/-f/-v), so anyone coming from there does not have
# to relearn the command.
#
# Built on the same pieces as bluetti-modread (see its own comment), with
# one addition that matters: the write goes through BluettiDevice.write(),
# never the Component's own. That override is what absorbs a confirmation
# the device echoes at its internal register address - a strict client
# reports it as a protocol error even though the write applied - and what
# records the echo per device. Bypassing it would turn every successful
# write on a Balco-family device into a failure.

# The AC output switch: on a FridgePower it powers the fridge, on any
# device it can cut whatever the AC outlets feed. Same guard as
# script/write_probe.py - a deliberate flag, not a prompt to click
# through.
AC_OUTPUT_SWITCH = 57001


class WriteRefused(Exception):
    """A write this tool will not send, with the reason a user can act on."""


def writable_fields(device: BluettiDevice) -> list[str]:
    """The field names this device declares writable, in register order."""
    names = [n for n in device.field_names() if _field(device, n).writable]
    return sorted(names, key=lambda n: _field(device, n).address)


def _field(device: BluettiDevice, name: str) -> RegisterField[Any]:
    field = device.get_field(name)
    assert field is not None  # only ever called with a known field name
    return field


def prepare_write(
    device: BluettiDevice, field_name: str, raw_value: str, *, allow_ac_output: bool
) -> tuple[RegisterField[Any], Any]:
    """The field to write and the value to write to it, or raise WriteRefused.

    Everything that can be checked without touching the device is checked
    here: that the field exists, that the profile declares it writable,
    that the value parses the way the field decodes, and that it sits
    inside the bounds the profile declares (a ``Range`` on ``writable``,
    e.g. Balco260's b_soc_low is 5-90). Pure, so a test can exercise it
    without a connection.
    """
    field = device.get_field(field_name)
    if field is None:
        available = ", ".join(writable_fields(device)) or "none"
        raise WriteRefused(
            f"{field_name!r} is not a field of this device. Writable fields: {available}"
        )
    if not field.writable:
        available = ", ".join(writable_fields(device)) or "none"
        raise WriteRefused(
            f"{field_name!r} is read-only on this device. Writable fields: {available}"
        )
    if field.address == AC_OUTPUT_SWITCH and not allow_ac_output:
        raise WriteRefused(
            f"{field_name!r} is the AC output switch: writing it powers whatever "
            "the AC outlets feed (a fridge, on a FridgePower). Pass "
            "--allow-ac-output if you really mean it."
        )

    value = _parse_value(field, raw_value)
    if isinstance(field.writable, Range):
        # The same validator the device object applies on write - called
        # here so the bounds are reported before anything is sent.
        try:
            field.writable(value)
        except Exception as err:
            raise WriteRefused(
                f"{value} is outside what {field_name!r} accepts "
                f"({field.writable.min} to {field.writable.max}): {err}"
            ) from err
    return field, value


def _parse_value(field: RegisterField[Any], raw_value: str) -> Any:
    """The raw argument as this field's own type: an enum member, or a number."""
    enum_type = getattr(field, "convert", None)
    if isinstance(enum_type, type) and issubclass(enum_type, Enum):
        # Either spelling is accepted: the member name as the reader
        # prints it, or the integer the register holds.
        try:
            return enum_type[raw_value]
        except KeyError:
            pass
        try:
            return enum_type(int(raw_value))
        except (ValueError, KeyError) as err:
            options = ", ".join(f"{m.name}={m.value}" for m in enum_type)
            raise WriteRefused(
                f"{raw_value!r} is not one of this field's values: {options}"
            ) from err
    try:
        return int(raw_value)
    except ValueError as err:
        raise WriteRefused(f"{raw_value!r} is not a whole number") from err


def _connect(
    params: ModbusTcpParams | ModbusSerialParams, backend: Backend
) -> _BaseModbusConnection:
    # Built inside each branch, not imported under one shared name first -
    # see bluetti_modread's own identical comment.
    conn: _BaseModbusConnection
    if backend == "tmodbus":
        from modbus_connection.tmodbus import ModbusConnection as _TConn

        conn = _TConn(params, timeout=10)
    else:
        from modbus_connection.pymodbus import ModbusConnection as _PConn

        conn = _PConn(params, timeout=10)
    return conn


async def read_field(
    params: ModbusTcpParams | ModbusSerialParams,
    field: RegisterField[Any],
    backend: Backend,
    unit: int,
) -> Any:
    """This one field's current value, on a connection of its own.

    One block read, not a whole device update: a full refresh costs
    fifteen block reads on a Balco 260 and sixteen on a FridgePower, on a
    Modbus stack that serves one client at a time - far too much traffic
    to show a single number. The connection is opened and closed around
    it, so nothing is held while the user decides.
    """
    conn = _connect(params, backend)
    try:
        await conn.connect()
        words = await conn.for_unit(unit).read_holding_registers(
            field.address, field.count
        )
        return field.decode(words)
    finally:
        await conn.close()


async def write_field(
    params: ModbusTcpParams | ModbusSerialParams,
    device_type: str,
    field_name: str,
    field: RegisterField[Any],
    value: Any,
    backend: Backend,
    unit: int,
) -> Any:
    """Write the value and return what the device reports afterwards.

    The device is built on this connection - a component's unit is fixed
    at construction - and the write goes through BluettiDevice.write(),
    never the Component's own: that override is what absorbs a
    confirmation the device echoes at its internal register address,
    which a strict client reports as a protocol error even though the
    write applied.
    """
    conn = _connect(params, backend)
    try:
        await conn.connect()
        unit_handle = conn.for_unit(unit)
        device = get_device(device_type, unit_handle)
        assert device is not None  # the type was checked before connecting
        await device.write(field_name, value)
        words = await unit_handle.read_holding_registers(field.address, field.count)
        return field.decode(words)
    finally:
        await conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write one setting on a bluetti device via modbus"
    )
    add_connection_arguments(parser)
    parser.add_argument("-t", "--type", type=str, help="Device type")
    parser.add_argument(
        "-f", "--field", type=str, help="Field to write, e.g. b_soc_high"
    )
    parser.add_argument(
        "-v",
        "--value",
        type=str,
        help="Value to write: a number, or an enum field's member name",
    )
    parser.add_argument(
        "--allow-ac-output",
        action="store_true",
        help=(
            "allow writing the AC output switch (57001) - it powers whatever "
            "the AC outlets feed, a fridge on a FridgePower"
        ),
    )
    parser.add_argument(
        "-y", "--yes", action="store_true", help="skip the confirmation prompt"
    )
    parser.add_argument(
        "-b",
        "--backend",
        type=str,
        choices=["pymodbus", "tmodbus"],
        default="tmodbus",
        help=(
            "Modbus backend (default: tmodbus, what both HA integrations use "
            "since 0.4.0 - see CONTRIBUTING.md). pymodbus is still available - "
            "pip install 'bluetti-modbus[cli-pymodbus]' first."
        ),
    )
    return parser


def start() -> None:
    parser = build_parser()
    args = parser.parse_args()
    check_connection_arguments(parser, args)

    if (
        args.type is None
        or args.field is None
        or args.value is None
        or (args.host is None and args.serial is None)
    ):
        parser.print_help()
        return

    device = get_device(args.type)
    if device is None:
        print("type not supported")
        return

    try:
        field, value = prepare_write(
            device, args.field, args.value, allow_ac_output=args.allow_ac_output
        )
    except WriteRefused as err:
        print(err)
        return

    params = connection_params(args)
    current = asyncio.run(read_field(params, field, args.backend, args.unit))
    print(f"{args.field} ({field.address}): {current} -> {value}")

    # Asked with no connection open: the device serves one client at a
    # time, and however long the answer takes is time it would otherwise
    # spend holding an idle socket for nothing.
    if not args.yes and input("Write it? [y/N] ").strip().lower() != "y":
        print("nothing written")
        return

    now = asyncio.run(
        write_field(
            params, args.type, args.field, field, value, args.backend, args.unit
        )
    )
    print(f"{args.field} now reads {now}")
