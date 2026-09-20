import asyncio
import logging
import struct
from unittest.mock import AsyncMock, patch

import pytest
from modbus_connection.exceptions import (
    AcknowledgeError,
    IllegalDataAddressError,
    ModbusError,
    ModbusProtocolError,
    ModbusTimeoutError,
)
from modbus_connection.mock import MockModbusConnection
from probatio.error import RangeInvalid

from bluetti_modbus_lib.devices import AC200L, EP500P, Balco260
from bluetti_modbus_lib.exceptions import BluettiModbusConnectionError


def _balco260() -> Balco260:
    return Balco260(MockModbusConnection().for_unit(1))


def _balco260_with_unit():
    mock_conn = MockModbusConnection()
    return Balco260(mock_conn.for_unit(1)), mock_conn


def test_field_names_and_get_sensors_are_the_same_view():
    device = Balco260(None)

    assert list(device.field_names()) == list(device.get_sensors())
    assert len(list(device.field_names())) > 0


def test_get_field_returns_the_registered_field():
    device = Balco260(None)
    name = next(iter(device.field_names()))

    assert device.get_field(name) is not None


def test_get_field_returns_none_for_unknown_field():
    device = Balco260(None)

    assert device.get_field("not_a_real_field") is None


def test_values_is_empty_before_any_update():
    device = Balco260(None)

    assert device.values == {}


def test_values_returns_a_copy_not_a_live_reference():
    device = Balco260(None)

    values = device.values
    values["injected"] = 1

    assert "injected" not in device.values


@pytest.mark.asyncio
async def test_async_update_with_retry_retries_once_after_an_acknowledge_response():
    device = _balco260()
    device.async_update = AsyncMock(side_effect=[AcknowledgeError(5), None])  # type: ignore[method-assign]

    await device.async_update_with_retry()

    assert device.async_update.await_count == 2


@pytest.mark.asyncio
async def test_async_update_with_retry_gives_up_after_a_second_busy_response():
    device = _balco260()
    device.async_update = AsyncMock(  # type: ignore[method-assign]
        side_effect=[AcknowledgeError(5), AcknowledgeError(5)]
    )

    with pytest.raises(AcknowledgeError):
        await device.async_update_with_retry()

    assert device.async_update.await_count == 2


@pytest.mark.asyncio
async def test_async_update_with_retry_retries_once_after_a_corrupted_frame():
    # Real-hardware evidence (persistent-connection testing against a real
    # Balco260/S Meter, tmodbus backend - bluetti-community/bluetti-modbus#29):
    # this recovers cleanly on the very next read on the same connection,
    # every time observed, with no reconnect needed.
    device = _balco260()
    corrupted = BluettiModbusConnectionError(
        "read_holding_registers(53001, 12): Expected response to start "
        "with function code and byte count"
    )
    corrupted.__cause__ = ModbusProtocolError(
        "Expected response to start with function code and byte count"
    )
    device.async_update = AsyncMock(side_effect=[corrupted, None])  # type: ignore[method-assign]

    await device.async_update_with_retry()

    assert device.async_update.await_count == 2


@pytest.mark.asyncio
async def test_async_update_with_retry_retries_once_after_a_pymodbus_timeout():
    # pymodbus can't tell a corrupted reply apart from no reply at all - both
    # surface as ModbusTimeoutError (confirmed via a real wire-level capture:
    # the device's malformed reply still arrived, pymodbus just discarded it
    # and then genuinely timed out) - retried the same as ModbusProtocolError.
    device = _balco260()
    timed_out = BluettiModbusConnectionError(
        "read_holding_registers(51001, 8): Modbus Error: [Input/Output] "
        "No response received after 0 retries, continue with next request"
    )
    timed_out.__cause__ = ModbusTimeoutError("no response")
    device.async_update = AsyncMock(side_effect=[timed_out, None])  # type: ignore[method-assign]

    await device.async_update_with_retry()

    assert device.async_update.await_count == 2


