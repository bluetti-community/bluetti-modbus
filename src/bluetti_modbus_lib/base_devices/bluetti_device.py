import asyncio
from collections.abc import KeysView
from typing import Any

from modbus_connection.exceptions import AcknowledgeError, ServerDeviceBusyError
from modbus_connection.model import Component, RegisterField


class BluettiDevice(Component):
    max_gap = 5
    max_span = 50

    def field_names(self) -> KeysView[str]:
        return self._register_fields.keys()

    def get_field(self, field_name: str) -> RegisterField[Any] | None:
        return self._register_fields.get(field_name)

    def get_sensors(self) -> KeysView[str]:
        return self.field_names()

    @property
    def values(self) -> dict[str, Any]:
        """A copy of all field values decoded on the last update."""
        return dict(self._values)

    async def async_update_with_retry(self) -> None:
        """Refresh this device's values, retrying once on a transient busy response.

        Codes 5/6 (acknowledge / server device busy) mean the device accepted
        the request but wants more time - seen in practice on registers that
        otherwise read fine, so it's transient device behavior, not a
        permanently bad address. Callers that want a hard failure to surface
        immediately should call ``async_update()`` directly instead.
        """
        try:
            await self._async_update_with_timeout()
        except (AcknowledgeError, ServerDeviceBusyError):
            await self._async_update_with_timeout()

    async def _async_update_with_timeout(self) -> None:
        # One async_update() call reads several register blocks sequentially
        # (see modbus_connection's ReadPlan.execute), each already bounded by
        # the connection's own per-request timeout. This timeout budgets the
        # whole sequence, not one request - it must be large enough to cover
        # every block being slow, not just one, or a single sluggish block
        # (this device's Modbus TCP stack is known to become unresponsive
        # under load) starves the ones after it: the connection gets
        # cancelled mid-read, which modbus_connection reports as "Request
        # cancelled outside library" for whatever block was in flight at that
        # moment - a confusing symptom that looks like a register-specific
        # fault but is really this budget being too tight.
        async with asyncio.timeout(30):
            await self.async_update()
