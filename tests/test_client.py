from unittest.mock import patch

import pytest
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
async def test_read_closes_the_connection_even_on_timeout():
    client, mock_conn = _client()
    mock_conn.for_unit(1).fail_requests(TimeoutError("simulated timeout"))

    await client.read()

    assert mock_conn.connected is False


def test_client_return_value_str_includes_all_fields():
    value = ClientReturnValue(
        name="pv_i_p_total",
        unit="W",
        value=100,
        category=None,
        state_class="measurement",
        device_class="power",
    )

    text = str(value)

    assert "pv_i_p_total" in text
    assert "100" in text
    assert "n/a" in text  # category is None
