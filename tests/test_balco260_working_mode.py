import pytest
from modbus_connection.exceptions import IllegalDataAddressError, IllegalFunctionError
from modbus_connection.mock import MockModbusConnection

from bluetti_modbus_lib import BalcoWorkingMode
from bluetti_modbus_lib.devices.balco260 import Balco260
from bluetti_modbus_lib.exceptions import BluettiModbusConnectionError


def _unit(*refused):
    unit = MockModbusConnection().for_unit(1)
    for address in range(50001, 57021):
        unit.holding[address] = 0
    for address in refused:
        unit.fail_read(address, IllegalDataAddressError(2))
    return unit


def test_the_working_mode_is_read_alone():
    # 57020 sits within max_gap of 57017; a Balco 260 answers a block that
    # touches an unserved register with silence, so each run of declared
    # settings registers is its own read (import.py, ISOLATED_SETTINGS_DEVICES).
    blocks = Balco260(None)._build_plan().blocks["holding"]
    assert [b for b in blocks if b[0] >= 57001] == [
        (57001, 1),
        (57009, 2),
        (57016, 2),
        (57020, 1),
    ]


@pytest.mark.asyncio
async def test_the_working_mode_reads_and_writes_as_the_apps():
    # 57020 read 2 in Self-Consumption and 4 in Backup after the change in
    # the app on a real unit; 1, 2 and 4 each written and read back there,
    # the app following.
    for mode in BalcoWorkingMode:
        unit = _unit()
        unit.holding[57020] = mode.value
        device = Balco260(unit)

        await device.async_update_with_retry()
        assert device.values["d_working_mode"] == mode

        await device.write("d_working_mode", BalcoWorkingMode.Backup)
        assert unit.holding[57020] == 4


@pytest.mark.asyncio
async def test_a_firmware_without_the_working_mode_keeps_its_other_fields():
    # 57020 is not in BLUETTI's register list: a firmware that refuses it
    # must not cost the device its other readings.
    unit = _unit(57020)
    unit.holding[57016] = 20
    device = Balco260(unit)

    await device.async_update_with_retry()

    assert device.values["b_soc_low"] == 20
    assert "d_working_mode" not in device.field_names()
    assert device.values.get("d_working_mode") is None
    assert (57020, 1) not in device._build_plan().blocks["holding"]

    # Later polls read the rest without asking again.
    unit.holding[57016] = 25
    await device.async_update_with_retry()
    assert device.values["b_soc_low"] == 25


@pytest.mark.asyncio
async def test_another_refused_register_still_fails_the_read():
    # Only the optional field is given up: a refusal once it is gone is an
    # error like any other.
    unit = _unit(57016, 57020)
    device = Balco260(unit)

    with pytest.raises(BluettiModbusConnectionError):
        await device.async_update_with_retry()


@pytest.mark.asyncio
async def test_another_kind_of_refusal_drops_nothing():
    unit = _unit()
    unit.fail_read(57020, IllegalFunctionError(1))
    device = Balco260(unit)

    with pytest.raises(BluettiModbusConnectionError):
        await device.async_update()

    assert "d_working_mode" in device.field_names()
