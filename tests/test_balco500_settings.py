import pytest
from modbus_connection.mock import MockModbusConnection

from bluetti_modbus_lib.devices.balco500 import Balco500


def _settings_blocks(device):
    return [b for b in device._build_plan().blocks["holding"] if b[0] >= 57001]


def test_settings_registers_are_read_in_runs_of_adjacent_declared_registers():
    # 57020 sits within max_gap of 57017; the gap planner would read
    # 57016-57020 in one block, and a Balco-family device answers a block
    # touching an unserved register with silence. import.py's
    # ISOLATED_SETTINGS_DEVICES keeps each run of declared registers apart.
    assert _settings_blocks(Balco500(None)) == [
        (57001, 1),
        (57009, 2),
        (57016, 2),
        (57020, 1),
    ]


@pytest.mark.asyncio
async def test_the_working_mode_reads_and_writes_as_the_apps():
    # 57020 read 1 in Custom, 2 in Self-Consumption and 4 in Backup on a real
    # unit, the Apex 300's numbering; Custom and Backup each written and read
    # back there, the app following.
    from bluetti_modbus_lib import BalcoWorkingMode

    for raw, mode in ((m.value, m) for m in BalcoWorkingMode):
        unit = MockModbusConnection().for_unit(1)
        for address in range(50001, 57021):
            unit.holding[address] = 0
        unit.holding[57020] = raw
        device = Balco500(unit)

        await device.async_update_with_retry()
        assert device.values["d_working_mode"] == mode

        await device.write("d_working_mode", BalcoWorkingMode.Backup)
        assert unit.holding[57020] == 4

    assert [m.name for m in BalcoWorkingMode] == ["Custom", "SelfConsumption", "Backup"]
