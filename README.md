# bluetti-modbus-lib
Unofficial library for basic communication to Bluetti Power Stations via Modbus.

Based on official documentation https://github.com/bluetti-official/bluetti-modbus-tcp-slave

You have to enable Modbus TCP in the webinterface of your device first.

## Disclaimer
This library is provided without any warranty or support by Bluetti. I do not take responsibility for any problems it may cause in all cases. Use it at your own risk.

## Supported devices and data

- Balco260
- EP2000

Field names, units, and Modbus registers come from
[bluetti-registers](https://github.com/bluetti-community/bluetti-registers) -
`devices/balco260.py` and `devices/ep2000.py` in this repo are generated
from it by `import.py`, not written by hand.

## Installation

```bash
pip install bluetti-modbus-lib
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
d_num_inverters: 1   (category: FieldCategory.DIAGNOSTIC) (state_class: n/a) (device_class: n/a)
ac_o_p_total: 84 W (category: n/a) (state_class: FieldStateClass.MEASUREMENT) (device_class: DeviceClass.POWER)
pv_i_p_total: 0 W (category: n/a) (state_class: FieldStateClass.MEASUREMENT) (device_class: DeviceClass.POWER)
ac_o_e_total: 64.7 kWh (category: FieldCategory.DIAGNOSTIC) (state_class: FieldStateClass.TOTAL_INCREASING) (device_class: DeviceClass.ENERGY)
d_inverter_status: InverterStatus.GridConnectedOperation   (category: FieldCategory.DIAGNOSTIC) (state_class: n/a) (device_class: n/a)
g_i_f: 50.0 Hz (category: n/a) (state_class: FieldStateClass.MEASUREMENT) (device_class: DeviceClass.FREQUENCY)
b_v: 27.1 V (category: n/a) (state_class: FieldStateClass.MEASUREMENT) (device_class: DeviceClass.VOLTAGE)
b_soc: 100 % (category: n/a) (state_class: FieldStateClass.MEASUREMENT) (device_class: DeviceClass.BATTERY)
b_cycle_count: 8   (category: FieldCategory.DIAGNOSTIC) (state_class: FieldStateClass.MEASUREMENT) (device_class: n/a)
b_t_avg: 0 °C (category: n/a) (state_class: FieldStateClass.MEASUREMENT) (device_class: DeviceClass.TEMPERATURE)
b_i_e: 23420 Wh (category: FieldCategory.DIAGNOSTIC) (state_class: FieldStateClass.TOTAL_INCREASING) (device_class: DeviceClass.ENERGY)
```

Note the two energy fields above: most cumulative energy fields (`ac_o_e_total`, etc.) are reported in kWh, but the battery charge/discharge ones (`b_i_e`, `b_o_e`) are in Wh - both correct as reported by the device, just worth knowing if you're comparing values across fields.

Field names follow the naming convention documented in
[bluetti-registers](https://github.com/bluetti-community/bluetti-registers#naming-convention-for-field-names).
