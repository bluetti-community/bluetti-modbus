# Python: async client for BLUETTI power stations over Modbus

[![PyPI Version][pypi-shield]][pypi]
[![Python Versions][python-versions-shield]][pypi]
[![License][license-shield]](LICENSE)
[![Build Status][build-shield]][build]
[![Open in Dev Containers][devcontainer-shield]][devcontainer]

Asynchronous Python client for BLUETTI power stations over their local Modbus
TCP interface.

## About

This package decodes what a BLUETTI device reports over Modbus TCP, using
the register maps documented in [bluetti-registers][bluetti-registers]. It is
built on [`modbus-connection`][modbus-connection], a backend-neutral async
Modbus toolkit: the caller owns the connection and hands the library a
`ModbusUnit`, so several device objects can share one connection.

The library is **read-only by default**. The few fields a device is known to
accept writes for (output switches, SOC thresholds - see the table) support
`await device.write(field_name, value)`, validated against the schema's own
bounds with [`probatio`][probatio] before anything reaches the device.

## Supported devices

| Device | `get_device()` id | Status | Writable |
|---|---|---|---|
| Balco 260 | `balco260` | Confirmed by BLUETTI and on real hardware | AC output, grid in/out switches, SOC thresholds |
| Balco 500 | `balco500` | From BLUETTI's register spec, no unit seen yet | - |
| EP2000 | `ep2000` | From BLUETTI's register spec, no unit seen yet | - |
| S Meter | `smeter` | Confirmed by BLUETTI and on real hardware | - |
| AC500 | `ac500` | Confirmed on real hardware ([evidence][ev-ac500]) | AC/DC output switches |
| AC200L | `ac200l` | Beta - confirmed on a real unit against its BLE readings ([evidence][ev-ac200l]) | AC/DC output switches |
| EP500Pro | `ep500p` | Beta - two real units ([evidence][ev-ep500p]) | AC/DC output switches |
| FridgePower | `fp` | Confirmed on three real units ([evidence][ev-fp]) | DC output, grid charging switches |

Notes:

