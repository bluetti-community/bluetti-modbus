from typing import Any

from ..base_devices import BluettiDevice
from ..devices import SMeter


async def read_values(device: BluettiDevice) -> dict[str, Any]:
    """Poll a device once, with the library's retries, and return its values.

    For a caller that holds the device's unit rather than a
    BluettiModbusClient - a connection Home Assistant shares between
    integrations, for one. The unit connects on demand.

    An S Meter answers its measurements only on the first read of a
    connection and zeros on every read after it, so its link is dropped
    before the read (another read, a diagnostics dump say, may have left it
    open) and after it; the next request reconnects by itself.
    """
    unit = device.modbus_unit
    fresh_link = isinstance(device, SMeter)
    if fresh_link and unit.connected:
        await unit.disconnect()
    await device.async_update_with_retry()
    if fresh_link:
        await unit.disconnect()
    return dict(device.values)
