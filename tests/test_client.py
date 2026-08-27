from unittest.mock import AsyncMock, patch

import pytest
from modbus_connection.exceptions import AcknowledgeError, IllegalDataAddressError
from modbus_connection.mock import MockModbusConnection

from bluetti_modbus_lib.fields.field_extras import DeviceClass, FieldStateClass
from bluetti_modbus_lib.modbus.client import BluettiModbusClient, ClientReturnValue


def _client(device_type: str = "balco260") -> tuple[BluettiModbusClient, MockModbusConnection]:
    mock_conn = MockModbusConnection()
    with patch("bluetti_modbus_lib.modbus.client.ModbusConnection", return_value=mock_conn):
        client = BluettiModbusClient("10.0.0.1", 502, device_type)
    return client, mock_conn


@pytest.mark.asyncio
async def test_read_returns_decoded_values_from_the_device():
    client, mock_conn = _client()
    mock_conn.for_unit(1).holding[50001] = 2  # d_num_inverters

    results = await client.read()

    by_name = {r.name: r for r in results}
    assert by_name["d_num_inverters"].value == 2


@pytest.mark.asyncio
async def test_read_reports_category_state_class_and_device_class():
    client, mock_conn = _client()
    mock_conn.for_unit(1).holding[50002] = 100  # ac_o_p_total (power, measurement)

    results = await client.read()

    by_name = {r.name: r for r in results}
    power = by_name["ac_o_p_total"]
    assert power.value == 100
    assert power.unit == "W"
    assert power.device_class == DeviceClass.POWER
    assert power.state_class == FieldStateClass.MEASUREMENT


@pytest.mark.asyncio
async def test_read_raises_on_timeout_without_closing_the_connection():
    client, mock_conn = _client()
    mock_conn.for_unit(1).fail_requests(TimeoutError("simulated timeout"))

    with pytest.raises(TimeoutError):
        await client.read()

    # A failed read must not tear the connection down - opening a fresh one on
    # every read/retry is exactly what makes this device's Modbus TCP stack
    # unresponsive under load. The link stays usable for the next read.
    assert mock_conn.connected is True


@pytest.mark.asyncio
async def test_consecutive_reads_reuse_the_same_connection():
    client, mock_conn = _client()
    mock_conn.for_unit(1).holding[50001] = 2  # d_num_inverters

    await client.read()
    assert mock_conn.connected is True
    await client.read()

    assert mock_conn.connected is True


@pytest.mark.asyncio
async def test_read_reconnects_transparently_after_a_dropped_link():
    client, mock_conn = _client()
    mock_conn.for_unit(1).holding[50001] = 2  # d_num_inverters

    await client.read()
    mock_conn.simulate_connection_lost()
    results = await client.read()

    by_name = {r.name: r for r in results}
    assert by_name["d_num_inverters"].value == 2


@pytest.mark.asyncio
async def test_read_retries_once_after_an_acknowledge_response():
    client, _ = _client()
    client.device.async_update = AsyncMock(  # type: ignore[method-assign]
        side_effect=[AcknowledgeError(5), None]
    )

    await client.read()

    assert client.device.async_update.await_count == 2


@pytest.mark.asyncio
async def test_read_gives_up_after_a_second_acknowledge_response():
    client, _ = _client()
    client.device.async_update = AsyncMock(  # type: ignore[method-assign]
        side_effect=[AcknowledgeError(5), AcknowledgeError(5)]
    )

    with pytest.raises(AcknowledgeError):
        await client.read()

    assert client.device.async_update.await_count == 2


@pytest.mark.asyncio
async def test_read_does_not_retry_a_non_transient_modbus_error():
    client, _ = _client()
    client.device.async_update = AsyncMock(  # type: ignore[method-assign]
        side_effect=IllegalDataAddressError(2)
    )

    with pytest.raises(IllegalDataAddressError):
        await client.read()

    assert client.device.async_update.await_count == 1


@pytest.mark.asyncio
async def test_aclose_closes_the_connection():
    client, mock_conn = _client()
    mock_conn.for_unit(1).holding[50001] = 2  # d_num_inverters
    await client.read()

    await client.aclose()

    assert mock_conn.connected is False


def test_client_return_value_str_includes_all_fields():
    value = ClientReturnValue(
        name="pv_i_p_total",
        unit="W",
        value=100,
        category=None,
        state_class=FieldStateClass.MEASUREMENT,
        device_class=DeviceClass.POWER,
    )

    text = str(value)

    assert "pv_i_p_total" in text
    assert "100" in text
    assert "n/a" in text  # category is None


def test_client_raises_for_an_unsupported_device_type():
    with pytest.raises(ValueError, match="not-a-real-device"):
        _client(device_type="not-a-real-device")
