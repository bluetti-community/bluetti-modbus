from enum import Enum, unique


# The Apex 300's working mode, as the BLUETTI app names it. Read-only over
# Modbus TCP, so a plain Enum.
@unique
class WorkingMode(Enum):
    Custom = 1
    SelfConsumption = 2
    Backup = 4
    TimeOfUse = 5
