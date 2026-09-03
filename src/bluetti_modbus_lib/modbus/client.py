import logging
from dataclasses import dataclass
from typing import Any, Literal

from modbus_connection import ModbusConnection as _BaseModbusConnection
from modbus_connection import ModbusTcpParams

from ..devices import EP2000, Balco260, SMeter, get_device

LOGGER = logging.getLogger(__name__)

Backend = Literal["pymodbus", "tmodbus"]


@dataclass
class ClientReturnValue:
    name: str
    unit: str | None
    value: Any

    def __str__(self) -> str:
        return f"{self.name}: {self.value} {self.unit or ' '}"


class BluettiModbusClient:
    def __init__(
        self, host: str, port: int, device_type: str, *, backend: Backend = "tmodbus"
    ) -> None:
        # tmodbus is the default since 0.4.0 - confirmed via persistent-
        # connection testing against real Balco260/S Meter hardware: it
        # correctly reports a corrupted/truncated reply as ModbusProtocolError,
        # where pymodbus reports the identical event as a generic timeout
        # (see #29 and CONTRIBUTING.md). backend="pymodbus" stays available
        # (pip install "bluetti-modbus[cli-pymodbus]") for anyone who needs
        # the previous default.
        #
        # Import chosen here, not at module level: each backend is an
        # optional extra (see pyproject.toml's cli/cli-pymodbus) - importing
        # both eagerly would require every caller to install both.
        #
        # Typed against modbus_connection's own backend-neutral base (its
        # public re-export of BaseModbusConnection) - the two branches below
        # each import an unrelated concrete class, even though the doc's own
        # contract is that both back this same base and are interchangeable
        # at the call sites below. Building the instance inside each branch,
        # rather than importing under one shared name first, is what lets
        # mypy see each concrete class as assignment-compatible with that
        # declared base instead of flagging the import itself.
        params = ModbusTcpParams(host=host, port=port)
        self.conn: _BaseModbusConnection
        if backend == "tmodbus":
            from modbus_connection.tmodbus import ModbusConnection as _TConn

            self.conn = _TConn(params, timeout=10)
        else:
            from modbus_connection.pymodbus import ModbusConnection as _PConn

            self.conn = _PConn(params, timeout=10)
        device = get_device(device_type, self.conn.for_unit(1))
        if device is None:
            raise ValueError(f"Unsupported device type: {device_type!r}")
        self.device: Balco260 | EP2000 | SMeter = device

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
