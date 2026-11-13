from enum import IntEnum, unique


# The Balco series' working mode: the three modes the BLUETTI app offers a
# Balco, numbered as WorkingMode. IntEnum for the write.
@unique
class BalcoWorkingMode(IntEnum):
    Custom = 1
    SelfConsumption = 2
    Backup = 4