- **Balco 260** reports up to five BC260 expansion packs - see
  [Multiple battery packs](#multiple-battery-packs-balco-260).
- **Balco 500 / EP2000** come from BLUETTI's official register spec and have
  not been read on real hardware, so nothing is writable there yet.
- **AC500 / EP500Pro / AC200L** share one register layout (the AC500's) with
  per-device scales. SOC thresholds are read-only on them; energies and PV
  fields on the AC200L and EP500Pro are carried over unverified. None of
  them exposes per-pack data over Modbus TCP.
- **FridgePower** is a Balco-family device on the Modbus side: the full
  BalcoXX register set, pack voltage at 0.01 V, signed grid power. Its SOC
  thresholds refuse writes (unlike the Balco 260's); the AC output and grid
  feed-in switches are untried.
- `AC200L`, `EP500P` and `FP` are named after the type string the device
  itself gives at register 50200.

Field names, units and addresses come from
[bluetti-registers][bluetti-registers]: every `devices/*.py` is generated
from it by `import.py`, and a [scheduled workflow][sync-devices] keeps them
in sync. Have a device this doesn't support, or a value that looks wrong?
See [HARDWARE_TESTING.md](HARDWARE_TESTING.md) - no coding experience
required.

## Enabling Modbus TCP on your device

Modbus TCP is off by default - enable it in the device's own web interface
first, then point this library at its IP address. The steps vary by model;
see the official [bluetti-modbus-tcp-slave][official-docs] documentation.

## Installation

```bash
pip install bluetti-modbus
```

Python 3.12 or newer. On a machine still on an older one, `uv` runs the
commands without installing anything system-wide:

```bash
uvx --python 3.13 --from "bluetti-modbus[cli]" bluetti-modread -c 10.2.1.60 -t balco260
```

That pulls in only `modbus-connection`'s backend-neutral interface - enough
to use the device classes against a `ModbusUnit` you already have. The
`bluetti-modread` CLI and the examples below need a concrete backend, via
the `cli` extra ([tmodbus][tmodbus], the default):

```bash
pip install "bluetti-modbus[cli]"
```

`--backend pymodbus` is also available (`pip install
"bluetti-modbus[cli-pymodbus]"`).

## Usage

The caller owns the connection and hands the library a unit:

```python
import asyncio

from modbus_connection.tmodbus import connect_tcp

from bluetti_modbus_lib import BluettiModbusConnectionError, get_device


async def main() -> None:
    connection = await connect_tcp("10.2.1.60", port=502)
    try:
        unit = connection.for_unit(1)
        device = get_device("balco260", unit)
        if device is None:
            return

        try:
            await device.async_update_with_retry()
        except BluettiModbusConnectionError as err:
            print("Could not read the device:", err)
            return

        print(device.values["b_soc"], "%")
        print(device.values["b_v"], "V")
        print(device.values["d_inverter_status"])
    finally:
        await connection.close()


asyncio.run(main())
```

- There is no self-describing header to detect the model from:
  `get_device()` takes the id from the table above, and the caller has to
  know which device it is talking to.
- `async_update_with_retry()` retries a transient acknowledge/busy response
  (Modbus codes 5/6), which these devices return now and then on registers
  that otherwise read fine. `async_update()` raises on the first failure
  instead. A communication failure raises `BluettiModbusConnectionError`
  (also a `modbus_connection.ModbusError`).
- Decoded values land on `device.values`, a `dict[str, Any]` keyed by field
  name. `field_names()` and `get_field()` expose each field's address, type,
  scale, unit and whether it is writable - protocol facts only, no UI
  concepts.
- Everything a caller needs (`get_device`, the device classes, the
  exceptions, `BluettiModbusClient`, the enums, the pack helpers) is
  importable from `bluetti_modbus_lib` directly.

### Multiple battery packs (Balco 260)

A Balco 260 takes up to `MAX_BATTERY_PACKS` (5) BC260 packs. Pack 1's own
data (`b_soc`, `b_v`, serial, ...) is part of the main device's fields. The
pack count and every aggregate field (`d_num_battery_packs`, `b_v_total`,
`b_soc_total`, ... - `AGGREGATE_SUMMARY_FIELDS`) are only served at the
aggregate unit id `AGGREGATE_SLAVE_ID` (250); at the device's own unit id
the count always reads 0:

```python
from bluetti_modbus_lib import aggregate_pack_summary

summary = aggregate_pack_summary(connection)
await summary.async_update_with_retry()
print(summary.values["d_num_battery_packs"], "packs")
```

Each expansion pack answers the "Each Pack Base Information" block
(`PACK_INFO_FIELDS`) at its own unit id, starting at
`EXPANSION_PACK_FIRST_SLAVE_ID` (41): pack 2 at 41, pack 3 at 42, and so on.
`pack_slave_id()` does the arithmetic, `battery_pack()` builds a `Balco260`
restricted to that block:

```python
from bluetti_modbus_lib import battery_pack, pack_slave_id

pack2 = battery_pack(connection, pack_slave_id(2))
await pack2.async_update_with_retry()
print(pack2.values["b_soc"], "%")
```

A slot can answer its serial number and zeros for everything else (a
firmware issue BLUETTI has acknowledged). `pack_is_reporting(values)` tells
a reporting pack from such a slot; while it is False, treat the pack as
absent rather than as "0 %, 0 V".

These helpers are Balco 260 only. On the AC500, EP500Pro and AC200L,
`d_num_battery_packs` is a fixed maximum, not a count, and registers
51200-51249 are a window onto whichever pack the BLUETTI app has selected -
the selector is not reachable over Modbus TCP, so per-pack data cannot be
read from that family. Never address another unit id on those devices (see
[Device behaviours](#device-behaviours-this-library-works-around)).

### Modbus RTU over a serial line (RS485)

Some devices carry an RS485 port instead of, or alongside, Modbus TCP - an
EP2000's EMS is the case this was written for. `BluettiModbusClient` takes
a serial device in place of a host, and the CLI a `--serial`:

```python
client = BluettiModbusClient(device_type="ep2000", serial_device="/dev/ttyUSB0")
client = BluettiModbusClient(
    device_type="ep2000",
    serial_device="socket://192.168.1.50:8899",  # a serial-to-TCP gateway
    unit_id=1,
)
```

The device string is a port path (`/dev/ttyUSB0`, `COM3`) or any URL
pyserial understands; `socket://host:port` reaches a transparent
serial-to-TCP gateway - an ESP32 bridge, a hardware converter - in which
case the line settings live in the gateway and the ones here are ignored.
`baudrate` (9600), `parity` (`N`), `stopbits` (1) and `bytesize` (8) are
the defaults for a real port, and `unit_id` picks the device on a shared
bus. Framing is RTU.

Nothing about this is verified against a BLUETTI device yet: no unit is
known to answer as a Modbus slave on its RS485 port, and an EMS may well
be the *master* there (see `HARDWARE_TESTING.md` before wiring anything to
a live bus).

### Encrypted mode (Modbus/TLS)

A device's web page offers an encrypted Modbus TCP mode: it is Modbus over
TLS with your own certificates - the page takes a CA certificate, a server
certificate and its key, and the client authenticates with a certificate
signed by that CA, on the same port as plain mode. `BluettiModbusClient`
speaks it with `tls=True` (`verify` = the CA file, `check_hostname=False`,
`client_cert`/`client_key`); the device classes take a
`modbus_connection.ModbusTlsParams` connection the same way. Leave the mode
off unless you have uploaded certificates: with it on, plain connections
are refused.

## CLI

The optional CLI reads a device straight from the terminal - for testing,
not something another application should build on (see
[Architecture](#architecture)):

```bash
bluetti-modread -c 10.2.1.60 -p 502 -t balco260
```

Over a serial line, `--serial` replaces `--host`:

```bash
bluetti-modread -s /dev/ttyUSB0 -t ep2000 --baud 9600 --parity N --stopbits 1
bluetti-modread -s socket://192.168.1.50:8899 -t ep2000 -u 1
```

Example output from a real Balco 260 (truncated - one line per field):

```text
d_num_inverters: 1
ac_o_p_total: 84 W
pv_i_p_total: 0 W
ac_o_e_total: 64.7 kWh
d_inverter_status: InverterStatus.GridConnectedOperation
g_i_f: 50.0 Hz
b_v: 27.1 V
b_soc: 100 %
b_cycle_count: 8
b_i_e: 23420 Wh
```

The output ends with the number of Modbus block reads the update took
(`15 Modbus block reads`) - a quick way to notice a profile whose fields
do not pool into reads as expected.

### Writing a setting

`bluetti-modwrite` writes one setting register - the switches and SOC
thresholds a device declares writable, nothing else:

```bash
bluetti-modwrite -c 10.2.1.60 -p 502 -t balco260 -f b_soc_high -v 95
bluetti-modwrite -s /dev/ttyUSB0 -t ep2000 -f b_soc_high -v 95   # same over RS485
```

| | |
|---|---|
| `-c`, `-p` / `-s` … | the same transport options as the reader: TCP, or a serial line |
| `-t TYPE` | device type |
| `-f FIELD` | the field to write; an unknown or read-only name lists the writable ones |
| `-v VALUE` | a number, or an enum field's member name |
| `-y`, `--yes` | skip the confirmation prompt |
| `--allow-ac-output` | required to write the AC output switch - it powers whatever the outlets feed |
| `-b` | backend, as for the reader |

It reads that one field - one block read, not a whole device refresh -
prints `old -> new`, asks with the connection closed, then reconnects to
write and read the value back. The flags follow the `bluetti-modwrite`
in Patrick762's own bluetti-modbus-lib, so a user of that one does not
have to relearn the command.

> Stop anything else polling the device first - a write landing while Home
> Assistant is mid-poll collides on a Modbus stack that takes one client at
> a time. `script/write_probe.py`'s own note says how: disable the
> integration entry itself, not just its devices, and restart Home
> Assistant.

Most cumulative energies (`ac_o_e_total`, ...) are in kWh; the battery
charge/discharge energies (`b_i_e`, `b_o_e`) are in Wh, as the device
reports them. Field names follow the
[bluetti-registers naming convention][bluetti-registers-naming].

## Architecture

Two things in this library talk Modbus, for two audiences:

- The device classes (`bluetti_modbus_lib.devices`) are the integration
  surface: each takes a `ModbusUnit` built from whichever backend and
  connection the caller manages. This is what an application should build
  on.
- `BluettiModbusClient` (`bluetti_modbus_lib.modbus.client`) owns its own
  connection. It exists for the `bluetti-modread` CLI and standalone use -
  building an application on it would open a second, competing connection
  to the device.

## Device behaviours this library works around

All confirmed on real hardware; the details live in the linked issues.

- **A read touching an unserved register gets no reply.** A Balco-family
  device answers a single-register read of an address it does not serve
  with "illegal data address", but a multi-register read that touches one
  with silence until the timeout. Hence `Balco260`'s `max_span = 20`, the
  AC family's one-block-per-field read plans, and `FP`'s settings block
  read in runs of adjacent registers. For a new profile, run
  `bluetti-modread -t <its own id>` on the device before building on it:
  a dump taken with a neighbouring profile proves the registers, not the
  read plan.
- **AC500 and EP500Pro: unit id 1 only.** A request to any other unit id
  gets no reply, and on an AC500 it froze the Modbus TCP stack until a
  power cycle ([details][ev-ac500]). Nothing in this library, and nothing
  built on it, may address another unit id on that family.
- **Writes are confirmed with the device's internal address.** A Write
  Single Register (0x06) comes back with the right function code and value
  but the setting's address in the device's own register space (the one
  the BLUETTI app uses - 57016 → 2022 on a Balco 260, 57005 → 3008 on the
  portable stations). The write has applied every time; `write()` accepts
  such a confirmation, logs the echoed address at debug when it is the one
  on file (`_INTERNAL_WRITE_ADDRESS` in `base_devices/bluetti_device.py`)
  and at warning when it isn't - that warning is the signal to add an
  entry. Reported to BLUETTI.
- **The internal register space is not reachable over Modbus TCP.** Reads
  and writes of the app's own addresses are refused; only the documented
  registers are translated.

## Related projects

This library is the Modbus layer for Home Assistant integrations built on
top of it:

- [`hassio-bluetti-modbus`][hassio-bluetti-modbus] - a HACS-installable
  custom integration, vendoring this library directly (see its own README
  for why).
- [`bluetti-home-assistant`][bluetti-home-assistant] - the cloud
  integration; its built-in Modbus path, now deprecated in favour of the
  one above, depends on this library via PyPI.
- [home-assistant/core#180602][ha-core-pr] - an in-review attempt at a
  built-in `home-assistant/core` integration for the Modbus-only path.

## Relationship to Patrick762's `bluetti-modbus-lib`

This repository started as a fork of
[Patrick762/bluetti-modbus-lib][patrick-original] and has since diverged
significantly (packaging, testing, retry handling, device coverage).
Patrick762 is still actively maintaining his own version independently and
was asked directly whether he'd like to fold this work back into his project
or join `bluetti-community` - he's not in a position to commit the time to
that right now, which is completely fine.

Since the PyPI name `bluetti-modbus-lib` is his and still actively used, this
project is published on PyPI under a different name, **`bluetti-modbus`**, to
avoid any ambiguity between the two. The GitHub repository itself keeps its
original name.

## Changelog & releases

This repository keeps a change log using [GitHub's releases][releases]
functionality. Publishing a release triggers the PyPI publish workflow
directly (via [Trusted Publishing][trusted-publishing], no stored token),
setting the package version from the release tag.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for how to
get started.

## Setting up a development environment

The easiest way to start is by opening a Codespace here on GitHub, or by
using the [Dev Container][devcontainer] feature of Visual Studio Code -
either installs Python 3.13, the `cli` extra, and every dev tool below
automatically, no local setup required.

[![Open in Dev Containers][devcontainer-shield]][devcontainer]

To set it up manually instead: this project uses a plain `venv` + `pip`
workflow - no Poetry, no Node tooling required. You need at least:

- Python 3.13+

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[cli]"
```

As this repository uses [pre-commit][pre-commit], changes are linted and
formatted on every commit once you've run `pre-commit install` (the
Dev Container does this for you automatically). `script/run_checks.sh`
installs whatever's still missing (ruff, mypy, pytest) and runs all checks
and tests manually, the same way CI does - formatting, ruff, mypy --strict,
and the test suite with 100% coverage required:

```bash
script/run_checks.sh
```

To run just the Python tests:

```bash
pytest
```

`script/format_code.sh` applies ruff's safe autofixes and formats the tree.

## Authors & contributors

The original author of `bluetti-modbus-lib` is [Patrick762][patrick762].
This fork is maintained by [bluetti-community][bluetti-community].

For a full list of all authors and contributors, check
[the contributor's page][contributors].

## Sponsoring

If you want to support this project, you can sponsor
[Patrick762 on GitHub][github-sponsors], the original author.

## Disclaimer

This project is an independent, community-driven effort. It is **not
affiliated with, endorsed by, or supported by** BLUETTI (PowerOak). All
product names, trademarks, and registered trademarks are property of their
respective owners.

The register map is based on BLUETTI's own published
[bluetti-modbus-tcp-slave][official-docs] documentation and the
[bluetti-registers][bluetti-registers] project. This work is done for
interoperability purposes.

Use this software at your own risk. This library is provided without any
warranty or support by BLUETTI, and the authors are not responsible for any
problems it may cause.

## License

MIT License

Copyright (c) 2026 Patrick762

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

[bluetti-community]: https://github.com/bluetti-community
[bluetti-home-assistant]: https://github.com/bluetti-community/bluetti-home-assistant
[bluetti-registers-naming]: https://github.com/bluetti-community/bluetti-registers#naming-convention-for-field-names
[ev-ac200l]: https://github.com/bluetti-community/bluetti-modbus/issues/76
[ev-ac500]: https://github.com/bluetti-community/bluetti-registers/issues/13
[ev-ep500p]: https://github.com/bluetti-community/bluetti-registers/issues/35
[ev-fp]: https://github.com/bluetti-community/bluetti-registers/issues/38
[bluetti-registers]: https://github.com/bluetti-community/bluetti-registers
[build-shield]: https://github.com/bluetti-community/bluetti-modbus/actions/workflows/tests.yml/badge.svg
[build]: https://github.com/bluetti-community/bluetti-modbus/actions/workflows/tests.yml
[contributors]: https://github.com/bluetti-community/bluetti-modbus/graphs/contributors
[devcontainer-shield]: https://img.shields.io/static/v1?label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode
[devcontainer]: https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/bluetti-community/bluetti-modbus
[github-sponsors-shield]: https://img.shields.io/badge/sponsor-Patrick762-db61a2.svg?logo=githubsponsors
[github-sponsors]: https://github.com/sponsors/Patrick762
[ha-core-pr]: https://github.com/home-assistant/core/pull/180602
[hassio-bluetti-modbus]: https://github.com/bluetti-community/hassio-bluetti-modbus
[license-shield]: https://img.shields.io/github/license/bluetti-community/bluetti-modbus.svg
[modbus-connection]: https://pypi.org/project/modbus-connection/
[official-docs]: https://github.com/bluetti-official/bluetti-modbus-tcp-slave
[patrick-original]: https://github.com/Patrick762/bluetti-modbus-lib
[patrick762]: https://github.com/Patrick762
[pre-commit]: https://pre-commit.com
[probatio]: https://pypi.org/project/probatio/
[pymodbus]: https://pypi.org/project/pymodbus/
[pypi-shield]: https://img.shields.io/pypi/v/bluetti-modbus.svg
[pypi]: https://pypi.org/project/bluetti-modbus/
[python-versions-shield]: https://img.shields.io/pypi/pyversions/bluetti-modbus.svg
[releases]: https://github.com/bluetti-community/bluetti-modbus/releases
[sync-devices]: .github/workflows/sync-devices.yml
[tmodbus]: https://pypi.org/project/tmodbus/
[trusted-publishing]: https://docs.pypi.org/trusted-publishers/
