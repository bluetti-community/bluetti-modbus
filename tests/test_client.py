from unittest.mock import patch

import pytest
from modbus_connection.mock import MockModbusConnection

from bluetti_modbus_lib.exceptions import BluettiModbusConnectionError
from bluetti_modbus_lib.modbus.client import BluettiModbusClient, ClientReturnValue


def _client(
    device_type: str = "balco260",
) -> tuple[BluettiModbusClient, MockModbusConnection]:
    mock_conn = MockModbusConnection()
    # backend="pymodbus" (the default) imports ModbusConnection from
    # modbus_connection.pymodbus locally, inside __init__ - not a module-
    # level name in client.py, so the patch target is the real source, not
    # this module.
    with patch("modbus_connection.pymodbus.ModbusConnection", return_value=mock_conn):
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
async def test_read_reports_the_field_unit():
    client, mock_conn = _client()
    mock_conn.for_unit(1).holding[50002] = 100  # ac_o_p_total

    results = await client.read()

    by_name = {r.name: r for r in results}
    power = by_name["ac_o_p_total"]
    assert power.value == 100
    assert power.unit == "W"


@pytest.mark.asyncio
async def test_read_raises_on_timeout_without_closing_the_connection():
    client, mock_conn = _client()
    mock_conn.for_unit(1).fail_requests(TimeoutError("simulated timeout"))

    with pytest.raises(BluettiModbusConnectionError) as exc_info:
        await client.read()

    assert isinstance(exc_info.value.__cause__, TimeoutError)

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
async def test_aclose_closes_the_connection():
    client, mock_conn = _client()
    mock_conn.for_unit(1).holding[50001] = 2  # d_num_inverters
    await client.read()

    await client.aclose()

    assert mock_conn.connected is False


def test_client_return_value_str_includes_all_fields():
    value = ClientReturnValue(name="pv_i_p_total", unit="W", value=100)

    text = str(value)

    assert "pv_i_p_total" in text
    assert "100" in text
    assert "W" in text


def test_client_raises_for_an_unsupported_device_type():
    with pytest.raises(ValueError, match="not-a-real-device"):
        _client(device_type="not-a-real-device")


def test_default_backend_is_pymodbus():
    # Both HA integrations construct BluettiModbusClient without a backend=
    # argument at all - this must keep resolving to pymodbus, unchanged,
    # regardless of the tmodbus trial (backend="tmodbus", CLI-only for now).
    mock_conn = MockModbusConnection()
    with (
        patch(
            "modbus_connection.pymodbus.ModbusConnection", return_value=mock_conn
        ) as pym,
        patch("modbus_connection.tmodbus.ModbusConnection") as tm,
    ):
        BluettiModbusClient("10.0.0.1", 502, "balco260")

    pym.assert_called_once()
    tm.assert_not_called()


def test_backend_tmodbus_uses_the_tmodbus_connection():
    mock_conn = MockModbusConnection()
    with (
        patch("modbus_connection.pymodbus.ModbusConnection") as pym,
        patch(
            "modbus_connection.tmodbus.ModbusConnection", return_value=mock_conn
        ) as tm,
    ):
        BluettiModbusClient("10.0.0.1", 502, "balco260", backend="tmodbus")

    tm.assert_called_once()
    pym.assert_not_called()