@pytest.mark.asyncio
async def test_async_update_with_retry_recovers_after_two_consecutive_corrupted_frames():
    # Real HA logs (bluetti-community/bluetti-modbus#29) showed the original
    # single retry wasn't always enough - two corrupted frames back to back
    # on the same live Balco260. _TRANSIENT_RETRY_COUNT=2 means this now
    # recovers instead of surfacing as a coordinator error.
    device = _balco260()
    corrupted = BluettiModbusConnectionError("read_holding_registers(53001, 12): ...")
    corrupted.__cause__ = ModbusProtocolError(
        "Expected response to start with function code and byte count"
    )
    device.async_update = AsyncMock(  # type: ignore[method-assign]
        side_effect=[corrupted, corrupted, None]
    )

    await device.async_update_with_retry()

    assert device.async_update.await_count == 3


@pytest.mark.asyncio
async def test_async_update_with_retry_stops_retrying_on_a_non_transient_error_mid_loop():
    # Regression test: a transient failure that then turns into a permanent
    # one (e.g. the device drops the connection for real, or a genuinely
    # illegal address) must not keep consuming the retry budget - it should
    # surface immediately, same as if it had been the very first failure.
    device = _balco260()
    corrupted = BluettiModbusConnectionError("read_holding_registers(53001, 12): ...")
    corrupted.__cause__ = ModbusProtocolError(
        "Expected response to start with function code and byte count"
    )
    permanent = BluettiModbusConnectionError("read_holding_registers(53001, 12): ...")
    permanent.__cause__ = IllegalDataAddressError(2)
    device.async_update = AsyncMock(  # type: ignore[method-assign]
        side_effect=[corrupted, permanent]
    )

    with pytest.raises(BluettiModbusConnectionError) as exc_info:
        await device.async_update_with_retry()

    assert device.async_update.await_count == 2
    assert exc_info.value is permanent


@pytest.mark.asyncio
async def test_async_update_with_retry_gives_up_after_a_third_corrupted_frame():
    device, mock_conn = _balco260_with_unit()
    corrupted = BluettiModbusConnectionError("read_holding_registers(53001, 12): ...")
    corrupted.__cause__ = ModbusProtocolError(
        "Expected response to start with function code and byte count"
    )
    device.async_update = AsyncMock(  # type: ignore[method-assign]
        side_effect=[corrupted, corrupted, corrupted]
    )
    unit = mock_conn.for_unit(1)

    with (
        patch.object(unit, "disconnect", AsyncMock()) as disconnect,
        pytest.raises(BluettiModbusConnectionError),
    ):
        await device.async_update_with_retry()

    assert device.async_update.await_count == 3
    # Every retry hit the same kind of error - no reason left to believe
    # this connection will recover on its own, so it's dropped here rather
    # than left for the next attempt to get stuck on too.
    disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_update_with_retry_does_not_disconnect_after_recovering():
    # The far more common case: a transient error that DOES recover within
    # the retry budget must not pay for a reconnect it doesn't need.
    device, mock_conn = _balco260_with_unit()
    corrupted = BluettiModbusConnectionError("read_holding_registers(53001, 12): ...")
    corrupted.__cause__ = ModbusProtocolError(
        "Expected response to start with function code and byte count"
    )
    device.async_update = AsyncMock(side_effect=[corrupted, None])  # type: ignore[method-assign]
    unit = mock_conn.for_unit(1)
    with patch.object(unit, "disconnect", AsyncMock()) as disconnect:
        await device.async_update_with_retry()

    disconnect.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_update_with_retry_does_not_disconnect_for_a_busy_device():
    # AcknowledgeError/ServerDeviceBusyError mean the device answered - it's
    # just not ready yet. That's a different signal from a stuck link, and
    # disconnecting wouldn't help a device that's already responding.
    device, mock_conn = _balco260_with_unit()
    device.async_update = AsyncMock(  # type: ignore[method-assign]
        side_effect=[AcknowledgeError(5), AcknowledgeError(5)]
    )
    unit = mock_conn.for_unit(1)
    with (
        patch.object(unit, "disconnect", AsyncMock()) as disconnect,
        pytest.raises(AcknowledgeError),
    ):
        await device.async_update_with_retry()

    disconnect.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_update_with_retry_wraps_a_non_transient_error():
    # Regression test: a ModbusError that isn't a transient busy response
    # (so never retried) must come out as BluettiModbusConnectionError, not
    # the bare modbus_connection exception - the point of that type is one
    # thing to catch regardless of which failure mode triggered it. Still
    # also a ModbusError itself (see the exception's own docstring), and the
    # original exception stays reachable via __cause__.
    device = _balco260()
    device.async_update = AsyncMock(side_effect=IllegalDataAddressError(2))  # type: ignore[method-assign]

    with pytest.raises(BluettiModbusConnectionError) as exc_info:
        await device.async_update_with_retry()

    assert device.async_update.await_count == 1
    assert isinstance(exc_info.value, ModbusError)
    assert isinstance(exc_info.value.__cause__, IllegalDataAddressError)


