# Python: Unofficial async client for Bluetti power stations over Modbus

[![PyPI Version][pypi-shield]][pypi]
[![Python Versions][python-versions-shield]][pypi]
[![License][license-shield]](LICENSE)
[![Build Status][build-shield]][build]
[![Open in Dev Containers][devcontainer-shield]][devcontainer]

Asynchronous Python client for Bluetti power stations over their local Modbus
TCP interface.

## About

This package reads Bluetti power stations over Modbus, using the register
maps Bluetti documents for its Modbus TCP slave implementation. It is built
on top of [`modbus-connection`][modbus-connection], a backend-neutral async
Modbus toolkit: the library does **not** create or own a connection itself.
The caller opens a `ModbusConnection` and hands over a `ModbusUnit`; a site
with several devices creates one device object per unit, all sharing a
single connection.

Because the caller owns the connection, the transport is up to you - Modbus
TCP over Ethernet or WiFi is the common path, but anything that hands this
library a `ModbusUnit` will do. This is the integration surface used to embed
the library into another application, such as the `bluetti_modbus` Home
Assistant integration (currently in review at
[home-assistant/core#180602][ha-core-pr]).

This library is primarily **read-only** - it decodes what a device reports.
A small, explicit set of fields `bluetti-registers`' schema marks writeable
(currently: Balco260's 3 control switches and 2 battery SOC thresholds - not
yet EP2000, which is still spec-derived rather than field-tested) also
support `await device.write(field_name, value)`, validated against the
schema's own bounds (via [`probatio`][probatio]) before anything reaches the
device. Everything else stays read-only.

Supported out of the box:

- **Balco260**: battery voltage/current/SoC/SoH/cycle count, per-string PV,
  grid import/export, AC output, inverter status/fault/warning, and more
- **EP2000**: the same Balco260 register set plus a rated-capacity and
  EMS/grid-export control block Balco260 doesn't have - sourced from
  BLUETTI's own official register spec, not yet verified against real
  EP2000 hardware (see [bluetti-registers][bluetti-registers] for the
  provenance of every field)
- **S Meter**: Bluetti's AC meter/CT accessory (register map decoded, but
  not yet verified against real hardware)

EP2000 support was pulled for a while pending confirmation that it exposes
Modbus TCP at all (see
[bluetti-official/bluetti-home-assistant#125](https://github.com/bluetti-official/bluetti-home-assistant/issues/125))
and re-added once BLUETTI published an official register spec confirming it
does - the original report's closed port 502 on one specific unit is still
unexplained, so treat this device as spec-derived rather than field-tested.

Field names, units, and register addresses come from
[bluetti-registers][bluetti-registers], not from hand-written tables in this
repository - `devices/balco260.py` is generated from it by `import.py`, and a
[scheduled workflow][sync-devices] re-runs that
generator weekly and commits any diff, so `main` never silently drifts from
what `bluetti-registers` currently documents.

## Enabling Modbus TCP on your device

Modbus TCP is off by default on Bluetti power stations that support it -
enable it in the device's own web interface first, then point this library
at its IP address. See the official
[bluetti-modbus-tcp-slave][official-docs] documentation for the exact steps
for your model; they vary enough between devices that this README won't
guess at them.

## Installation

```bash
pip install bluetti-modbus
```

Installing `bluetti-modbus` alone only pulls in `modbus-connection`'s
backend-neutral interface - enough to use the device classes directly against
a `ModbusUnit` you already have. The `bluetti-modread` CLI, and the examples
below, need a concrete backend, installed via the `cli` extra (currently
[tmodbus][tmodbus], the default since 0.4.0 - see
[CONTRIBUTING.md](CONTRIBUTING.md) for why):

```bash
pip install "bluetti-modbus[cli]"
```

`bluetti-modread` also accepts `--backend pymodbus` (`pip install
"bluetti-modbus[cli-pymodbus]"` first) - the previous default, still
available for anyone who needs it.

## Usage

The consumer owns the connection and hands the library a unit:

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

There is no self-describing header to detect the model from, unlike some
Modbus devices - `get_device()` takes the model as a plain string
(`"balco260"`, `"ep2000"`, or `"smeter"`); the caller has to already know
which one it's talking to. `async_update_with_retry()` is the entry point
most callers want: it retries once on a transient acknowledge/busy response
(codes 5/6), which Bluetti devices return in practice on registers that
otherwise read fine. Call `async_update()` directly instead if you want that
first failure to raise immediately. Either way, a communication failure
raises `BluettiModbusConnectionError` (also a `modbus_connection.ModbusError`,
for code that already catches that directly) - except for a transient busy
response, which `async_update_with_retry` decides whether to retry rather
than wrapping. Decoded values land on `device.values`, a plain
`dict[str, Any]` keyed by field name; `field_names()` and `get_field()`
expose the field metadata (address, type, scale, unit, whether it's
writable) behind each key, deliberately limited to what's true at the
protocol level - no Home Assistant concepts like entity category or device
class live here, since those describe UI presentation, not the register.

Everything above (`get_device`, the device classes, `BluettiModbusError`,
`BluettiModbusConnectionError`, `BluettiModbusClient`, the inverter enums) is
importable directly from `bluetti_modbus_lib`, not from the deeper module
paths that define them.

## CLI

The optional CLI reads a device straight from the terminal - useful for
testing, not something another application should build on (see
[Architecture](#architecture) below).

```bash
bluetti-modread -c 10.2.1.60 -p 502 -t balco260
```

Example output, captured from a real Balco260 (truncated - `bluetti-modread`
prints one line per field):

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
b_t_avg: 0 °C
b_i_e: 23420 Wh
```

Note the two energy fields above: most cumulative energy fields
(`ac_o_e_total`, etc.) are reported in kWh, but the battery charge/discharge
ones (`b_i_e`, `b_o_e`) are in Wh - both correct as reported by the device,
just worth knowing if you're comparing values across fields. Field names
follow the naming convention documented in
[bluetti-registers][bluetti-registers-naming].

## Architecture

Two different things in this library talk Modbus, for two different
audiences:

- `Balco260`, `EP2000`, and `SMeter` (`bluetti_modbus_lib.devices`) are the
  integration surface: each takes a `ModbusUnit` supplied by the caller,
  built from whichever backend and connection the caller already manages.
  This is what an application - a Home Assistant integration, for example -
  should build on.
- `BluettiModbusClient` (`bluetti_modbus_lib.modbus.client`) is different: it
  owns and manages its own connection. It exists for the `bluetti-modread`
  CLI above and standalone/manual use, not as something another application
  should depend on - doing so would open a second, competing connection to
  the device instead of sharing one.

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
affiliated with, endorsed by, or supported by** Bluetti (PowerOak). All
product names, trademarks, and registered trademarks are property of their
respective owners.

The register map is based on Bluetti's own published
[bluetti-modbus-tcp-slave][official-docs] documentation and the
[bluetti-registers][bluetti-registers] project. This work is done for
interoperability purposes.

Use this software at your own risk. This library is provided without any
warranty or support by Bluetti, and the authors are not responsible for any
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
[bluetti-registers-naming]: https://github.com/bluetti-community/bluetti-registers#naming-convention-for-field-names
[bluetti-registers]: https://github.com/bluetti-community/bluetti-registers
[build-shield]: https://github.com/bluetti-community/bluetti-modbus/actions/workflows/tests.yml/badge.svg
[build]: https://github.com/bluetti-community/bluetti-modbus/actions/workflows/tests.yml
[contributors]: https://github.com/bluetti-community/bluetti-modbus/graphs/contributors
[devcontainer-shield]: https://img.shields.io/static/v1?label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode
[devcontainer]: https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/bluetti-community/bluetti-modbus
[github-sponsors-shield]: https://img.shields.io/badge/sponsor-Patrick762-db61a2.svg?logo=githubsponsors
[github-sponsors]: https://github.com/sponsors/Patrick762
[ha-core-pr]: https://github.com/home-assistant/core/pull/180602
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
