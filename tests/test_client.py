import ssl
from unittest.mock import patch

import pytest
from modbus_connection import ModbusTcpParams, ModbusTlsParams
from modbus_connection.mock import MockModbusConnection

from bluetti_modbus_lib.exceptions import BluettiModbusConnectionError
from bluetti_modbus_lib.modbus.client import BluettiModbusClient, ClientReturnValue


def _client(
    device_type: str = "balco260",
) -> tuple[BluettiModbusClient, MockModbusConnection]:
    mock_conn = MockModbusConnection()
    # backend="tmodbus" (the default since 0.4.0) imports ModbusConnection
    # from modbus_connection.tmodbus locally, inside __init__ - not a
    # module-level name in client.py, so the patch target is the real
    # source, not this module.
    with patch("modbus_connection.tmodbus.ModbusConnection", return_value=mock_conn):
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


def test_default_backend_is_tmodbus():
    # Both HA integrations construct BluettiModbusClient without a backend=
    # argument at all - since 0.4.0 this resolves to tmodbus, confirmed via
    # persistent-connection testing against real Balco260/S Meter hardware
    # (see #29 and CONTRIBUTING.md).
    mock_conn = MockModbusConnection()
    with (
        patch("modbus_connection.pymodbus.ModbusConnection") as pym,
        patch(
            "modbus_connection.tmodbus.ModbusConnection", return_value=mock_conn
        ) as tm,
    ):
        BluettiModbusClient("10.0.0.1", 502, "balco260")

    tm.assert_called_once()
    pym.assert_not_called()


def test_backend_pymodbus_uses_the_pymodbus_connection():
    mock_conn = MockModbusConnection()
    with (
        patch(
            "modbus_connection.pymodbus.ModbusConnection", return_value=mock_conn
        ) as pym,
        patch("modbus_connection.tmodbus.ModbusConnection") as tm,
    ):
        BluettiModbusClient("10.0.0.1", 502, "balco260", backend="pymodbus")

    pym.assert_called_once()
    tm.assert_not_called()


def _params_passed_to(mock_backend):
    return mock_backend.call_args.args[0]


def test_plain_tcp_by_default():
    with patch(
        "modbus_connection.tmodbus.ModbusConnection",
        return_value=MockModbusConnection(),
    ) as tm:
        client = BluettiModbusClient("10.0.0.1", 502, "balco260")

    params = _params_passed_to(tm)
    assert isinstance(params, ModbusTcpParams)
    assert (params.host, params.port) == ("10.0.0.1", 502)
    assert client.params is params


def test_tls_builds_tls_params_with_the_given_options():
    with patch(
        "modbus_connection.tmodbus.ModbusConnection",
        return_value=MockModbusConnection(),
    ) as tm:
        BluettiModbusClient(
            "10.0.0.1",
            802,
            "ep500p",
            tls=True,
            verify="/etc/ssl/device-ca.pem",
            check_hostname=False,
            client_cert="/etc/ssl/client.pem",
            client_key="/etc/ssl/client.key",
            client_key_password="secret",
        )

    params = _params_passed_to(tm)
    assert isinstance(params, ModbusTlsParams)
    assert (params.host, params.port) == ("10.0.0.1", 802)
    assert params.verify == "/etc/ssl/device-ca.pem"
    assert params.check_hostname is False
    assert (params.client_cert, params.client_key, params.client_key_password) == (
        "/etc/ssl/client.pem",
        "/etc/ssl/client.key",
        "secret",
    )


def test_tls_with_the_pymodbus_backend():
    with (
        patch(
            "modbus_connection.pymodbus.ModbusConnection",
            return_value=MockModbusConnection(),
        ) as pym,
        patch("modbus_connection.tmodbus.ModbusConnection") as tm,
    ):
        BluettiModbusClient("10.0.0.1", 802, "balco260", backend="pymodbus", tls=True)

    assert isinstance(_params_passed_to(pym), ModbusTlsParams)
    tm.assert_not_called()


@pytest.mark.asyncio
async def test_tls_params_build_an_ssl_context_the_backend_can_use():
    with patch(
        "modbus_connection.tmodbus.ModbusConnection",
        return_value=MockModbusConnection(),
    ):
        verified = BluettiModbusClient("10.0.0.1", 802, "balco260", tls=True)
        self_signed = BluettiModbusClient(
            "10.0.0.1", 802, "balco260", tls=True, verify=False
        )

    assert isinstance(verified.params, ModbusTlsParams)
    assert isinstance(self_signed.params, ModbusTlsParams)
    strict = await verified.params.create_ssl_context()
    lax = await self_signed.params.create_ssl_context()

    assert strict.verify_mode == ssl.CERT_REQUIRED
    assert strict.check_hostname is True
    # verify=False is the self-signed-certificate case: no verification at all.
    assert lax.verify_mode == ssl.CERT_NONE
    assert lax.check_hostname is False


def test_tls_options_without_tls_are_refused():
    with pytest.raises(ValueError, match="tls=True"):
        BluettiModbusClient("10.0.0.1", 502, "balco260", verify=False)
