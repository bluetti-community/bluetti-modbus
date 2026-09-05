"""Unofficial async client for Bluetti power stations over Modbus."""

from .devices import (
    AGGREGATE_SLAVE_ID,
    AGGREGATE_SUMMARY_FIELDS,
    EP2000,
    MAX_BATTERY_PACKS,
    PACK_INFO_FIELDS,
    Balco260,
    SMeter,
    aggregate_pack_summary,
    battery_pack,
    get_device,
)
from .enums import InverterFault, InverterStatus, InverterWarning, PackChargingStatus
from .exceptions import BluettiModbusConnectionError, BluettiModbusError
from .modbus import BluettiModbusClient

__all__ = [
    "AGGREGATE_SLAVE_ID",
    "AGGREGATE_SUMMARY_FIELDS",
    "EP2000",
    "MAX_BATTERY_PACKS",
    "PACK_INFO_FIELDS",
    "Balco260",
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
]
