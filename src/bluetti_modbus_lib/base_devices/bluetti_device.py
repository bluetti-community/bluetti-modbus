import asyncio
import logging
import struct
from collections.abc import KeysView
from dataclasses import dataclass
from typing import Any, override

from modbus_connection.exceptions import (
    AcknowledgeError,
    ModbusConnectionError,
    ModbusError,
    ModbusProtocolError,
    ModbusTimeoutError,
    ServerDeviceBusyError,
)
from modbus_connection.model import Component, RegisterField
from probatio.error import Invalid

from ..exceptions import BluettiModbusConnectionError, BluettiModbusError

_LOGGER = logging.getLogger(__name__)

# Modbus function code 0x06, "Write Single Register" - see BluettiDevice.write.
_WRITE_SINGLE_REGISTER_FUNCTION_CODE = 6

# The address a BLUETTI device echoes in a Write Single Register confirmation
# is not the Modbus address that was written to but the same setting's
# address in the device's own internal register space - the one the BLUETTI
# app speaks ("ProtocolAddrV2" in the app's code, tabulated by
# https://github.com/mikemccllstr/voltkeeper/blob/main/docs/source/protocol/modbus-registers.md
# from app v3.0.9). The Modbus TCP slave evidently translates the write to
# an internal one and builds the confirmation from that, so a strict Modbus
# client sees a confirmation that doesn't match its request. That internal
# space differs between product families - a Balco 260 confirms its AC
# output switch at 2011, an AC200L its DC output switch at 3008, nowhere
# near the 2012 the Balco family's map would predict - so the table is
# keyed by device class name, then by the Modbus holding-register address
# written to, and holds only captured echoes: every Balco 260 entry from
# 2026-09-16 (all five of its writable registers), the AC200L one from
# 2026-09-18 (bluetti-modbus#78), the EP500P one from 2026-09-20 (its
# owner's first toggles in Home Assistant, hassio-bluetti-modbus#122) -
# the same 3008 as the AC200L, the portable stations sharing one internal
# map; a FridgePower and a Balco 500 echo the Balco 260's numbers (2012 for
# the DC switch). A device or register with no entry gets its echo accepted and
# reported - see BluettiDevice.write.
_INTERNAL_WRITE_ADDRESS: dict[str, dict[int, int]] = {
    "Balco260": {
        57001: 2011,  # ac_o_switch - AC_SWITCH
        57009: 2207,  # g_i_switch - CTRL_GRID
        57010: 2208,  # g_o_switch - CTRL_FEED
        57016: 2022,  # b_soc_low - SYS_SOC_LOW_CAPACITY
        57017: 2023,  # b_soc_high - SYS_SOC_HIGH_CAPACITY
    },
    "Balco500": {
        57001: 2011,  # ac_o_switch - AC_SWITCH, captured on a real Balco 500
        57009: 2207,  # g_i_switch - CTRL_GRID, captured on a real Balco 500
        57010: 2208,  # g_o_switch - CTRL_FEED, captured on a real Balco 500
        57016: 2022,  # b_soc_low - captured on a real Balco 500, as on the Balco 260
        57017: 2023,  # b_soc_high - captured on a real Balco 500, as on the Balco 260
        57020: 2005,  # d_working_mode - WORKING_MODE, captured on a real Balco 500
    },
    "AC200L": {
        57005: 3008,  # dc_o_switch - captured on a real AC200L
        57022: 3066,  # ac_power_lifting_switch - captured on a real AC200PL, as on the AC240
        57023: 3065,  # d_charging_mode - captured on a real AC200PL
    },
    "AC500": {
        57001: 3007,  # ac_o_switch - captured on a real AC500, as on the AC240
    },
    "EP500P": {
        57005: 3008,  # dc_o_switch - captured on a real EP500Pro
        57009: 3011,  # g_i_switch - captured on a real EP500Pro
    },
    "FP": {
        57005: 2012,  # dc_o_switch - DC_SWITCH, captured on a real FridgePower
        57009: 2207,  # g_i_switch - CTRL_GRID, same as the Balco 260
    },
    "PA030": {
        57001: 2011,  # ac_o_switch - AC_SWITCH, captured on a real Apex 300
        57005: 2012,  # dc_o_switch - DC_SWITCH, the Balco family's, not 3008
        57009: 2207,  # g_i_switch - CTRL_GRID, captured on a real Apex 300
        57023: 2020,  # d_charging_mode - CHARGING_MODE, captured on a real Apex 300
    },
    "AC240": {
        57001: 3007,  # ac_o_switch - captured on a real AC240 (AC_SWITCH)
        57005: 3008,  # dc_o_switch - captured on a real AC240, as on the AC200L
        57009: 3011,  # g_i_switch - captured on a real AC240, as on the EP500Pro
        57022: 3066,  # ac_power_lifting_switch - captured on a real AC240
        57024: 3063,  # ac_eco_switch - captured on a real AC240
    },
    "AC300": {
        57005: 3008,  # dc_o_switch - captured on a real AC300
    },
}

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