@pytest.mark.asyncio
async def test_async_update_with_retry_wraps_a_timeout():
    # Regression test: a plain TimeoutError (the whole-sequence budget in
    # _async_update_with_timeout expiring, or anything else that raises one)
    # must also come out as BluettiModbusConnectionError, not bare.
    device = _balco260()
    device.async_update = AsyncMock(side_effect=TimeoutError("no response"))  # type: ignore[method-assign]

    with pytest.raises(BluettiModbusConnectionError) as exc_info:
        await device.async_update_with_retry()

    assert isinstance(exc_info.value.__cause__, TimeoutError)


@pytest.mark.asyncio
async def test_async_update_with_retry_does_not_double_wrap():
    # Regression test: going through async_update_with_retry with the real
    # async_update override active (not mocked away, unlike every other test
    # here) must not wrap an already-wrapped BluettiModbusConnectionError a
    # second time - the original cause must stay one hop away, not two.
    device = _balco260()

    with (
        patch(
            "modbus_connection.model.Component.async_update",
            AsyncMock(side_effect=IllegalDataAddressError(2)),
        ),
        pytest.raises(BluettiModbusConnectionError) as exc_info,
    ):
        await device.async_update_with_retry()

    assert isinstance(exc_info.value.__cause__, IllegalDataAddressError)


@pytest.mark.asyncio
async def test_async_update_wraps_a_modbus_error_directly():
    # async_update() itself (not just async_update_with_retry) must also
    # wrap - the README documents it as a valid, direct entry point. Patches
    # the base Component.async_update, not this instance's own attribute:
    # mocking device.async_update would replace the very override under test.
    device = _balco260()

    with (
        patch(
            "modbus_connection.model.Component.async_update",
            AsyncMock(side_effect=IllegalDataAddressError(2)),
        ),
        pytest.raises(BluettiModbusConnectionError) as exc_info,
    ):
        await device.async_update()

    assert isinstance(exc_info.value.__cause__, IllegalDataAddressError)


@pytest.mark.asyncio
async def test_async_update_does_not_wrap_a_transient_busy_response():
    # A direct async_update() call must still let a caller distinguish a
    # transient busy response from a real connection failure, same as
    # async_update_with_retry does - only async_update_with_retry decides
    # whether to retry it.
    device = _balco260()

    with (
        patch(
            "modbus_connection.model.Component.async_update",
            AsyncMock(side_effect=AcknowledgeError(5)),
        ),
        pytest.raises(AcknowledgeError),
    ):
        await device.async_update()


@pytest.mark.asyncio
async def test_async_update_with_retry_survives_a_slow_update_within_the_budget():
    # Regression test: the update-wide timeout must be large enough to cover
    # a single slow register block, not just fail immediately - a real
    # production symptom ("Request cancelled outside library") was traced to
    # this budget being too tight for how long one block can legitimately
    # take on this device's Modbus TCP stack under load.
    device = _balco260()

    async def slow_update() -> None:
        await asyncio.sleep(15)

    device.async_update = AsyncMock(side_effect=slow_update)  # type: ignore[method-assign]

    await device.async_update_with_retry()

    device.async_update.assert_awaited_once()


@pytest.mark.asyncio
async def test_b_soc_low_write_within_bounds_reaches_the_device():
    # b_soc_low (register 57016) is one of the two SOC-threshold fields
    # bluetti-registers marks writeable, bounded 5-90 on Balco260 (the
    # official BLUETTI app's own SOC screen doesn't allow this discharge-
    # stop threshold outside that range) - see import.py's Range()-based
    # writable=. Confirms the whole chain, not just that field() accepts
    # the parameter: a real write actually lands on the register the mock
    # holds.
    device, mock_conn = _balco260_with_unit()

    await device.write("b_soc_low", 42)

    assert mock_conn.for_unit(1).holding[57016] == 42


