import argparse
import asyncio

from ..devices.getter import get_device
from ..modbus import Backend, BluettiModbusClient


async def async_read(host: str, port: int, type: str, backend: Backend) -> None:
    if get_device(type) is None:
        print("type not supported")
        return

    client = BluettiModbusClient(host, port, type, backend=backend)

    try:
        result = await client.read()
    finally:
        await client.aclose()

    for r in result:
        print(r)


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
        default="pymodbus",
        help=(
            "Modbus backend (default: pymodbus, what both HA integrations use "
            "today). tmodbus is an experimental trial - pip install "
            "'bluetti-modbus[cli-tmodbus]' first. See CONTRIBUTING.md."
        ),
    )
    args = parser.parse_args()

    if args.host is None or args.port is None or args.type is None:
        parser.print_help()
        return

    asyncio.run(async_read(args.host, args.port, args.type, args.backend))