# The failures a following attempt can recover from: a corrupted or
# truncated reply, no reply, or a connection the device dropped mid-request
# (the backend reconnects on the next request by itself). A dropped
# connection shows up on a real Balco 260 about as often as the other two,
# always on the first block of a poll, and used to fail the whole poll at
# once while those were retried.
_TRANSIENT_CAUSES = (ModbusProtocolError, ModbusTimeoutError, ModbusConnectionError)

# How long to leave the device before reading a setting back, and how many
# times to look again. A Balco 260 applies a write immediately but serves
# the old value for a moment afterwards - a read straight after the write
# returns the previous setting, and the next command shows the new one
# (confirmed on real hardware: writing b_soc_low 15 -> 16 read back 15, and
# the following run read 16). script/write_probe.py has always waited for
# the same reason.
READ_BACK_DELAY = 2.0
READ_BACK_ATTEMPTS = 3

# The setting registers BluettiDevice.write_register accepts where the
# profile marks the field writable - the ones script/write_probe.py tests -
# with the values each can hold, used where the field states no bound.
WRITABLE_REGISTERS: dict[int, range] = {
    57001: range(2),  # ac_o_switch
    57005: range(2),  # dc_o_switch
    57009: range(2),  # g_i_switch
    57010: range(2),  # g_o_switch
    57016: range(101),  # b_soc_low (%)
    57017: range(101),  # b_soc_high (%)
}