@pytest.mark.asyncio
async def test_b_soc_low_write_above_the_bound_is_rejected():
    device, mock_conn = _balco260_with_unit()

    # 95 - within the old, wider 0-100 range this field used to have, so
    # this is a real regression check for the tightened 5-90 bound, not
    # just any out-of-range value.
    with pytest.raises(RangeInvalid):
        await device.write("b_soc_low", 95)

    # Rejected before it ever reaches the device - nothing was written.
    assert 57016 not in mock_conn.for_unit(1).holding


@pytest.mark.asyncio
async def test_b_soc_low_write_below_the_bound_is_rejected():
    device, mock_conn = _balco260_with_unit()

    with pytest.raises(RangeInvalid):
        await device.write("b_soc_low", 3)

    assert 57016 not in mock_conn.for_unit(1).holding


@pytest.mark.asyncio
async def test_ac_o_switch_is_writable_without_a_bound():
    # ac_o_switch (57001) is writeable in the schema but has no num_min/
    # num_max - plain writable=True, no validator.
    device, mock_conn = _balco260_with_unit()

    await device.write("ac_o_switch", 1)

    assert mock_conn.for_unit(1).holding[57001] == 1


def _mismatched_confirmation(
    function_code: int, address: int, value: int
) -> ModbusProtocolError:
    """A ModbusProtocolError chained from tmodbus's InvalidResponseError, the
    shape modbus_connection raises when a Write Single Register confirmation
    doesn't match the request - carrying the device's actual response bytes.
    """
    from tmodbus.exceptions import InvalidResponseError

    cause = InvalidResponseError(
        "Expected response to match request",
        response_bytes=struct.pack(">BHH", function_code, address, value),
    )
    err = ModbusProtocolError("write_register(...): Expected response to match request")
    err.__cause__ = cause
    return err


def _balco260_whose_writes_confirm_as(
    function_code: int, address: int, value: int
) -> Balco260:
    device = _balco260()
    device.modbus_unit.write_register = AsyncMock(  # type: ignore[method-assign]
        side_effect=_mismatched_confirmation(function_code, address, value)
    )
    return device


@pytest.mark.asyncio
async def test_write_accepts_a_confirmation_at_the_internal_address_on_file(caplog):
    # Captured on a real Balco 260: the device confirms a write to 57016
    # (b_soc_low) at 2022, its own internal address for that setting - see
    # _INTERNAL_WRITE_ADDRESS. The write applied; the confirmation is just
    # in the device's address space, so it is success, logged at debug.
    device = _balco260_whose_writes_confirm_as(function_code=6, address=2022, value=20)

    with caplog.at_level(logging.DEBUG, logger="bluetti_modbus_lib"):
        await device.write("b_soc_low", 20)  # must not raise

    assert "b_soc_low (57016) confirmed at internal register 2022" in caplog.text
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


@pytest.mark.asyncio
async def test_write_accepts_but_reports_a_confirmation_at_an_address_not_on_file(
    caplog,
):
    # The table is confirmed on a Balco 260, so a different echo is news
    # worth a warning (a new firmware, another device) - but the function
    # code and value still say the device applied this write, so it is not
    # a failure.
    device = _balco260_whose_writes_confirm_as(function_code=6, address=2999, value=1)

    with caplog.at_level(logging.WARNING, logger="bluetti_modbus_lib"):
        await device.write("g_o_switch", 1)  # must not raise

    assert "g_o_switch (57010) applied" in caplog.text
    assert "internal register 2999, not the 2208 on file" in caplog.text


@pytest.mark.asyncio
async def test_write_looks_the_echo_up_per_device(caplog):
    # Captured on a real AC200L2 (bluetti-modbus#78): its DC output switch
    # (57005) confirms at 3008 - nowhere near what the Balco family's
    # internal map would say. The table is keyed by device, so this is the
    # entry on file for an AC200L and logs at debug, not warning.
    device = AC200L(MockModbusConnection().for_unit(1))
    device.modbus_unit.write_register = AsyncMock(  # type: ignore[method-assign]
        side_effect=_mismatched_confirmation(6, 3008, 1)
    )

    with caplog.at_level(logging.DEBUG, logger="bluetti_modbus_lib"):
        await device.write("dc_o_switch", 1)  # must not raise

    assert "dc_o_switch (57005) confirmed at internal register 3008" in caplog.text
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


