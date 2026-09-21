#!/usr/bin/env python3
"""Test one documented setting register for writes, on the owner's terms.

For a device whose profile is still read-only: reads the register, writes
the value it already holds (which changes nothing on the device), and
reports how the device confirmed it - the Balco family confirms a Write
Single Register with the setting's address in its own internal register
space rather than the Modbus one, and that echoed address is what the
library records per device (bluetti_device.py, _INTERNAL_WRITE_ADDRESS).
With --value it then writes the new value, reads it back, and restores the
original unless --keep is given.

Only the documented setting registers are accepted, at unit id 1:

    57001  AC output switch      - refused unless --allow-ac-output: on a
                                   FridgePower this powers the fridge
    57005  DC output switch
    57009  grid charging switch
    57010  grid feed-in switch
    57016  battery SOC low threshold (%)
    57017  battery SOC high threshold (%)

Stop anything else polling the device first: in Home Assistant, disable
the integration entry itself (the switch at the top of its page - disabling
the devices below it is not enough, the entry keeps polling), then restart
Home Assistant so the unit drops that connection. Each step waits for the
previous reply; nothing is retried.

    pip install "modbus-connection[tmodbus]" "tmodbus[async-serial]"
    python3 write_probe.py --host 192.168.1.50 --device fp --register 57017
    python3 write_probe.py --host 192.168.1.50 --device fp --register 57017 --value 95 --yes
"""

from __future__ import annotations

import argparse
import asyncio
import json
import struct
import sys
from datetime import UTC, datetime

from modbus_connection import ModbusTcpParams
from modbus_connection.exceptions import (
    IllegalDataAddressError,
    ModbusError,
    ModbusExceptionError,
    ModbusProtocolError,
    ModbusTimeoutError,
)
from modbus_connection.tmodbus import ModbusConnection

REGISTERS: dict[int, tuple[str, range]] = {
    57001: ("ac_o_switch", range(2)),
    57005: ("dc_o_switch", range(2)),
    57009: ("g_i_switch", range(2)),
    57010: ("g_o_switch", range(2)),
    57016: ("b_soc_low", range(101)),
    57017: ("b_soc_high", range(101)),
}
DEVICES = (
    "balco260",
    "balco500",
    "fp",
    "transfer-hub",
    "unknown",
    "ac500",
    "ac200l",
    "ep500p",
)


def _confirmation(err: ModbusProtocolError) -> tuple[int, int] | None:
    """The (address, value) of a Write Single Register confirmation a strict
    client rejected for carrying another address."""
    response = getattr(err.__cause__, "response_bytes", None)
    if not isinstance(response, bytes) or len(response) != 5:
        return None
    function_code, address, value = struct.unpack(">BHH", response)
    return (address, value) if function_code == 0x06 else None


