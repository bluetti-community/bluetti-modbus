from enum import IntEnum, unique


# The Apex 300's AC charging mode: ChargingMode's values plus Custom, which
# the AC200L has not. IntEnum, as ChargingMode, for the write.
@unique
class ApexChargingMode(IntEnum):
    Standard = 0
    Silent = 1
    Turbo = 2
    Custom = 4
