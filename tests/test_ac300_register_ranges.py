import pytest
from modbus_connection.mock import MockModbusConnection

from bluetti_modbus_lib.devices.ac300 import AC300


def test_every_field_is_its_own_read_block():
    # Same invariant as the other AC-family profiles: BLUETTI's register list
    # does not cover this model, so no block may bridge an address the unit
    # has not confirmed (import.py's ISOLATED_RANGE_DEVICES).
    device = AC300(None)

    plan = device._build_plan()

    field_count = len(list(device.field_names()))
    block_count = len(plan.blocks["holding"])
    assert block_count == field_count


def test_only_the_dc_output_switch_is_writable():
    # The one write confirmed in the app on a real unit (bluetti-registers#47).
    # The SOC limits refuse a write there.
    device = AC300(None)

    writable = {n for n in device.field_names() if device.get_field(n).writable}

    assert writable == {"dc_o_switch"}


@pytest.mark.asyncio
async def test_raw_words_decode_as_read_on_the_unit():
    # From the owner's reads (bluetti-registers#47): grid frequency 50.02 Hz
    # (0.01 Hz), PV yield 546.6 kWh (0.1 kWh, one register), ARM 4037.07 and
    # IoT 9041.17 (two-part versions, low word first).
    conn = MockModbusConnection()
    unit = conn.for_unit(1)
    unit.holding[50214] = 5002
    unit.holding[50229] = 5466
    unit.holding[50210] = 403707 & 0xFFFF
    unit.holding[50211] = 403707 >> 16
    unit.holding[53011] = 0xCBB5
    unit.holding[53012] = 0x000D
    device = AC300(unit)

    await device.async_update_with_retry()

    assert device.values["g_i_f"] == pytest.approx(50.02)
    assert device.values["pv_i_e_local"] == pytest.approx(546.6)
    assert device.values["d_ver_arm"] == "4037.07"
    assert device.values["d_iot_ver"] == "9041.17"


@pytest.mark.asyncio
async def test_pv_input_1_power_reads_from_50219():
    # 50219, the AC500's pv_i_p_local, reads the app's DC Input Power 1 on a
    # real AC300, also checked on the device display (bluetti-registers#47):
    # 131 W while the total read 375 W. No register carries the second input.
    unit = MockModbusConnection().for_unit(1)
    unit.holding[50004] = 375
    unit.holding[50219] = 131
    device = AC300(unit)

    await device.async_update_with_retry()

    assert device.values["pv_1_i_p"] == 131
    assert device.values["pv_i_p_total"] == 375
    assert "pv_2_i_p" not in device.field_names()
    assert "pv_i_p_local" not in device.field_names()
