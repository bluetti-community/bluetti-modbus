import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from modbus_connection.exceptions import (
    AcknowledgeError,
    IllegalDataAddressError,
    ModbusError,
)
from modbus_connection.mock import MockModbusConnection

from bluetti_modbus_lib.devices import Balco260
from bluetti_modbus_lib.exceptions import BluettiModbusConnectionError


def _balco260() -> Balco260:
    return Balco260(MockModbusConnection().for_unit(1))


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
