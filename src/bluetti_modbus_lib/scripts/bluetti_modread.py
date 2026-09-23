import argparse
import asyncio

from modbus_connection import ModbusConnection as _BaseModbusConnection
from modbus_connection import ModbusSerialParams, ModbusTcpParams
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

    print_component(device)
    print(f"\n{counting_unit.reads} Modbus block reads")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read bluetti devices via modbus")
    # Modbus TCP and a serial line are two transports: one of them, never
    # both. --port stays outside the group because it belongs to --host,
    # and is refused next to --serial below.
    transport = parser.add_mutually_exclusive_group()
    transport.add_argument("-c", "--host", type=str, help="IP-address of the device")
    transport.add_argument(
        "-s",
        "--serial",
        type=str,
        metavar="DEVICE",
        help=(
            "serial port to read Modbus RTU from, instead of --host: a port "
            "path (/dev/ttyUSB0, COM3) or any URL pyserial understands, "
            "notably socket://ip:port for a transparent serial-to-TCP "
            "gateway (an ESP32 bridge, a hardware converter), where the line "
            "settings below live in the gateway and are ignored here."
        ),
    )
    parser.add_argument(
        "-p", "--port", type=int, help="Port of the device (with --host)"
    )
    parser.add_argument("-t", "--type", type=str, help="Device type")
    parser.add_argument(
        "--baud", type=int, default=9600, help="serial line speed (default: 9600)"
    )
    parser.add_argument(
        "--parity",
        choices=["N", "E", "O"],
        default="N",
        help="serial parity: none, even or odd (default: N)",
    )
    parser.add_argument(
        "--stopbits",
        type=int,
        choices=[1, 2],
        default=1,
        help="serial stop bits (default: 1)",
    )
    parser.add_argument(
        "-u",
        "--unit",
        type=int,
        default=1,
        help=(
            "Modbus unit id to read (default: 1). On a shared RS485 bus this "
            "is how a device is picked; never address another unit id on an "
            "AC500 or EP500Pro - see HARDWARE_TESTING.md."
        ),
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.serial is not None and args.port is not None:
        parser.error("--port belongs to --host; --serial carries no port")
    return args


def start() -> None:
    args = parse_args()

    if args.type is None or (args.host is None and args.serial is None):
        # argparse already refuses --host with --serial; this is the
        # "nothing useful given" case, where the help is the answer.
        build_parser().print_help()
        return

    params: ModbusTcpParams | ModbusSerialParams
    if args.serial is not None:
        params = ModbusSerialParams(
            device=args.serial,
            baudrate=args.baud,
            parity=args.parity,
            stopbits=args.stopbits,
            framer="rtu",
        )
    else:
        params = ModbusTcpParams(
            host=args.host, port=502 if args.port is None else args.port
        )

    asyncio.run(async_read(params, args.type, args.backend, args.unit))
