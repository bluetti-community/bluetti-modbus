from typing import cast

from modbus_connection import ModbusUnit

from .ac200l import AC200L
from .ac500 import AC500
from .balco260 import Balco260
from .balco500 import Balco500
from .ep500p import EP500P
from .ep2000 import EP2000
from .fp import FP
from .smeter import SMeter


def get_device(
    d: str, unit: ModbusUnit | None = None
) -> AC200L | AC500 | FP | Balco260 | Balco500 | EP2000 | EP500P | SMeter | None:
    # unit=None is a real, supported call (e.g. sensor.py inspects a
    # device's fields without a live connection) - Component.__init__ only
    # stores the reference, it doesn't dereference it, so this is safe even
    # though ModbusUnit itself isn't declared Optional there.
    unit = cast(ModbusUnit, unit)
    if d == "ac200l":
        return AC200L(unit)
    if d == "ac500":
        return AC500(unit)
    if d == "balco260":
        return Balco260(unit)
    if d == "balco500":
        return Balco500(unit)
    if d == "ep2000":
        return EP2000(unit)
    if d == "ep500p":
        return EP500P(unit)
    if d == "fp":
        return FP(unit)
    if d == "smeter":
        return SMeter(unit)
    else:
        return None
