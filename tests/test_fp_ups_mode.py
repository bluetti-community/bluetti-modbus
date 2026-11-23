import pytest
from modbus_connection.mock import MockModbusConnection

from bluetti_modbus_lib import UpsWorkingMode
from bluetti_modbus_lib.devices import FP


@pytest.mark.asyncio
async def test_the_ups_mode_reads_as_the_apps_and_refuses_a_write():
    # 57020 read 1 in Customized UPS, 2 in PV Priority UPS, 4 in Standard UPS
    # and 5 in Time Control UPS on a real FridgePower (bluetti-registers#38);
    # a same-value write is refused there, so the field is read-only.
    for mode in UpsWorkingMode:
        unit = MockModbusConnection().for_unit(1)
        for address in range(50001, 57025):
            unit.holding[address] = 0
        unit.holding[57020] = mode.value
        device = FP(unit)

        await device.async_update_with_retry()
        assert device.values["d_working_mode"] == mode

    assert not FP(None).get_field("d_working_mode").writable
    assert [m.value for m in UpsWorkingMode] == [1, 2, 4, 5]
