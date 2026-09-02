from enum import Enum, unique


@unique
class PackChargingStatus(Enum):
    Idle = 0
    Charging = 1
    Discharging = 2
