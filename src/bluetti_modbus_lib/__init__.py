"""Unofficial async client for Bluetti power stations over Modbus."""

from .devices import (
    AC200L,
    AC500,
    AGGREGATE_SLAVE_ID,
    AGGREGATE_SUMMARY_FIELDS,
    EP500P,
    EP2000,
    EXPANSION_PACK_FIRST_SLAVE_ID,
    FP,
    MAX_BATTERY_PACKS,
    PACK_INFO_FIELDS,
    Balco260,
    Balco500,
    SMeter,
    aggregate_pack_summary,
    battery_pack,
    get_device,
    pack_is_reporting,
    pack_slave_id,
)
from .enums import InverterFault, InverterStatus, InverterWarning, PackChargingStatus
from .exceptions import BluettiModbusConnectionError, BluettiModbusError
from .modbus import BluettiModbusClient

__all__ = [
    "AC200L",
    "AC500",
    "AGGREGATE_SLAVE_ID",
    "AGGREGATE_SUMMARY_FIELDS",
    "EP500P",
    "EP2000",
    "EXPANSION_PACK_FIRST_SLAVE_ID",
    "FP",
    "MAX_BATTERY_PACKS",
    "PACK_INFO_FIELDS",
    "Balco260",
    "Balco500",
    "BluettiModbusClient",
    "BluettiModbusConnectionError",
    "BluettiModbusError",
    "InverterFault",
    "InverterStatus",
    "InverterWarning",
    "PackChargingStatus",
    "SMeter",
    "aggregate_pack_summary",
    "battery_pack",
    "get_device",
    "pack_is_reporting",
    "pack_slave_id",
]
