from enum import Enum, unique


@unique
class PvType(Enum):
    Reserve = 0
    Car = 1
    Adapter = 2
    Other = 3
