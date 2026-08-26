import logging
from dataclasses import dataclass
from typing import Any

import async_timeout
from modbus_connection import ModbusTcpParams
from modbus_connection.pymodbus import ModbusConnection

from ..devices import EP2000, Balco260, SMeter, get_device
from ..fields.field_extras import DeviceClass, FieldCategory, FieldStateClass

LOGGER = logging.getLogger(__name__)


@dataclass
class ClientReturnValue:
    name: str
    unit: str | None
    value: Any
    category: FieldCategory | None
    state_class: FieldStateClass | None
    device_class: DeviceClass | None

    def __str__(self) -> str:
        return f"{self.name}: {self.value} {self.unit or " "} (category: {self.category or "n/a"}) (state_class: {self.state_class or "n/a"}) (device_class: {self.device_class or "n/a"})"


class BluettiModbusClient:
    def __init__(self, host: str, port: int, device_type: str) -> None:
        self.conn = ModbusConnection(ModbusTcpParams(host=host, port=port), timeout=10)
        device = get_device(device_type, self.conn.for_unit(1))
        if device is None:
            raise ValueError(f"Unsupported device type: {device_type!r}")
        self.device: Balco260 | EP2000 | SMeter = device

    async def read(self) -> list[ClientReturnValue]:
        try:
            await self.conn.connect()

            async with async_timeout.timeout(10):
                LOGGER.debug("Reading device data")

                await self.device.async_update()
        finally:
            await self.conn.close()

        results = []
        for name, value in self.device._values.items():
            field = self.device.get_field(name)
            assert field is not None, f"{name} is in _values, so it must be a registered field"
            results.append(
                ClientReturnValue(
                    name=name,
                    unit=field.unit,
                    value=value,
                    category=getattr(field, "category", None),
                    state_class=getattr(field, "state_class", None),
                    device_class=getattr(field, "device_class", None),
                )
            )
        return results
