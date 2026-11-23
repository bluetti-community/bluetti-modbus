from enum import Enum, unique


# The working mode of the stations whose BLUETTI app names it a UPS mode
# (the FridgePower). Read-only over Modbus TCP there, so a plain Enum.
@unique
class UpsWorkingMode(Enum):
    CustomizedUps = 1
    PvPriorityUps = 2
    StandardUps = 4
    TimeControlUps = 5