@dataclass(frozen=True)
class RegisterWrite:
    """What BluettiDevice.write_register saw: where the device confirmed the
    write, and what the register held once the device had settled."""

    address: int
    value: int
    confirmed_at: int
    """The address the confirmation carried: ``address`` itself for a plain
    Modbus confirmation, else the setting's internal address."""
    read_back: int

    @property
    def applied(self) -> bool:
        return self.read_back == self.value


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

    def readable_ranges(self) -> tuple[tuple[int, int], ...]:
        """The inclusive address runs read_registers accepts.

        Those the profile declares the device serves, kept apart as its own
        poll keeps them; else the runs that poll reads, field spans joined
        across gaps of at most max_gap. An address outside them may get no
        reply at all - a Balco 260 answers an unknown address read alone
        with an exception but goes silent when it is part of a longer read.
        """
        if self.register_ranges is not None:
            return tuple(sorted(self.register_ranges))
        spans = sorted(
            (field.address, field.address + field.count - 1)
            for field in self._register_fields.values()
        )
        runs: list[tuple[int, int]] = []
        for low, high in spans:
            if runs and low - runs[-1][1] <= self.max_gap:
                runs[-1] = (runs[-1][0], max(runs[-1][1], high))
            else:
                runs.append((low, high))
        return tuple(runs)

    async def read_registers(self, address: int, count: int) -> list[int]:
        """Read raw holding registers inside one of readable_ranges.

        Raises ValueError for a read that leaves those runs or is longer
        than max_span, and BluettiModbusConnectionError when the read fails.
        """
        if not 1 <= count <= self.max_span:
            raise ValueError(
                f"count must be between 1 and {self.max_span} on this device, "
                f"not {count}"
            )
        end = address + count - 1
        if not any(
            low <= address and end <= high for low, high in self.readable_ranges()
        ):
            raise ValueError(
                f"registers {address}-{end} are outside the ranges this device's "
                "profile reads"
            )
        try:
            return await self.modbus_unit.read_holding_registers(address, count)
        except ModbusError as err:
            raise BluettiModbusConnectionError(str(err)) from err

    async def write_register(
        self, address: int, value: int, *, settle: float = READ_BACK_DELAY
    ) -> RegisterWrite:
        """Write one setting register raw and read it back.

        Only the registers in WRITABLE_REGISTERS whose field this profile
        marks writable are accepted - a write confirmed on that device - with
        the field's own bound when it states one, else the register's value
        range there; ValueError otherwise.
        A confirmation at the setting's internal address counts as success,
        as in write(). The register is then read back after settle seconds,
        up to READ_BACK_ATTEMPTS times until it holds the value; whether it
        did is the result's applied, not an error. Any Modbus failure is
        raised as BluettiModbusConnectionError; a write is never retried.
        """
        allowed = WRITABLE_REGISTERS.get(address)
        field = next(
            (f for f in self._register_fields.values() if f.address == address),
            None,
        )
        if allowed is None or field is None or not field.writable:
            raise ValueError(f"register {address} is not a setting this device writes")
        if callable(field.writable):
            try:
                field.writable(value)
            except Invalid as err:
                raise ValueError(
                    f"{value} is out of range for {address}: {err}"
                ) from err
        elif value not in allowed:
            raise ValueError(
                f"{value} is out of range for {address} "
                f"({allowed.start}-{allowed.stop - 1})"
            )

        confirmed_at = address
        try:
            await self.modbus_unit.write_register(address, value)
        except ModbusProtocolError as err:
            echoed = _write_confirmation_address(err)
            if echoed is None or echoed[1] != value:
                raise BluettiModbusConnectionError(str(err)) from err
            confirmed_at = echoed[0]
        except ModbusError as err:
            raise BluettiModbusConnectionError(str(err)) from err

        read_back = value
        for _ in range(READ_BACK_ATTEMPTS):
            await asyncio.sleep(settle)
            [read_back] = await self.read_registers(address, 1)
            if read_back == value:
                break
        return RegisterWrite(address, value, confirmed_at, read_back)

    @override
    async def write(self, key: str, value: Any) -> None:
        """Write one writable field, accepting BLUETTI's own confirmation of it.

        A Balco 260 confirms a Write Single Register with the right function
        code and value but the setting's address in its internal register
        space instead of the Modbus one - see _INTERNAL_WRITE_ADDRESS. The
        write has applied every time this was captured (the official BLUETTI
        app shows the new value), so such a confirmation is treated as
        success here rather than surfacing as the protocol error a strict
        client makes of it. Which address was echoed is logged at debug when
        it is the one on file for that register and at warning when it
        isn't - the table holds only captured echoes, so a different one is
        worth reporting (a new device, a new register, or a new firmware) but
        not worth failing a write the device did apply. Anything else - a different
        function code or value, or a response shaped unlike a Write Single
        Register confirmation - is a real failure and is raised unchanged.
        """
        try:
            await super().write(key, value)
        except ModbusProtocolError as err:
            field = self.get_field(key)
            echoed = _write_confirmation_address(err)
            if (
                field is None
                or echoed is None
                or echoed[1] != _written_word(field, value)
            ):
                raise
            expected = _INTERNAL_WRITE_ADDRESS.get(type(self).__name__, {}).get(
                field.address
            )
            if echoed[0] == expected:
                _LOGGER.debug(
                    "Write to %s (%d) confirmed at internal register %d, as on file",
                    key,
                    field.address,
                    echoed[0],
                )
                return
            _LOGGER.warning(
                "Write to %s (%d) applied; the device confirmed it at internal "
                "register %d, %s - please report this echo so bluetti-modbus can "
                "record it. %s",
                key,
                field.address,
                echoed[0],
                f"not the {expected} on file for this register"
                if expected is not None
                else "which is not on file for this register",
                err,
            )

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
        - A connection the device dropped mid-request (ModbusConnectionError,
          "Connection lost before response was received"): the backend
          reconnects on the next request, so it is retried like the two
          below.
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
          why this isn't just one any more). If every one of those retries
          still hits the same kind of error, that's no longer "a one-off
          glitch" - retrying further on the same connection can't help a
          link the device's own Modbus TCP stack has gotten stuck on (this
          stack is known to become unresponsive under load - see
          ``BluettiModbusClient.read``'s own comment). The connection is
          dropped right before this last failure is raised, so whichever
          request follows (a caller's own outer retry, or simply the next
          poll cycle) opens a fresh one instead of repeating into the same
          stuck link. On a connection shared with other holders (Home
          Assistant's), that drops it for them too; their next request
          reconnects by itself (modbus-connection 4.12.4 and later also
          reconnect a request that was already waiting its turn).

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
            if not isinstance(err.__cause__, _TRANSIENT_CAUSES):
                raise

        for attempt in range(_TRANSIENT_RETRY_COUNT):
            try:
                await self._async_update_with_timeout()
                return
            except BluettiModbusConnectionError as err:
                if not isinstance(err.__cause__, _TRANSIENT_CAUSES):
                    raise
                if attempt == _TRANSIENT_RETRY_COUNT - 1:
                    await self.modbus_unit.disconnect()
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


def _write_confirmation_address(err: ModbusProtocolError) -> tuple[int, int] | None:
    """The (address, value) a mismatched Write Single Register confirmation
    carries, or None if the response isn't one - see BluettiDevice.write.

    modbus_connection wraps tmodbus's InvalidResponseError, which keeps the
    raw response, as the ModbusProtocolError's cause; a 0x06 confirmation is
    exactly function code, address, value, five bytes big-endian.
    """
    response = getattr(err.__cause__, "response_bytes", None)
    if not isinstance(response, bytes) or len(response) != 5:
        return None
    function_code: int
    address: int
    value: int
    function_code, address, value = struct.unpack(">BHH", response)
    if function_code != _WRITE_SINGLE_REGISTER_FUNCTION_CODE:
        return None
    return address, value


def _written_word(field: RegisterField[Any], value: Any) -> int | None:
    """The single register word modbus_connection put on the wire for value,
    or None when the write couldn't have been a single register - the same
    validator-then-encode steps its write_register_field takes, minus the
    scale register none of BLUETTI's writable fields has.
    """
    if callable(field.writable):
        value = field.writable(value)
    words = field.encode(value)
    return words[0] if len(words) == 1 else None
