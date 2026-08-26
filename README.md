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
[bluetti-registers](https://github.com/Patrick762/bluetti-registers) -
`devices/balco260.py` and `devices/ep2000.py` in this repo are generated
from it by `import.py`, not written by hand.

## Installation

```bash
pip install bluetti-modbus-lib
```

## Sponsoring and Affiliate links (Anzeige / Ad)

If you want to support this project and buy a Bluetti device, you can use the sponsors button on github:

> [!NOTE]
> DE: Bei diesem Link handelt es sich um einen Affiliate-Link. Wenn du darüber kaufst, erhalte ich eine kleine Provision. Für dich entstehen keine Zusatzkosten.
>
> EN: This is an affiliate link. If you make a purchase through it, I may earn a small commission at no extra cost to you.

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

Example output (illustrative - the actual values depend on your device):

```bash
d_num_inverters: 1   (category: FieldCategory.DIAGNOSTIC) (state_class: n/a) (device_class: n/a)
ac_o_p_total: 350 W (category: n/a) (state_class: FieldStateClass.MEASUREMENT) (device_class: DeviceClass.POWER)
pv_i_p_total: 420 W (category: n/a) (state_class: FieldStateClass.MEASUREMENT) (device_class: DeviceClass.POWER)
g_i_p_total: 0 W (category: n/a) (state_class: FieldStateClass.MEASUREMENT) (device_class: DeviceClass.POWER)
b_soc: 62 % (category: n/a) (state_class: FieldStateClass.MEASUREMENT) (device_class: DeviceClass.BATTERY)
b_soh: 100 % (category: FieldCategory.DIAGNOSTIC) (state_class: FieldStateClass.MEASUREMENT) (device_class: n/a)
```

Field names follow the naming convention documented in
[bluetti-registers](https://github.com/Patrick762/bluetti-registers#naming-convention-for-field-names).
