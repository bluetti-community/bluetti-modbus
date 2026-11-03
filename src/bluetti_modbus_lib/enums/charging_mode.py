from enum import IntEnum, unique


# IntEnum, not Enum: the field is writable, and modbus_connection encodes a
# write with int(value).
@unique
class ChargingMode(IntEnum):
    Standard = 0
    Silent = 1
    Turbo = 2
