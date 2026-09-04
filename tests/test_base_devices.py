import asyncio
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

from bluetti_modbus_lib.devices import Balco260
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
async def test_async_update_with_retry_gives_up_after_a_second_corrupted_frame():
    device = _balco260()
    corrupted = BluettiModbusConnectionError("read_holding_registers(53001, 12): ...")
    corrupted.__cause__ = ModbusProtocolError(
        "Expected response to start with function code and byte count"
    )
    device.async_update = AsyncMock(side_effect=[corrupted, corrupted])  # type: ignore[method-assign]

    with pytest.raises(BluettiModbusConnectionError):
        await device.async_update_with_retry()

    assert device.async_update.await_count == 2


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
