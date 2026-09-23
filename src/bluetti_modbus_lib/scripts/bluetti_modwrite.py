import argparse
import asyncio
from enum import Enum
from typing import Any

from modbus_connection import ModbusConnection as _BaseModbusConnection
from modbus_connection import ModbusTcpParams
from modbus_connection.model import RegisterField
from probatio import Range

from ..base_devices import BluettiDevice
from ..devices.getter import get_device
from ..modbus import Backend

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


async def async_write(
    params: ModbusTcpParams,
    type: str,
    field_name: str,
    raw_value: str,
    backend: Backend,
    *,
    allow_ac_output: bool = False,
    assume_yes: bool = False,
) -> None:
    if get_device(type) is None:
        print("type not supported")
        return

    # Built inside each branch, not imported under one shared name first -
    # see bluetti_modread's own identical comment.
    conn: _BaseModbusConnection
    if backend == "tmodbus":
        from modbus_connection.tmodbus import ModbusConnection as _TConn

        conn = _TConn(params, timeout=10)
    else:
        from modbus_connection.pymodbus import ModbusConnection as _PConn

        conn = _PConn(params, timeout=10)

    # Unit id 1, always: a request to any other unit id froze an AC500's
    # Modbus TCP stack until a power cycle and silenced an EP500P (see
    # script/probe_unexplored_registers.py). Nothing here needs another.
    device = get_device(type, conn.for_unit(1))
    assert device is not None  # already checked above

    try:
        field, value = prepare_write(
            device, field_name, raw_value, allow_ac_output=allow_ac_output
        )
    except WriteRefused as err:
        print(err)
        await conn.close()
        return

    try:
        await conn.connect()
        await device.async_update_with_retry()
        current = device.values.get(field_name)
        print(f"{field_name} ({field.address}): {current} -> {value}")
        if not assume_yes and not _confirmed():
            print("nothing written")
            return

        await device.write(field_name, value)

        await device.async_update_with_retry()
        print(f"{field_name} now reads {device.values.get(field_name)}")
    finally:
        await conn.close()


def _confirmed() -> bool:
    return input("Write it? [y/N] ").strip().lower() == "y"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write one setting on a bluetti device via modbus"
    )
    parser.add_argument("-c", "--host", type=str, help="IP-address of the device")
    parser.add_argument("-p", "--port", type=int, help="Port of the device")
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

    if (
        args.host is None
        or args.port is None
        or args.type is None
        or args.field is None
        or args.value is None
    ):
        parser.print_help()
        return

    asyncio.run(
        async_write(
            ModbusTcpParams(host=args.host, port=args.port),
            args.type,
            args.field,
            args.value,
            args.backend,
            allow_ac_output=args.allow_ac_output,
            assume_yes=args.yes,
        )
    )
