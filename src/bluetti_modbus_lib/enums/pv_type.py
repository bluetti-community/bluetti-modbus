from enum import Enum, unique


@unique
class PvType(Enum):
    Reserve = 0
    Car = 1
    Adapter = 2
    Other = 3
    # "Only available on some models" per the official register spec's
    # remark column - not sequential with the 4 above, but every real
    # Balco260 reports this value (confirmed against real hardware). A
    # previous attempt at this enum only covered 0-3 and silently failed to
    # decode every real read as a result (bluetti-registers@8f5dadd).
    DcPv = 100
    AcPv = 101
