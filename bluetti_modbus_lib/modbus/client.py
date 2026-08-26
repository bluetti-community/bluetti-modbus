import logging
from dataclasses import dataclass
from typing import Any

import async_timeout
from modbus_connection.pymodbus import ModbusConnection, ModbusTcpParams

from ..devices import get_device

LOGGER = logging.getLogger(__name__)


@dataclass
class ClientReturnValue:
    name: str
    unit: str
    value: Any
    category: str
    state_class: str
    device_class: str

    def __str__(self):
        return f"{self.name}: {self.value} {self.unit or " "} (category: {self.category or "n/a"}) (state_class: {self.state_class or "n/a"}) (device_class: {self.device_class or "n/a"})"


class BluettiModbusClient:
    def __init__(self, host: str, port: int, device_type: str):
        self.conn = ModbusConnection(ModbusTcpParams(host=host, port=port), timeout=10)
        self.device = get_device(device_type, self.conn.for_unit(1))

    async def read(self):
        try:
            await self.conn.connect()

            async with async_timeout.timeout(10):
                LOGGER.debug("Reading device data")

                await self.device.async_update()

        except TimeoutError:
            LOGGER.error("Timeout")
        finally:
            await self.conn.close()

        return [
            ClientReturnValue(
                name=n,
                unit=self.device.get_field(n).unit,
                value=v,
                category=getattr(self.device.get_field(n), "category", None),
                state_class=getattr(self.device.get_field(n), "state_class", None),
                device_class=getattr(self.device.get_field(n), "device_class", None),
            )
            for (n, v) in self.device._values.items()
        ]
