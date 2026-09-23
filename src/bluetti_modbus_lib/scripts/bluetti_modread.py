import argparse
import asyncio
import inspect
import sys

from modbus_connection import ModbusConnection as _BaseModbusConnection
from modbus_connection import ModbusSerialParams, ModbusTcpParams
from modbus_connection.cli_helper import CountingUnit, field_rows, group_rows
from modbus_connection.exceptions import ModbusError
from modbus_connection.model import Component

from ..devices.getter import get_device
from ..modbus import Backend
from ._connection_args import (
    add_connection_arguments,
    check_connection_arguments,
    connection_params,
)

# Not BluettiModbusClient: that wrapper decodes straight into a flat
# name/value/unit list (see ClientReturnValue), which is exactly what a
# downstream integration wants but hides the two things a query helper is
# for - the live Component itself (print_fields below walks its own field
# metadata/grouping, not a flattened copy) and the raw connection (needed
# to wrap it in CountingUnit below). Talking to the same pieces
# BluettiModbusClient itself is built on, directly, is the documented
# pattern for a library's own query helper - see modbus-connection's own
# patterns/query-helper.


# What Component itself defines. field_rows() skips these and reports
# everything else a class adds, so a subclass's own properties land among
# the fields: BluettiDevice.values is one, and it repeats the whole read
# as a dict under the rows it duplicates.
_COMPONENT_ATTRS = frozenset(dir(Component))


def _property_names(component: Component) -> set[str]:
    """The names field_rows() lists that are properties, not Modbus fields."""
    cls = type(component)
    return {
        name
        for name in dir(component)
        if not name.startswith("_")
        and name not in _COMPONENT_ATTRS
        and isinstance(inspect.getattr_static(cls, name, None), property)
    }


def print_fields(
    component: Component, *, title: str | None = None, indent: str = ""
) -> None:
    """Print a device's fields, and each repeating group's, as a table.

    print_component() with the properties left out; the rows, their units
    and the groups are still what modbus-connection itself reflects.
    """
    skipped = _property_names(component)
    rows = [row for row in field_rows(component) if row[0] not in skipped]
    heading = title if title is not None else type(component).__name__
    print(f"{indent}{heading}")
    print(f"{indent}{'-' * len(heading)}")
    width = max((len(name) for name, _ in rows), default=0)
    for name, value in rows:
        print(f"{indent}  {name.ljust(width)}  {value}")
    for name, instances in group_rows(component):
        for index, instance in enumerate(instances, start=1):
            print()
            print_fields(instance, title=f"{name}[{index}]", indent=f"{indent}  ")


async def async_read(
    params: ModbusTcpParams | ModbusSerialParams,
    type: str,
    backend: Backend,
    unit: int = 1,
) -> None:
    if get_device(type) is None:
        print("type not supported")
        return

    # Built inside each branch, not imported under one shared name first
    # (see BluettiModbusClient.__init__'s own identical comment) - that's
    # what lets mypy see each concrete class as assignment-compatible with
    # this declared base, instead of flagging the import itself.
    conn: _BaseModbusConnection
    if backend == "tmodbus":
        from modbus_connection.tmodbus import ModbusConnection as _TConn

        conn = _TConn(params, timeout=10)
    else:
        from modbus_connection.pymodbus import ModbusConnection as _PConn

        conn = _PConn(params, timeout=10)

    # CountingUnit implements the full ModbusUnit interface (no casting
    # needed) - it only adds a running tally of block reads, so this is a
    # transparent wrap: get_device()/the device's own update logic below
    # behave exactly as they would against the unit directly.
    counting_unit = CountingUnit(conn.for_unit(unit))
    device = get_device(type, counting_unit)
    assert device is not None  # already checked above

    try:
        await conn.connect()
        await device.async_update_with_retry()
    finally:
        await conn.close()

    print_fields(device)
    print(f"\n{counting_unit.reads} Modbus block reads")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read bluetti devices via modbus")
    add_connection_arguments(parser)
    parser.add_argument("-t", "--type", type=str, help="Device type")
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args(argv)
    check_connection_arguments(parser, args)
    return args


def start() -> None:
    args = parse_args()

    if args.type is None or (args.host is None and args.serial is None):
        # argparse already refuses --host with --serial; this is the
        # "nothing useful given" case, where the help is the answer.
        build_parser().print_help()
        return

    try:
        asyncio.run(
            async_read(connection_params(args), args.type, args.backend, args.unit)
        )
    except ModbusError as err:
        # An unreachable device or a serial port that will not open is an
        # ordinary outcome for a command like this, not a crash to print a
        # traceback for.
        print(err)
        sys.exit(1)