class WriteProbe:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.conn = ModbusConnection(
            ModbusTcpParams(host=args.host, port=args.port), timeout=args.timeout
        )
        self.unit = self.conn.for_unit(1)
        self.steps: list[dict[str, object]] = []

    async def read(self, label: str) -> int | None:
        address = self.args.register
        rec: dict[str, object] = {"op": "read", "step": label, "address": address}
        try:
            value = (await self.unit.read_holding_registers(address, 1))[0]
        except ModbusError as err:
            rec["status"] = type(err).__name__
            rec["error"] = str(err)
            print(f"read  {address} ({label}) -> {type(err).__name__}: {err}")
            self.steps.append(rec)
            return None
        rec["status"] = "ok"
        rec["value"] = value
        print(f"read  {address} ({label}) -> {value}")
        self.steps.append(rec)
        return value

    async def write(self, label: str, value: int) -> bool:
        address = self.args.register
        rec: dict[str, object] = {
            "op": "write",
            "step": label,
            "address": address,
            "value": value,
        }
        head = f"write {address} <- {value} ({label})"
        ok = False
        try:
            await self.unit.write_register(address, value)
        except IllegalDataAddressError:
            rec["status"] = "illegal-address"
            print(
                f"{head} -> refused: illegal data address (not writable over Modbus TCP)"
            )
        except ModbusExceptionError as err:
            rec["status"] = f"modbus-exception:{type(err).__name__}"
            print(f"{head} -> device exception {type(err).__name__}: {err}")
        except ModbusProtocolError as err:
            echo = _confirmation(err)
            rec["echo"] = echo
            rec["error"] = str(err)
            if echo:
                rec["status"] = "confirmed-at-internal-address"
                ok = True
                print(
                    f"{head} -> confirmed at internal register {echo[0]} = {echo[1]} "
                    f"(the device's own address for {address}; this is the echo to report)"
                )
            else:
                rec["status"] = "protocol-error"
                print(f"{head} -> protocol error: {err}")
        except ModbusTimeoutError as err:
            rec["status"] = "timeout"
            rec["error"] = str(err)
            print(f"{head} -> no reply: {err}")
        else:
            rec["status"] = "confirmed"
            ok = True
            print(f"{head} -> confirmed at {address} (a plain Modbus confirmation)")
        self.steps.append(rec)
        return ok

    async def run(self) -> int:
        args = self.args
        name = REGISTERS[args.register][0]
        print(f"register {args.register} ({name}) on {args.host}:{args.port}, unit 1\n")
        await self.conn.connect()
        try:
            current = await self.read("before")
            if current is None:
                print("\nthe register does not read; nothing written")
                return 1
            if not await self.write("same value", current):
                print("\nthe device did not accept the write; nothing changed")
                return 1
            after = await self.read("after the same-value write")
            if after != current:
                print(f"\nunexpected: the register now reads {after}, not {current}")
                return 1
            if args.value is None:
                print("\nsame-value write accepted - the register takes writes.")
                return 0
            if not await self.write("new value", args.value):
                return 1
            await asyncio.sleep(args.settle)
            new = await self.read("after the new value")
            if new != args.value:
                print(f"\nthe register reads {new} after writing {args.value}")
            else:
                print(f"\nthe register reads {args.value}: the write applied.")
            if args.keep:
                print(f"--keep: {args.value} left in place")
                return 0
            if not await self.write("restore", current):
                print(f"\ncould not restore {current}: set it back in the app")
                return 1
            await asyncio.sleep(args.settle)
            restored = await self.read("after restore")
            print(
                f"\nrestored to {current}"
                if restored == current
                else f"\nafter restoring, the register reads {restored}, not {current}: check the app"
            )
            return 0 if restored == current else 1
        finally:
            await self.conn.close()

    def save(self) -> None:
        args = self.args
        payload = {
            "generated": datetime.now(UTC).isoformat(),
            "host": args.host,
            "device": args.device,
            "register": args.register,
            "name": REGISTERS[args.register][0],
            "steps": self.steps,
        }
        with open(args.output, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"full results written to {args.output}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--host", required=True, help="IP address of the device")
    p.add_argument("--port", type=int, default=502)
    p.add_argument(
        "--device", choices=DEVICES, required=True, help="which device this is"
    )
    p.add_argument(
        "--register",
        type=int,
        choices=sorted(REGISTERS),
        required=True,
        help="the documented setting register to test",
    )
    p.add_argument(
        "--value",
        type=int,
        help="after the same-value write: write this value, read it back, restore",
    )
    p.add_argument("--keep", action="store_true", help="leave --value in place")
    p.add_argument(
        "--allow-ac-output",
        action="store_true",
        help="allow register 57001, the AC output switch - everything on the AC "
        "output loses power when it is written to 0",
    )
    p.add_argument("--timeout", type=float, default=5.0, help="seconds per reply")
    p.add_argument(
        "--settle",
        type=float,
        default=2.0,
        help="seconds between a write and its read-back",
    )
    p.add_argument("--output", default=None, help="JSON results file")
    p.add_argument("--yes", action="store_true", help="skip the confirmation prompts")
    args = p.parse_args(argv)
    if args.register == 57001 and not args.allow_ac_output:
        p.error(
            "57001 is the AC output switch; pass --allow-ac-output if you really mean it"
        )
    if args.value is not None and args.value not in REGISTERS[args.register][1]:
        p.error(f"--value {args.value} is outside the register's range")
    if args.keep and args.value is None:
        p.error("--keep needs --value")
    if args.output is None:
        stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
        args.output = f"write-{args.device}-{args.register}-{stamp}.json"
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if not args.yes:
        print(
            "This writes to the device: first the value the register already holds,\n"
            f"then {args.value if args.value is not None else 'nothing else'}.\n"
            "Disable the Home Assistant integration entry itself (not just its devices),\n"
            "restart Home Assistant, and stop anything else polling the unit first."
        )
        if input("Continue? [y/N] ").strip().lower() != "y":
            return 1
    probe = WriteProbe(args)
    try:
        return asyncio.run(probe.run())
    finally:
        probe.save()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
