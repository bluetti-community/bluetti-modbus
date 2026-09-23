"""The connection options bluetti-modread and bluetti-modwrite share.

One transport per run: Modbus TCP (``--host``, ``--port``) or Modbus RTU
on a serial line (``--serial`` and the line settings). Kept here so the
two commands cannot drift apart - a device readable over RS485 has to be
writable over it too.
"""

import argparse

from modbus_connection import ModbusSerialParams, ModbusTcpParams

# The Modbus TCP port BLUETTI devices listen on, and the port their
# encrypted mode listens on too (developer.bluetti.com).
DEFAULT_TCP_PORT = 502


def add_connection_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the transport options to a parser, TCP and serial."""
    transport = parser.add_mutually_exclusive_group()
    transport.add_argument("-c", "--host", type=str, help="IP-address of the device")
    transport.add_argument(
        "-s",
        "--serial",
        type=str,
        metavar="DEVICE",
        help=(
            "serial port to speak Modbus RTU on, instead of --host: a port "
            "path (/dev/ttyUSB0, COM3) or any URL pyserial understands, "
            "notably socket://ip:port for a transparent serial-to-TCP "
            "gateway (an ESP32 bridge, a hardware converter), where the line "
            "settings below live in the gateway and are ignored here."
        ),
    )
    parser.add_argument(
        "-p", "--port", type=int, help="Port of the device (with --host)"
    )
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
            "Modbus unit id (default: 1). On a shared RS485 bus this is how a "
            "device is picked; never address another unit id on an AC500 or "
            "EP500Pro - see HARDWARE_TESTING.md."
        ),
    )


def check_connection_arguments(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> None:
    """Refuse the option pairs argparse's own group cannot express."""
    if args.serial is not None and args.port is not None:
        parser.error("--port belongs to --host; --serial carries no port")


def connection_params(
    args: argparse.Namespace,
) -> ModbusTcpParams | ModbusSerialParams:
    """The parameters for whichever transport the arguments name."""
    if args.serial is not None:
        return ModbusSerialParams(
            device=args.serial,
            baudrate=args.baud,
            parity=args.parity,
            stopbits=args.stopbits,
            framer="rtu",
        )
    return ModbusTcpParams(
        host=args.host, port=DEFAULT_TCP_PORT if args.port is None else args.port
    )
