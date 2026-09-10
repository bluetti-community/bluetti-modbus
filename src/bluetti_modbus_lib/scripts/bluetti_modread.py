import argparse
import asyncio

from modbus_connection import ModbusConnection as _BaseModbusConnection
from modbus_connection import ModbusTcpParams
from modbus_connection.cli_helper import CountingUnit, print_component

from ..devices.getter import get_device
from ..modbus import Backend

# Not BluettiModbusClient: that wrapper decodes straight into a flat
# name/value/unit list (see ClientReturnValue), which is exactly what a
# downstream integration wants but hides the two things a query helper is
# for - the live Component itself (print_component walks its own field
# metadata/grouping, not a flattened copy) and the raw connection (needed
# to wrap it in CountingUnit below). Talking to the same pieces
# BluettiModbusClient itself is built on, directly, is the documented
# pattern for a library's own query helper - see modbus-connection's own
# patterns/query-helper.


async def async_read(host: str, port: int, type: str, backend: Backend) -> None:
    if get_device(type) is None:
        print("type not supported")
        return

    params = ModbusTcpParams(host=host, port=port)
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
    counting_unit = CountingUnit(conn.for_unit(1))
    device = get_device(type, counting_unit)
    assert device is not None  # already checked above

    try:
        await conn.connect()
        await device.async_update_with_retry()
    finally:
        await conn.close()

    print_component(device)
    print(f"\n{counting_unit.reads} Modbus block reads")


def start() -> None:
    parser = argparse.ArgumentParser(description="Read bluetti devices via modbus")
    parser.add_argument("-c", "--host", type=str, help="IP-address of the device")
    parser.add_argument("-p", "--port", type=int, help="Port of the device")
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
    args = parser.parse_args()

    if args.host is None or args.port is None or args.type is None:
        parser.print_help()
        return

    asyncio.run(async_read(args.host, args.port, args.type, args.backend))