@pytest.mark.asyncio
async def test_write_knows_the_ep500p_dc_switch_echo(caplog):
    # Captured on a real EP500Pro on its owner's first toggles in Home
    # Assistant (hassio-bluetti-modbus#122, 2026-09-20): 57005 confirms at
    # 3008, the same internal address as the AC200L2's - on file, so debug.
    device = EP500P(MockModbusConnection().for_unit(1))
    device.modbus_unit.write_register = AsyncMock(  # type: ignore[method-assign]
        side_effect=_mismatched_confirmation(6, 3008, 0)
    )

    with caplog.at_level(logging.DEBUG, logger="bluetti_modbus_lib"):
        await device.write("dc_o_switch", 0)  # must not raise

    assert "dc_o_switch (57005) confirmed at internal register 3008" in caplog.text
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


@pytest.mark.asyncio
async def test_write_reports_an_echo_for_a_device_with_no_entries_at_all(caplog):
    # A device class the table does not know (nothing captured on it yet):
    # the echo is accepted and reported as not on file, never raised.
    device = _balco260_whose_writes_confirm_as(function_code=6, address=2011, value=1)

    with (
        patch.dict(
            "bluetti_modbus_lib.base_devices.bluetti_device._INTERNAL_WRITE_ADDRESS",
            {},
            clear=True,
        ),
        caplog.at_level(logging.WARNING, logger="bluetti_modbus_lib"),
    ):
        await device.write("ac_o_switch", 1)  # must not raise

    assert "internal register 2011, which is not on file" in caplog.text


@pytest.mark.asyncio
async def test_write_accepts_but_reports_a_confirmation_for_a_register_without_an_entry(
    caplog,
):
    # A field that is writable but whose Modbus address has no entry in the
    # table at all (none of Balco 260's - so exercised through the table
    # itself, missing the entry for this register).
    device = _balco260_whose_writes_confirm_as(function_code=6, address=1234, value=1)

    with (
        patch.dict(
            "bluetti_modbus_lib.base_devices.bluetti_device._INTERNAL_WRITE_ADDRESS",
            {"Balco260": {}},
            clear=True,
        ),
        caplog.at_level(logging.WARNING, logger="bluetti_modbus_lib"),
    ):
        await device.write("ac_o_switch", 1)  # must not raise

    assert "internal register 1234, which is not on file" in caplog.text


@pytest.mark.asyncio
async def test_write_reraises_when_the_confirmed_value_differs():
    # Same function code, same internal address, but a different value than
    # the one written - not the known confirmation quirk, a real failure.
    device = _balco260_whose_writes_confirm_as(function_code=6, address=2022, value=21)

    with pytest.raises(ModbusProtocolError):
        await device.write("b_soc_low", 20)


@pytest.mark.asyncio
async def test_write_reraises_when_the_function_code_differs():
    device = _balco260_whose_writes_confirm_as(function_code=3, address=2022, value=20)

    with pytest.raises(ModbusProtocolError):
        await device.write("b_soc_low", 20)


@pytest.mark.asyncio
async def test_write_reraises_when_the_response_is_not_a_single_register_confirmation():
    device = _balco260()
    err = ModbusProtocolError("write_register(...): Expected response to match request")
    err.__cause__ = ValueError("no response_bytes here")
    device.modbus_unit.write_register = AsyncMock(side_effect=err)  # type: ignore[method-assign]

    with pytest.raises(ModbusProtocolError):
        await device.write("b_soc_low", 20)


@pytest.mark.asyncio
async def test_write_reraises_when_the_response_has_the_wrong_length():
    from tmodbus.exceptions import InvalidResponseError

    device = _balco260()
    err = ModbusProtocolError("write_register(...): Expected response to match request")
    err.__cause__ = InvalidResponseError("short", response_bytes=b"\x06\x07")
    device.modbus_unit.write_register = AsyncMock(side_effect=err)  # type: ignore[method-assign]

    with pytest.raises(ModbusProtocolError):
        await device.write("b_soc_low", 20)


@pytest.mark.asyncio
async def test_write_reraises_for_a_field_that_does_not_exist():
    # Component.write raises AttributeError for an unknown key before any
    # Modbus traffic; the override must not get in the way of that.
    device = _balco260()

    with pytest.raises(AttributeError):
        await device.write("not_a_real_field", 1)
