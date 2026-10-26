"""The inverter faults, registers 50027-50031, read as one value, low word first.

Each set bit is one BLUETTI E code, from BLUETTI's Modbus Open Protocol
Fault and Alarm Table (bluetti-official/bluetti-modbus-tcp-slave,
doc/Bluetti-Modbus-Open-Protocol-Fault-and-Alarm-Table.xlsx): bit b of
register 50027 + n is bit 16 * n + b here. Bits the table marks reserved
have no member.
"""

from enum import IntFlag, unique


@unique
class InverterFault(IntFlag):
    NoFault = 0
    E001 = 1 << 0  # 50027 bit 0
    E002 = 1 << 1  # 50027 bit 1
    E003 = 1 << 2  # 50027 bit 2
    E004 = 1 << 3  # 50027 bit 3
    E005 = 1 << 4  # 50027 bit 4
    E006 = 1 << 5  # 50027 bit 5
    E007 = 1 << 6  # 50027 bit 6
    E008 = 1 << 7  # 50027 bit 7
    E009 = 1 << 8  # 50027 bit 8
    E010 = 1 << 9  # 50027 bit 9
    E011 = 1 << 10  # 50027 bit 10
    E012 = 1 << 11  # 50027 bit 11
    E013 = 1 << 12  # 50027 bit 12
    E014 = 1 << 13  # 50027 bit 13
    E015 = 1 << 14  # 50027 bit 14
    E016 = 1 << 15  # 50027 bit 15
    E017 = 1 << 16  # 50028 bit 0
    E018 = 1 << 17  # 50028 bit 1
    E019 = 1 << 18  # 50028 bit 2
    E020 = 1 << 19  # 50028 bit 3
    E021 = 1 << 20  # 50028 bit 4
    E022 = 1 << 21  # 50028 bit 5
    E023 = 1 << 22  # 50028 bit 6
    E024 = 1 << 23  # 50028 bit 7
    E025 = 1 << 24  # 50028 bit 8
    E026 = 1 << 25  # 50028 bit 9
    E027 = 1 << 26  # 50028 bit 10
    E028 = 1 << 27  # 50028 bit 11
    E033 = 1 << 32  # 50029 bit 0
    E034 = 1 << 33  # 50029 bit 1
    E035 = 1 << 34  # 50029 bit 2
    E036 = 1 << 35  # 50029 bit 3
    E037 = 1 << 36  # 50029 bit 4
    E038 = 1 << 37  # 50029 bit 5
    E039 = 1 << 38  # 50029 bit 6
    E040 = 1 << 39  # 50029 bit 7
    E041 = 1 << 40  # 50029 bit 8
    E042 = 1 << 41  # 50029 bit 9
    E043 = 1 << 42  # 50029 bit 10
    E044 = 1 << 43  # 50029 bit 11
    E065 = 1 << 64  # 50031 bit 0
    E066 = 1 << 65  # 50031 bit 1
    E067 = 1 << 66  # 50031 bit 2
    E068 = 1 << 67  # 50031 bit 3
    E069 = 1 << 68  # 50031 bit 4
    E070 = 1 << 69  # 50031 bit 5
    E071 = 1 << 70  # 50031 bit 6
    E072 = 1 << 71  # 50031 bit 7
    E073 = 1 << 72  # 50031 bit 8
    E074 = 1 << 73  # 50031 bit 9
    E075 = 1 << 74  # 50031 bit 10
    E076 = 1 << 75  # 50031 bit 11
    E077 = 1 << 76  # 50031 bit 12


FAULT_DESCRIPTIONS: dict[str, str] = {
    "E001": "Inverter overload",
    "E002": "Inverter over-temperature",
    "E003": "Inverter short circuit",
    "E004": "Inverter output fault (inverter soft start)",
    "E005": "LLC output fault (HV/LV side soft start)",
    "E006": "BUS overvoltage / hardware BUS overvoltage",
    "E007": "BUS undervoltage",
    "E008": "Hardware inverter overcurrent",
    "E009": "Hardware input overcurrent",
    "E010": "Battery voltage too high / hardware battery overvoltage",
    "E011": "Battery voltage too low (inverter input side)",
    "E012": "Main relay failure",
    "E013": "Grid relay failure",
    "E014": "Zero drift abnormality",
    "E015": "Auxiliary power supply fault",
    "E016": "Fan fault",
    "E017": "Multiple master error",
    "E018": "Phase loss",
    "E019": "Multi-unit communication abnormality (including duplicate parallel address)",
    "E020": "Multi-unit synchronization abnormality",
    "E021": "Multi-unit configuration abnormality",
    "E022": "Generator voltage abnormality",
    "E023": "System initialization abnormality",
    "E024": "Parallel relay fault",
    "E025": "Grid input overcurrent",
    "E026": "Whole unit overload",
    "E027": "DC output overload (total DC output power)",
    "E028": "Inverter under-temperature",
    "E033": "PV1 overvoltage",
    "E034": "PV2 overvoltage",
    "E035": "PV3 overvoltage",
    "E036": "PV1 overcurrent",
    "E037": "PV2 overcurrent",
    "E038": "PV3 overcurrent",
    "E039": "PV1 over-temperature",
    "E040": "PV2 over-temperature",
    "E041": "PV3 over-temperature",
    "E042": "PV pre-charge fault",
    "E043": "PV1 hardware fault",
    "E044": "PV2 hardware fault",
    "E065": "DC output short circuit",
    "E066": "DC output overvoltage",
    "E067": "DC output overcurrent",
    "E068": "DC output over-temperature",
    "E069": "DC output fault",
    "E070": "Battery pack communication fault",
    "E071": "Inverter group communication fault",
    "E072": "RTC error",
    "E073": "EEPROM error",
    "E074": "BMS system fault (see Pack for specific faults)",
    "E075": "Controller temperature too high",
    "E076": "Zero drift abnormality (DSP)",
    "E077": "DC output under-temperature",
}
