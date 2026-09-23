import logging
from dataclasses import dataclass
from typing import Any, Literal

from modbus_connection import ModbusConnection as _BaseModbusConnection
from modbus_connection import ModbusSerialParams, ModbusTcpParams, ModbusTlsParams

from ..devices import (
    AC200L,
    AC500,
    EP500P,
    EP2000,
    FP,
    Balco260,
    Balco500,
    SMeter,
    get_device,
)

LOGGER = logging.getLogger(__name__)

Backend = Literal["pymodbus", "tmodbus"]


@dataclass
class ClientReturnValue:
    name: str
    unit: str | None
    value: Any

    def __str__(self) -> str:
        return f"{self.name}: {self.value} {self.unit or ' '}"


class BluettiModbusClient:
    """A device behind a connection this client owns - for the CLI and standalone use.

    Three transports, one of which must be named:

    - **Modbus TCP** (the default): ``host`` and ``port``.
    - **Modbus/TLS**: the same, with ``tls=True`` and the certificate
      options below.
    - **Modbus RTU over a serial line**: ``serial_device`` instead of a
      host, with ``baudrate``, ``parity``, ``stopbits`` and ``bytesize``.
      The device is a port path (``/dev/ttyUSB0``, ``COM3``) or any URL
      pyserial understands - ``socket://192.168.1.50:8899`` for a
      serial-to-TCP gateway, an ESP32 or a hardware bridge, where the line
      settings live in the gateway rather than here.

    ``unit_id`` selects the Modbus address to talk to (1 by default). On a
    shared RS485 bus that is how the device is picked; over TCP the BLUETTI
    devices answer at 1 and nothing else should be addressed on the
    AC500/EP500Pro family (see this library's README).

    ``message_spacing`` (seconds) is the minimum gap the backend leaves
    between requests. A serial line needs the RTU inter-frame gap, which
    the backend derives from the line speed - state it here only to pace a
    device further apart than that.

    Modbus/TLS options, ``modbus_connection.ModbusTlsParams``':

    - ``verify``: ``True`` checks the server certificate against the system
      store, a path names the CA file or directory to check against,
      ``False`` skips verification altogether.
    - ``check_hostname``: whether the certificate must name the host; only
      meaningful with verification on.
    - ``client_cert`` / ``client_key`` / ``client_key_password``: the client
      certificate, for a device that requires one.

    BLUETTI's encrypted mode (developer.bluetti.com, "Modbus TCP") is
    exactly this: the device's web page takes a CA certificate, a server
    certificate and its key, and the client authenticates with a
    certificate signed by that CA, on the same port as plain mode (502 by
    default). Both backends handle the link. Example::

        client = BluettiModbusClient(
            "192.168.1.100",
            502,
            "ep500p",
            tls=True,
            verify="ca.pem",
            check_hostname=False,
            client_cert="client.pem",
            client_key="client.key",
        )
        values = await client.read()
        await client.aclose()

    And over a serial line, a USB adapter or a gateway::

        client = BluettiModbusClient(device_type="ep2000", serial_device="/dev/ttyUSB0")
        client = BluettiModbusClient(
            device_type="ep2000", serial_device="socket://192.168.1.50:8899"
        )
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        device_type: str | None = None,
        *,
        backend: Backend = "tmodbus",
        unit_id: int = 1,
        message_spacing: float | None = None,
        serial_device: str | None = None,
        baudrate: int = 9600,
        parity: Literal["N", "E", "O"] = "N",
        stopbits: Literal[1, 2] = 1,
        bytesize: Literal[7, 8] = 8,
        tls: bool = False,
        verify: bool | str = True,
        check_hostname: bool = True,
        client_cert: str | None = None,
        client_key: str | None = None,
        client_key_password: str | None = None,
    ) -> None:
        # tmodbus is the default since 0.4.0 - confirmed via persistent-
        # connection testing against real Balco260/S Meter hardware: it
        # correctly reports a corrupted/truncated reply as ModbusProtocolError,
        # where pymodbus reports the identical event as a generic timeout
        # (see #29 and CONTRIBUTING.md). backend="pymodbus" stays available
        # (pip install "bluetti-modbus[cli-pymodbus]") for anyone who needs
        # the previous default.
        #
        # Import chosen here, not at module level: each backend is an
        # optional extra (see pyproject.toml's cli/cli-pymodbus) - importing
        # both eagerly would require every caller to install both.
        #
        # Typed against modbus_connection's own backend-neutral base (its
        # public re-export of BaseModbusConnection) - the two branches below
        # each import an unrelated concrete class, even though the doc's own
        # contract is that both back this same base and are interchangeable
        # at the call sites below. Building the instance inside each branch,
        # rather than importing under one shared name first, is what lets
        # mypy see each concrete class as assignment-compatible with that
        # declared base instead of flagging the import itself.
        if device_type is None:
            raise ValueError("device_type is required")
        # host/port and serial_device name two different transports; each
        # call has to say which one, so neither a typo nor a half-filled
        # configuration can quietly open the wrong kind of link.
        if host is not None and serial_device is not None:
            raise ValueError("host and serial_device are mutually exclusive")

        self.params: ModbusTcpParams | ModbusTlsParams | ModbusSerialParams
        if serial_device is not None:
            if port is not None:
                raise ValueError("port belongs to a TCP connection, not serial_device")
            if tls:
                raise ValueError("tls is a TCP transport; it has no serial equivalent")
            # Line settings are ignored on a socket:// device - the gateway
            # owns them there - and used as given on a real port.
            self.params = ModbusSerialParams(
                device=serial_device,
                baudrate=baudrate,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                framer="rtu",
            )
        elif host is None:
            raise ValueError("either host (with port) or serial_device is required")
        elif tls:
            self.params = ModbusTlsParams(
                host=host,
                # BLUETTI's encrypted mode listens on the same port as the
                # plain one, so the default here is 502 rather than the 802
                # ModbusTlsParams itself defaults to.
                port=502 if port is None else port,
                verify=verify,
                check_hostname=check_hostname,
                client_cert=client_cert,
                client_key=client_key,
                client_key_password=client_key_password,
            )
        else:
            # A TLS option on a plain-TCP client would be silently ignored;
            # better to say so than to let verify=False look like it applied.
            if (
                verify is not True
                or not check_hostname
                or client_cert is not None
                or client_key is not None
                or client_key_password is not None
            ):
                raise ValueError("TLS options need tls=True")
            # ModbusTcpParams' own default, stated here so a caller that
            # gives only a host gets the Modbus TCP port rather than a
            # TypeError.
            self.params = ModbusTcpParams(host=host, port=502 if port is None else port)
        params = self.params
        # Passed only when asked for: at this package's declared floor
        # (modbus-connection 4.11.1) message_spacing is a plain float
        # defaulting to 0.0, and handing it None raises TypeError before a
        # connection is ever opened. Leaving the argument out gets each
        # version's own default, which is what "no pacing asked for" means.
        pacing = {} if message_spacing is None else {"message_spacing": message_spacing}
        self.conn: _BaseModbusConnection
        if backend == "tmodbus":
            from modbus_connection.tmodbus import ModbusConnection as _TConn

            self.conn = _TConn(params, timeout=10, **pacing)
        else:
            from modbus_connection.pymodbus import ModbusConnection as _PConn

            self.conn = _PConn(params, timeout=10, **pacing)
        device = get_device(device_type, self.conn.for_unit(unit_id))
        if device is None:
            raise ValueError(f"Unsupported device type: {device_type!r}")
        self.device: (
            AC200L | AC500 | FP | Balco260 | Balco500 | EP2000 | EP500P | SMeter
        ) = device

    async def aclose(self) -> None:
        """Close the connection permanently. Call when actually done with this client."""
        await self.conn.close()

    async def read(self) -> list[ClientReturnValue]:
        # Connection is intentionally left open between calls - modbus_connection
        # keeps it usable across reads, reconnecting on demand if it drops. A
        # fresh connection on every read is exactly the pattern that has caused
        # this device's Modbus TCP stack to become unresponsive under load in
        # the past. Call aclose() when actually done with this client.
        await self.conn.connect()

        LOGGER.debug("Reading device data")
        await self.device.async_update_with_retry()

        results = []
        for name, value in self.device.values.items():
            field = self.device.get_field(name)
            assert field is not None, (
                f"{name} is in values, so it must be a registered field"
            )
            results.append(ClientReturnValue(name=name, unit=field.unit, value=value))
        return results
