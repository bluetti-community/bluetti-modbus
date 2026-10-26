"""The inverter warnings, registers 50023-50026, read as one value, low word first.

Each set bit is one BLUETTI E code, from BLUETTI's Modbus Open Protocol
Fault and Alarm Table (bluetti-official/bluetti-modbus-tcp-slave,
doc/Bluetti-Modbus-Open-Protocol-Fault-and-Alarm-Table.xlsx): bit b of
register 50023 + n is bit 16 * n + b here. Bits the table marks reserved
have no member.
"""

from enum import IntFlag, unique


@unique
class InverterWarning(IntFlag):
    NoWarning = 0
    E113 = 1 << 0  # 50023 bit 0
    E114 = 1 << 1  # 50023 bit 1
    E115 = 1 << 2  # 50023 bit 2
    E116 = 1 << 3  # 50023 bit 3
    E117 = 1 << 4  # 50023 bit 4
    E118 = 1 << 5  # 50023 bit 5
    E119 = 1 << 6  # 50023 bit 6
    E120 = 1 << 7  # 50023 bit 7
    E121 = 1 << 8  # 50023 bit 8
    E129 = 1 << 16  # 50024 bit 0
    E130 = 1 << 17  # 50024 bit 1


WARNING_DESCRIPTIONS: dict[str, str] = {
    "E113": "Grid voltage too high",
    "E114": "Grid voltage too low",
    "E115": "Grid frequency too high",
    "E116": "Grid frequency too low",
    "E117": "Grid oscillation",
    "E118": "Networking operation abnormality",
    "E119": "Grid port fault (reported when both ports are connected at the same time)",
    "E120": "Accessory operation abnormality (HV/LV HUB connected incorrectly)",
    "E121": "PV configuration error (2061 set incorrectly)",
    "E129": "Battery pack communication abnormality",
    "E130": "IOT communication abnormality",
}
