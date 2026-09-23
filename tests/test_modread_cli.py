"""Tests for the bluetti-modread CLI's option parsing."""

import asyncio

import pytest
from modbus_connection import ModbusSerialParams, ModbusTcpParams

from bluetti_modbus_lib.scripts.bluetti_modread import parse_args, start


def test_host_and_port_parse_as_a_tcp_connection():
    args = parse_args(["-c", "10.0.0.1", "-p", "502", "-t", "balco260"])

    assert (args.host, args.port, args.serial) == ("10.0.0.1", 502, None)
    assert args.unit == 1


def test_serial_parses_with_its_line_settings():
    args = parse_args(
        [
            "--serial",
            "/dev/ttyUSB0",
            "--baud",
            "19200",
            "--parity",
            "E",
            "--stopbits",
            "2",
            "-t",
            "ep2000",
        ]
    )

    assert args.serial == "/dev/ttyUSB0"
    assert (args.baud, args.parity, args.stopbits) == (19200, "E", 2)
    assert args.host is None


def test_serial_line_settings_have_defaults():
    args = parse_args(["--serial", "/dev/ttyUSB0", "-t", "ep2000"])

    assert (args.baud, args.parity, args.stopbits) == (9600, "N", 1)


def test_a_gateway_url_is_accepted_as_the_serial_device():
    args = parse_args(["-s", "socket://192.168.1.50:8899", "-t", "ep2000"])

    assert args.serial == "socket://192.168.1.50:8899"


def test_the_unit_id_can_be_chosen():
    args = parse_args(["-s", "/dev/ttyUSB0", "-t", "ep2000", "--unit", "7"])

    assert args.unit == 7


def test_host_and_serial_cannot_both_be_given():
    with pytest.raises(SystemExit):
        parse_args(["-c", "10.0.0.1", "-s", "/dev/ttyUSB0", "-t", "ep2000"])


def test_a_port_next_to_a_serial_device_is_refused():
    with pytest.raises(SystemExit):
        parse_args(["-s", "/dev/ttyUSB0", "-p", "502", "-t", "ep2000"])


def test_an_unknown_parity_is_refused():
    with pytest.raises(SystemExit):
        parse_args(["-s", "/dev/ttyUSB0", "--parity", "X", "-t", "ep2000"])


def test_start_builds_serial_params_from_the_serial_options(monkeypatch):
    captured: dict[str, object] = {}

    async def _fake_read(params, type, backend, unit=1) -> None:
        captured.update(params=params, type=type, backend=backend, unit=unit)

    monkeypatch.setattr(
        "sys.argv",
        [
            "bluetti-modread",
            "-s",
            "socket://192.168.1.50:8899",
            "-t",
            "ep2000",
            "--baud",
            "19200",
            "-u",
            "3",
        ],
    )
    monkeypatch.setattr(
        "bluetti_modbus_lib.scripts.bluetti_modread.async_read", _fake_read
    )
    monkeypatch.setattr(
        "bluetti_modbus_lib.scripts.bluetti_modread.asyncio.run", asyncio.run
    )

    start()

    params = captured["params"]
    assert isinstance(params, ModbusSerialParams)
    assert params.device == "socket://192.168.1.50:8899"
    assert params.baudrate == 19200
    assert captured["unit"] == 3


def test_start_builds_tcp_params_from_host_and_port(monkeypatch):
    captured: dict[str, object] = {}

    async def _fake_read(params, type, backend, unit=1) -> None:
        captured.update(params=params, type=type, backend=backend, unit=unit)

    monkeypatch.setattr(
        "sys.argv", ["bluetti-modread", "-c", "10.0.0.1", "-p", "502", "-t", "balco260"]
    )
    monkeypatch.setattr(
        "bluetti_modbus_lib.scripts.bluetti_modread.async_read", _fake_read
    )
    monkeypatch.setattr(
        "bluetti_modbus_lib.scripts.bluetti_modread.asyncio.run", asyncio.run
    )

    start()

    params = captured["params"]
    assert isinstance(params, ModbusTcpParams)
    assert (params.host, params.port) == ("10.0.0.1", 502)


def test_start_prints_the_help_when_no_transport_is_given(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["bluetti-modread", "-t", "balco260"])

    start()

    assert "usage:" in capsys.readouterr().out
