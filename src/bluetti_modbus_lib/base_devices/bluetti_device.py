import asyncio
from collections.abc import KeysView
from typing import Any, override

from modbus_connection.exceptions import (
    AcknowledgeError,
    ModbusError,
    ModbusProtocolError,
    ModbusTimeoutError,
    ServerDeviceBusyError,
)
from modbus_connection.model import Component, RegisterField

from ..exceptions import BluettiModbusConnectionError, BluettiModbusError

# How many times a transient corrupted/truncated-reply error gets retried
# before giving up - see async_update_with_retry's own docstring. Bumped
# from 1 to 2 after real HA logs (bluetti-community/bluetti-modbus#29)
# showed the single retry already in place wasn't always enough: 22
# occurrences over ~4h on one live Balco260 got through it and surfaced as
# coordinator errors, meaning both the original attempt and that one retry
# failed back to back. Confirmed backend-independent (both tmodbus and
# pymodbus observe the same truncated-frame pattern, just classify it
# differently), so this isn't a client-library quirk to fix elsewhere.
# Not proven sufficient either - a starting point pending extended
# real-hardware monitoring, same as Balco260's max_span override.
_TRANSIENT_RETRY_COUNT = 2


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

    @override
    async def async_update(self, *, notify: bool = True) -> None:
        """Refresh this device's values once, raising immediately on any failure.

        Wraps modbus_connection's own errors into BluettiModbusConnectionError
        (still also a ModbusError - see its own docstring), except for a
        transient busy response - see async_update_with_retry, which is what
        most callers want instead of calling this directly.
        """
        try:
            await super().async_update(notify=notify)
        except (AcknowledgeError, ServerDeviceBusyError):
            raise
        except ModbusError as err:
            raise BluettiModbusConnectionError(str(err)) from err

    async def async_update_with_retry(self) -> None:
        """Refresh this device's values, retrying on a transient failure.

        Two things are retried here, both confirmed transient on real
        hardware rather than assumed:

        - Codes 5/6 (acknowledge / server device busy) mean the device
          accepted the request but wants more time - seen in practice on
          registers that otherwise read fine, so it's transient device
          behavior, not a permanently bad address. Retried once.
        - A corrupted/truncated reply - ModbusProtocolError under tmodbus
          (bluetti-community/bluetti-modbus#29), or the same event
          classified as ModbusTimeoutError under pymodbus, which can't tell
          a corrupted reply apart from no reply at all. Persistent-connection
          testing against real Balco260/S Meter hardware (both backends)
          showed this recovers cleanly on a following read on the same
          connection in the large majority of cases, with no reconnect
          needed - so an immediate retry here avoids losing the whole poll
          cycle to what is, in practice, usually a one-off glitch. Retried
          up to ``_TRANSIENT_RETRY_COUNT`` times (see its own docstring for
          why this isn't just one any more) - a genuinely dead connection
          still fails, just later, at up to ``_TRANSIENT_RETRY_COUNT + 1``x
          the timeout budget.

        Anything else (e.g. an illegal address/function code) is a permanent
        condition retrying can't fix, and is not retried here - callers that
        want a hard failure to surface immediately for any reason should call
        ``async_update()`` directly instead.

        A device that is still busy after this one retry raises the bare
        AcknowledgeError/ServerDeviceBusyError, not wrapped into
        BluettiModbusConnectionError like every other failure here - "busy
        twice in a row" is a real, distinct signal from "the connection is
        broken" that a caller may want to tell apart.
        """
        try:
            await self._async_update_with_timeout()
            return
        except (AcknowledgeError, ServerDeviceBusyError):
            await self._async_update_with_timeout()
            return
        except BluettiModbusConnectionError as err:
            if not isinstance(err.__cause__, (ModbusProtocolError, ModbusTimeoutError)):
                raise

        for attempt in range(_TRANSIENT_RETRY_COUNT):
            try:
                await self._async_update_with_timeout()
                return
            except BluettiModbusConnectionError as err:
                if not isinstance(
                    err.__cause__, (ModbusProtocolError, ModbusTimeoutError)
                ):
                    raise
                if attempt == _TRANSIENT_RETRY_COUNT - 1:
                    raise

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
        #
        # Calls self.async_update() (the wrapping override above), not
        # Component's directly - so a test that replaces this instance's
        # async_update with its own mock is still exercised the same way a
        # real device's own async_update override would be. Two things this
        # still needs to guard against catching its own errors don't fit that
        # path: the timeout budget expiring here (not inside async_update, so
        # its own wrapping never sees it) and double-wrapping an error the
        # override already wrapped.
        try:
            async with asyncio.timeout(30):
                await self.async_update()
        except (AcknowledgeError, ServerDeviceBusyError):
            raise
        except BluettiModbusError:
            raise
        except (ModbusError, TimeoutError) as err:
            raise BluettiModbusConnectionError(str(err)) from err
