import ssl
from unittest.mock import patch

import pytest
from modbus_connection import ModbusSerialParams, ModbusTcpParams, ModbusTlsParams
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


def test_serial_builds_serial_params_with_the_line_settings():
    # An RS485 adapter on a real port: the line settings are the device's,
    # so they are passed as given.
    with patch(
        "modbus_connection.tmodbus.ModbusConnection",
        return_value=MockModbusConnection(),
    ) as tm:
        client = BluettiModbusClient(
            device_type="ep2000",
            serial_device="/dev/ttyUSB0",
            baudrate=19200,
            parity="E",
            stopbits=2,
            bytesize=7,
        )

    params = _params_passed_to(tm)
    assert isinstance(params, ModbusSerialParams)
    assert params.device == "/dev/ttyUSB0"
    assert (params.baudrate, params.parity, params.stopbits, params.bytesize) == (
        19200,
        "E",
        2,
        7,
    )
    # RTU: the framing every BLUETTI serial port is expected to speak.
    assert params.framer == "rtu"
    assert client.params is params


def test_serial_defaults_match_the_common_rs485_line():
    with patch(
        "modbus_connection.tmodbus.ModbusConnection",
        return_value=MockModbusConnection(),
    ) as tm:
        BluettiModbusClient(device_type="ep2000", serial_device="/dev/ttyUSB0")

    params = _params_passed_to(tm)
    assert (params.baudrate, params.parity, params.stopbits, params.bytesize) == (
        9600,
        "N",
        1,
        8,
    )


def test_a_serial_to_tcp_gateway_is_just_another_device_string():
    # socket://host:port is pyserial's own URL form: the gateway owns the
    # line settings, this end only has to name it.
    with patch(
        "modbus_connection.tmodbus.ModbusConnection",
        return_value=MockModbusConnection(),
    ) as tm:
        BluettiModbusClient(
            device_type="ep2000", serial_device="socket://192.168.1.50:8899"
        )

    assert _params_passed_to(tm).device == "socket://192.168.1.50:8899"


def test_serial_with_the_pymodbus_backend():
    with (
        patch(
            "modbus_connection.pymodbus.ModbusConnection",
            return_value=MockModbusConnection(),
        ) as pym,
        patch("modbus_connection.tmodbus.ModbusConnection") as tm,
    ):
        BluettiModbusClient(
            device_type="balco260", serial_device="/dev/ttyUSB0", backend="pymodbus"
        )

    assert isinstance(_params_passed_to(pym), ModbusSerialParams)
    tm.assert_not_called()


def test_a_transport_has_to_be_named():
    with pytest.raises(ValueError, match="host"):
        BluettiModbusClient(device_type="balco260")


def test_the_two_transports_are_mutually_exclusive():
    with pytest.raises(ValueError, match="mutually exclusive"):
        BluettiModbusClient(
            "10.0.0.1", device_type="balco260", serial_device="/dev/ttyUSB0"
        )


def test_a_port_is_refused_next_to_a_serial_device():
    with pytest.raises(ValueError, match="port belongs to a TCP connection"):
        BluettiModbusClient(
            port=502, device_type="balco260", serial_device="/dev/ttyUSB0"
        )


def test_tls_is_refused_on_a_serial_line():
    with pytest.raises(ValueError, match="no serial equivalent"):
        BluettiModbusClient(
            device_type="balco260", serial_device="/dev/ttyUSB0", tls=True
        )


def test_the_device_type_is_required():
    with pytest.raises(ValueError, match="device_type"):
        BluettiModbusClient("10.0.0.1", 502)


def test_a_host_without_a_port_gets_the_modbus_tcp_port():
    with patch(
        "modbus_connection.tmodbus.ModbusConnection",
        return_value=MockModbusConnection(),
    ) as tm:
        BluettiModbusClient("10.0.0.1", device_type="balco260")

    assert _params_passed_to(tm).port == 502


def test_the_unit_id_selects_which_device_on_the_bus_is_read():
    # Everything BLUETTI answers at 1 over TCP; a shared RS485 bus is what
    # this is for.
    mock_conn = MockModbusConnection()
    with patch("modbus_connection.tmodbus.ModbusConnection", return_value=mock_conn):
        client = BluettiModbusClient(
            device_type="balco260", serial_device="/dev/ttyUSB0", unit_id=7
        )

    assert client.device.modbus_unit is mock_conn.for_unit(7)


def test_unit_id_1_stays_the_default():
    mock_conn = MockModbusConnection()
    with patch("modbus_connection.tmodbus.ModbusConnection", return_value=mock_conn):
        client = BluettiModbusClient("10.0.0.1", 502, "balco260")

    assert client.device.modbus_unit is mock_conn.for_unit(1)


def test_message_spacing_is_handed_to_the_backend():
    with patch(
        "modbus_connection.tmodbus.ModbusConnection",
        return_value=MockModbusConnection(),
    ) as tm:
        BluettiModbusClient(
            device_type="balco260", serial_device="/dev/ttyUSB0", message_spacing=0.05
        )

    assert tm.call_args.kwargs["message_spacing"] == 0.05


def test_no_message_spacing_leaves_the_backend_to_its_own_pacing():
    with patch(
        "modbus_connection.tmodbus.ModbusConnection",
        return_value=MockModbusConnection(),
    ) as tm:
        BluettiModbusClient("10.0.0.1", 502, "balco260")

    assert tm.call_args.kwargs["message_spacing"] is None
