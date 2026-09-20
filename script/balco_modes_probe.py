#!/usr/bin/env python3
"""Does a Balco 260's Modbus TCP gateway reach the app's internal registers?

Provisional companion to `tou_codec.py`, for one owner's own Balco 260.
The question it answers decides whether the working modes (2005, 2241)
and the TOU scheduler table (26000, 26001+) can ever be driven over
Modbus TCP:

- Reads of the internal space are known to fail on a Balco 260: all 54
  internal addresses tried on 2026-09-16 (2005, 26000 and 26001 among
  them) answered "illegal data address". Step 1 re-checks that, dated
  with the unit's IoT firmware version, and also tries function code 0x04
  (input registers) in case the gateway exposes the internal space there.
- Writes are the open question. The gateway demonstrably TRANSLATES a
  documented write into the internal space (57016 is confirmed at 2022,
  see bluetti_device.py's _INTERNAL_WRITE_ADDRESS) - nobody has tried a
  write addressed straight at an internal register. Step 2 writes the
  working mode the app already shows back to 2005 (function code 0x06):
  idempotent by construction. "Illegal data address" closes the TCP
  route; a confirmation at 2005 opens it for 2241, 2266 and the TOU table.
- Step 3, only once step 2 has passed: writes one inert TOU period
  (function code 0x10, 14 registers at 26001) built by tou_codec - the
  scheduler left disabled (26000 untouched), both records writing "AC
  output on" to the AC switch (2011), i.e. the state the unit is already
  in even if it ever fired - then the app's time-plan page says whether
  the two-records-per-period reading and the codec are right.

Unit id 1 only, one register per request, the same pacing as
probe_unexplored_registers.py. Every write needs --yes and prints what it
is about to send first. Nothing here ever writes 26000, 2006 (control
events) or 2029.

    pip install "modbus-connection[tmodbus]"
    python3 balco_modes_probe.py --host 192.168.1.50                       # step 1
    python3 balco_modes_probe.py --host 192.168.1.50 --write-mode 2 --yes  # step 2
    python3 balco_modes_probe.py --host 192.168.1.50 --write-mode 2 --fc16 --yes  # step 2, FC 0x10
    python3 balco_modes_probe.py --host 192.168.1.50 --write-period 1,2 --yes  # step 3

--write-mode takes the value the app shows: 1 custom, 2 self-consumption,
3 backup (tou_codec.WorkingMode); --fc16 sends it as a one-register Write
Multiple Registers instead of Write Single Register, in case the gateway
filters the two function codes differently. --write-period takes the two
timeType values to try for the start and end record - they were not
decompiled.

Run on a real Balco 260 on 2026-09-20 (IoT 50012.01.x): step 1, every
address "illegal data address" under FC 0x03 and under FC 0x04 alike (the
function code is accepted, the space is not exposed there either); step 2,
FC 0x06 2005 <- 2 refused with "illegal data address" - the gateway does
not forward a write addressed at the internal space, only translates the
documented ones.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import struct
import sys
from datetime import UTC, datetime
from pathlib import Path

from modbus_connection import ModbusTcpParams
from modbus_connection.exceptions import (
    IllegalDataAddressError,
    IllegalFunctionError,
    ModbusError,
    ModbusExceptionError,
    ModbusProtocolError,
    ModbusTimeoutError,
)
from modbus_connection.tmodbus import ModbusConnection

_SPEC = importlib.util.spec_from_file_location(
    "tou_codec", Path(__file__).with_name("tou_codec.py")
)
assert _SPEC is not None and _SPEC.loader is not None
tou = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = tou
_SPEC.loader.exec_module(tou)

# A Balco 260 serves these; read first to prove the unit is alive and to
# date the run. d_iot_ver is two registers (dotted_version, little-endian
# words), read one at a time like everything else here.
LIVENESS_ADDRESS = 50001  # d_num_inverters, 1..10
IOT_VERSION_ADDRESS = 53011

# (name, address, count) - the internal registers step 1 reads.
READS: list[tuple[str, int, int]] = [
    ("WORKING_MODE", tou.WORKING_MODE, 1),
    ("EMS_CTRL_MODE_SET", tou.EMS_CTRL_MODE_SET, 1),
    ("SOC_SET_LOW", tou.SOC_SET_LOW, 1),
    ("SOC_SET_HIGH", tou.SOC_SET_HIGH, 1),
    ("EMS_SETTINGS", 5800, 1),
    ("AC_EMS_FEATURE_EN", 5801, 1),
    ("TOU_CTRL_ENABLE", tou.TOU_CTRL_ENABLE, 1),
    ("TOU_CTRL[0]", tou.TOU_CTRL, tou.PERIOD_REGISTERS),
]
FC04_ADDRESSES = [tou.WORKING_MODE, tou.TOU_CTRL_ENABLE, tou.TOU_CTRL]

NEVER_WRITE = {tou.TOU_CTRL_ENABLE, 2006, 2029}


def _iot_version(words: list[int]) -> str:
    raw = words[0] | (words[1] << 16)
    return f"{raw // 10000}.{(raw // 100) % 100:02d}.{raw % 100:02d}"


class Prober:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.conn = ModbusConnection(
            ModbusTcpParams(host=args.host, port=args.port),
            timeout=args.timeout,
            message_spacing=args.delay,
        )
        self.unit = self.conn.for_unit(1)
        self.results: list[dict[str, object]] = []

    async def recover(self) -> bool:
        print(f"  dropping the link, waiting {self.args.recover_delay}s, re-opening...")
        try:
            await self.conn.disconnect()
        except ModbusError:
            pass
        await asyncio.sleep(self.args.recover_delay)
        try:
            await self.conn.connect()
        except ModbusError as err:
            print(f"  could not re-open the link: {type(err).__name__}: {err}")
            return False
        return await self.alive()

    async def alive(self) -> bool:
        try:
            words = await self.unit.read_holding_registers(LIVENESS_ADDRESS, 1)
        except ModbusError as err:
            print(f"  liveness check failed: {type(err).__name__}: {err}")
            return False
        print(f"  liveness check: register {LIVENESS_ADDRESS} = {words[0]}")
        return True

    async def read_one(
        self, name: str, address: int, count: int, *, fc: int = 3
    ) -> None:
        rec: dict[str, object] = {
            "op": f"read-fc{fc:02d}",
            "name": name,
            "address": address,
        }
        label = f"FC{fc:02d} {name:20s} {address:<6} x{count:<2}"
        read = (
            self.unit.read_input_registers
            if fc == 4
            else self.unit.read_holding_registers
        )
        words: list[int] = []
        try:
            for i in range(count):
                words += await read(address + i, 1)
        except IllegalDataAddressError:
            rec["status"] = "illegal-address"
            rec["words"] = words
            served = f" ({len(words)}/{count} served first)" if words else ""
            print(f"{label} -> not served (illegal data address){served}")
        except IllegalFunctionError:
            rec["status"] = "illegal-function"
            print(f"{label} -> function code not supported")
        except ModbusExceptionError as err:
            rec["status"] = f"modbus-exception:{type(err).__name__}"
            print(f"{label} -> device exception {type(err).__name__}: {err}")
        except (ModbusTimeoutError, ModbusProtocolError) as err:
            rec["status"] = (
                "timeout" if isinstance(err, ModbusTimeoutError) else "protocol"
            )
            rec["error"] = str(err)
            print(f"{label} -> {rec['status']}: {err}")
            await self.recover()
        else:
            rec["status"] = "data"
            rec["words"] = words
            shown = " ".join(f"{w:04x}" for w in words)
            print(f"{label} -> [{shown}]")
            if name.startswith("TOU_CTRL[") and any(words):
                try:
                    events, order = tou.decode_table(words)
                    rec["decoded"] = [e.describe() for e in events]
                    for e in events:
                        print(f"{'':32s} {order}: {e.describe()}")
                except ValueError as err:
                    print(f"{'':32s} not decodable as TOU records: {err}")
        self.results.append(rec)

    async def write_single(
        self, name: str, address: int, value: int, *, fc16: bool = False
    ) -> bool:
        """FC 0x06 (or a one-register FC 0x10). True if the device confirmed it."""
        assert address not in NEVER_WRITE
        fc = "fc16" if fc16 else "fc06"
        rec: dict[str, object] = {
            "op": f"write-{fc}",
            "name": name,
            "address": address,
            "value": value,
        }
        label = f"{fc.upper()} {name:20s} {address:<6} <- {value}"
        try:
            if fc16:
                await self.unit.write_registers(address, [value])
            else:
                await self.unit.write_register(address, value)
        except IllegalDataAddressError:
            rec["status"] = "illegal-address"
            print(
                f"{label} -> refused: illegal data address (the gateway does not forward it)"
            )
        except ModbusExceptionError as err:
            rec["status"] = f"modbus-exception:{type(err).__name__}"
            print(f"{label} -> device exception {type(err).__name__}: {err}")
        except ModbusProtocolError as err:
            echo = _confirmation(err)
            rec["status"] = "confirmed-elsewhere" if echo else "protocol"
            rec["echo"] = echo
            rec["error"] = str(err)
            if echo:
                print(
                    f"{label} -> the device confirmed function 0x06 at register {echo[0]} "
                    f"= {echo[1]} (not {address}): applied, echoed at another address"
                )
            else:
                print(f"{label} -> protocol error: {err}")
                await self.recover()
        except ModbusTimeoutError as err:
            rec["status"] = "timeout"
            rec["error"] = str(err)
            print(f"{label} -> no reply: {err}")
            await self.recover()
        else:
            rec["status"] = "confirmed"
            print(
                f"{label} -> confirmed at {address} (the gateway forwards internal writes)"
            )
        self.results.append(rec)
        return rec["status"] in ("confirmed", "confirmed-elsewhere")

    async def write_period(self, time_types: tuple[int, int]) -> None:
        """FC 0x10 of one inert period at TOU_CTRL[0]."""
        period = tou.weekly(
            tou.seconds(0, 1),
            tou.seconds(0, 2),
            week=tou.EVERY_WEEKDAY,
            target_reg=tou.AC_SWITCH,
            start_value=1,
            end_value=1,
            time_type_start=time_types[0],
            time_type_end=time_types[1],
        )
        regs = period.to_registers()
        address = tou.period_address(0)
        print(
            "about to write one period (14 registers) - AC output ON at 00:01 and ON at 00:02,"
        )
        print(
            "every day - the state the unit is already in, with the scheduler left disabled:"
        )
        print(f"  start: {period.start.describe()}")
        print(f"  end:   {period.end.describe()}")
        print(f"  words: {' '.join(f'{w:04x}' for w in regs)} at {address}")
        rec: dict[str, object] = {"op": "write-fc16", "address": address, "words": regs}
        try:
            await self.unit.write_registers(address, regs)
        except IllegalDataAddressError:
            rec["status"] = "illegal-address"
            print("FC16 -> refused: illegal data address")
        except ModbusExceptionError as err:
            rec["status"] = f"modbus-exception:{type(err).__name__}"
            print(f"FC16 -> device exception {type(err).__name__}: {err}")
        except (ModbusTimeoutError, ModbusProtocolError) as err:
            rec["status"] = (
                "timeout" if isinstance(err, ModbusTimeoutError) else "protocol"
            )
            rec["error"] = str(err)
            print(f"FC16 -> {rec['status']}: {err}")
            await self.recover()
        else:
            rec["status"] = "confirmed"
            print(
                "FC16 -> confirmed. Now open the app's time-plan page: does it show a plan"
            )
            print(
                "        00:01-00:02, every day, AC output? Then delete it from the app."
            )
        self.results.append(rec)

    async def run(self) -> int:
        print(f"connecting to {self.args.host}:{self.args.port} unit 1")
        try:
            await self.conn.connect()
        except ModbusError as err:
            print(f"could not connect: {type(err).__name__}: {err}")
            return 2
        try:
            if not await self.alive():
                print(
                    "the unit does not answer a register it is documented to have - stopping."
                )
                return 2
            try:
                words = await self.unit.read_holding_registers(IOT_VERSION_ADDRESS, 1)
                words += await self.unit.read_holding_registers(
                    IOT_VERSION_ADDRESS + 1, 1
                )
                print(f"  IoT firmware {_iot_version(words)}")
                self.results.append(
                    {
                        "op": "read-fc03",
                        "name": "d_iot_ver",
                        "address": IOT_VERSION_ADDRESS,
                        "status": "data",
                        "words": words,
                        "decoded": _iot_version(words),
                    }
                )
            except ModbusError as err:
                print(f"  IoT firmware version not read: {type(err).__name__}: {err}")

            if self.args.write_mode is None and self.args.write_period is None:
                print("\nstep 1: reading the internal registers, one at a time\n")
                for name, address, count in READS:
                    await self.read_one(name, address, count)
                if not self.args.no_fc04:
                    print(
                        "\nstep 1b: the same three addresses as input registers (FC 0x04)\n"
                    )
                    for address in FC04_ADDRESSES:
                        await self.read_one(f"fc04@{address}", address, 1, fc=4)

            if self.args.write_mode is not None:
                value = self.args.write_mode
                print(
                    f"\nstep 2: writing working mode {value} ({tou.WorkingMode(value).name}) back to 2005\n"
                )
                await self.write_single(
                    "WORKING_MODE", tou.WORKING_MODE, value, fc16=self.args.fc16
                )

            if self.args.write_period is not None:
                print("\nstep 3: one inert TOU period at 26001\n")
                await self.write_period(self.args.write_period)

            print("\nfinal liveness check")
            await self.alive()
        finally:
            await self.conn.close()
        return 0

    def report(self) -> None:
        payload = {
            "host": self.args.host,
            "probed_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "results": self.results,
        }
        with open(self.args.output, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"\nfull results written to {self.args.output}")


def _confirmation(err: ModbusProtocolError) -> tuple[int, int] | None:
    """The (address, value) of a Write Single Register confirmation that a
    strict client rejected for echoing another address - the Balco 260's
    known habit for documented registers (bluetti_device.py)."""
    response = getattr(err.__cause__, "response_bytes", None)
    if not isinstance(response, bytes) or len(response) != 5:
        return None
    function_code, address, value = struct.unpack(">BHH", response)
    return (address, value) if function_code == 0x06 else None


def _time_types(text: str) -> tuple[int, int]:
    try:
        start, end = (int(x) for x in text.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError("expected two integers, e.g. 1,2") from None
    if not (0 <= start <= 7 and 0 <= end <= 7):
        raise argparse.ArgumentTypeError("timeType is a 3-bit field: 0..7")
    return start, end


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--host", required=True, help="IP address of the Balco 260")
    p.add_argument("--port", type=int, default=502)
    p.add_argument(
        "--timeout", type=float, default=5.0, help="seconds to wait for each reply"
    )
    p.add_argument("--delay", type=float, default=0.5, help="seconds between requests")
    p.add_argument("--recover-delay", type=float, default=5.0)
    p.add_argument(
        "--no-fc04", action="store_true", help="skip the input-register reads"
    )
    p.add_argument(
        "--write-mode",
        type=int,
        choices=[1, 2, 3],
        help="step 2: write this working mode back to 2005 - pass the value the app "
        "shows (1 custom, 2 self-consumption, 3 backup), so the write changes nothing",
    )
    p.add_argument(
        "--fc16",
        action="store_true",
        help="send --write-mode as a one-register Write Multiple Registers (0x10)",
    )
    p.add_argument(
        "--write-period",
        type=_time_types,
        metavar="START,END",
        help="step 3: write one inert period at 26001 with these two timeType values "
        "(unknown - a guess to check in the app); only after step 2 has passed",
    )
    p.add_argument("--output", default=None, help="JSON results file")
    p.add_argument("--yes", action="store_true", help="skip the confirmations")
    args = p.parse_args(argv)
    if args.output is None:
        args.output = f"balco-modes-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.json"
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    writes = []
    if args.write_mode is not None:
        writes.append(f"FC{16 if args.fc16 else '06'} 2005 <- {args.write_mode}")
    if args.write_period is not None:
        writes.append("FC16 26001 <- 14 registers (one inert period)")
    if not args.yes:
        print(
            "Disable the Bluetti Modbus integration entry in Home Assistant (and stop"
        )
        print("anything else polling this device) before continuing.")
        if writes:
            print("This run WRITES to the device: " + "; ".join(writes))
        if input("continue? [y/N] ").strip().lower() != "y":
            return 1
    prober = Prober(args)
    try:
        code = asyncio.run(prober.run())
    finally:
        prober.report()
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
