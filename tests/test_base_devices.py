import asyncio
from unittest.mock import AsyncMock

import pytest
from modbus_connection.exceptions import AcknowledgeError, IllegalDataAddressError
from modbus_connection.mock import MockModbusConnection

from bluetti_modbus_lib.devices import Balco260


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
async def test_async_update_with_retry_does_not_retry_a_non_transient_error():
    device = _balco260()
    device.async_update = AsyncMock(side_effect=IllegalDataAddressError(2))  # type: ignore[method-assign]

    with pytest.raises(IllegalDataAddressError):
        await device.async_update_with_retry()

    assert device.async_update.await_count == 1


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
