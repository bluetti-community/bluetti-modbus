import logging
from dataclasses import dataclass
from typing import Any

from modbus_connection import ModbusTcpParams
from modbus_connection.pymodbus import ModbusConnection

from ..devices import Balco260, SMeter, get_device

LOGGER = logging.getLogger(__name__)


@dataclass
class ClientReturnValue:
    name: str
    unit: str | None
    value: Any

    def __str__(self) -> str:
        return f"{self.name}: {self.value} {self.unit or ' '}"


class BluettiModbusClient:
    def __init__(self, host: str, port: int, device_type: str) -> None:
        self.conn = ModbusConnection(ModbusTcpParams(host=host, port=port), timeout=10)
        device = get_device(device_type, self.conn.for_unit(1))
        if device is None:
            raise ValueError(f"Unsupported device type: {device_type!r}")
        self.device: Balco260 | SMeter = device

    async def aclose(self) -> None:
        """Close the connection permanently. Call when actually done with this client."""
        await self.conn.close()

    async def read(self) -> list[ClientReturnValue]:
        # Connection is intentionally left open between calls - modbus_connection
        # keeps it usable across reads, reconnecting on demand if it drops. A
        # fresh connection on every read is exactly the pattern that has caused
        # this device's Modbus TCP stack to become unresponsive under load in
        # the past. Call aclose() when actually done with this client.
        await self.conn.connect()

        LOGGER.debug("Reading device data")
        await self.device.async_update_with_retry()

        results = []
        for name, value in self.device.values.items():
            field = self.device.get_field(name)
            assert field is not None, (
                f"{name} is in values, so it must be a registered field"
            )
            results.append(ClientReturnValue(name=name, unit=field.unit, value=value))
        return results
