"""Exceptions for the bluetti-modbus client."""

from modbus_connection.exceptions import ModbusError


class BluettiModbusError(Exception):
    """Generic bluetti-modbus exception."""


class BluettiModbusConnectionError(BluettiModbusError, ModbusError):
    """Bluetti Modbus communication error.

    Raised when reading from a device over Modbus fails, wrapping the
    backend-neutral error from ``modbus-connection`` (or a timeout of the
    whole read sequence - see BluettiDevice.async_update_with_retry's own
    docstring). Also a ModbusError, so code already catching that directly
    (e.g. the bluetti_modbus Home Assistant integration) keeps working
    unchanged - this just gives a library-specific type to a caller that
    doesn't want to depend on modbus_connection's own exception hierarchy.
    """
