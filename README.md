# bluetti-modbus-lib
Unofficial library for basic communication to Bluetti Power Stations via Modbus.

Based on official documentation https://github.com/bluetti-official/bluetti-modbus-tcp-slave

You have to enable Modbus TCP in the webinterface of your device first.

## Disclaimer
This library is provided without any warranty or support by Bluetti. I do not take responsibility for any problems it may cause in all cases. Use it at your own risk.

## Supported devices and data

- Balco260
- EP2000
- SMeter (Bluetti's AC meter/CT device - untested against real hardware so far)

Field names, units, and Modbus registers come from
[bluetti-registers](https://github.com/bluetti-community/bluetti-registers) -
`devices/balco260.py`, `devices/ep2000.py`, and `devices/smeter.py` in this
repo are generated from it by `import.py`, not written by hand.

## Architecture

This library does not create or own a Modbus transport itself. It's built on
[modbus-connection](https://pypi.org/project/modbus-connection/)'s
device-modelling framework: `Balco260`, `EP2000`, and `SMeter`
(`bluetti_modbus_lib.devices`) each take a `ModbusUnit` supplied by the
caller, built from whichever backend and connection the caller already
manages. That's the integration surface for embedding this library into
another application (a Home Assistant integration, for example).

`BluettiModbusClient` (`bluetti_modbus_lib.modbus.client`) is different: it
owns and manages its own connection. It exists for the `bluetti-modread` CLI
below and standalone/manual use, not as something another application should
build on - doing so would open a second, competing connection to the device
instead of sharing one.

Field metadata is deliberately limited to what's true at the Modbus/protocol
level - address, type, scale, unit, whether it's writable. It does not carry
Home Assistant concepts like entity category, state class, or device class:
those describe how a value should be presented in an HA UI, not anything
about the register itself, and belong in whichever integration consumes this
library, not in the library.

## Installation

```bash
pip install bluetti-modbus-lib
```

Installing `bluetti-modbus-lib` alone only pulls in `modbus-connection`'s
backend-neutral interface - enough to use the device classes directly against
a `ModbusUnit` you already have. The `bluetti-modread` CLI needs a concrete
backend, installed via the `cli` extra:

```bash
pip install "bluetti-modbus-lib[cli]"
```

## Sponsoring

If you want to support this project, you can sponsor [Patrick762 on GitHub](https://github.com/sponsors/Patrick762), the original author.

## Commands for testing

Commands included in this library should only be used for testing.

### Read device data for supported devices

```bash
usage: bluetti-modread [-h] [-c HOST] [-p PORT] [-t TYPE]

Read bluetti devices via modbus

options:
  -h, --help            show this help message and exit
  -c HOST, --host HOST  IP-address of the device
  -p PORT, --port PORT  Port of the device
  -t TYPE, --type TYPE  Device type
```

Example:

```bash
bluetti-modread -c 10.2.1.60 -p 502 -t balco260
```

Example output, captured from a real Balco260 (truncated - `bluetti-modread` prints one line per field):

```bash
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

Note the two energy fields above: most cumulative energy fields (`ac_o_e_total`, etc.) are reported in kWh, but the battery charge/discharge ones (`b_i_e`, `b_o_e`) are in Wh - both correct as reported by the device, just worth knowing if you're comparing values across fields.

Field names follow the naming convention documented in
[bluetti-registers](https://github.com/bluetti-community/bluetti-registers#naming-convention-for-field-names).
