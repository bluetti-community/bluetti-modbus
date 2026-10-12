import pytest
from modbus_connection.mock import MockModbusConnection

from bluetti_modbus_lib.devices.ac240 import AC240


def test_every_field_is_its_own_read_block():
    # Same invariant as the other AC-family profiles: BLUETTI's register list
    # does not cover this model, so no block may bridge an address the unit
    # has not confirmed (import.py's ISOLATED_RANGE_DEVICES). The AC240 was
    # scanned one register at a time (bluetti-registers#65).
    device = AC240(None)

    plan = device._build_plan()

    field_count = len(list(device.field_names()))
    block_count = len(plan.blocks["holding"])
    # pv_dc_count/pv_ac_count share one address (50267), as on the AC500.
    assert block_count == field_count - 1


def test_the_confirmed_switches_are_writable_and_the_soc_limits_are_not():
    device = AC240(None)

    writable = {n for n in device.field_names() if device.get_field(n).writable}

    assert writable == {
        "ac_o_switch",
        "dc_o_switch",
        "g_i_switch",
        "ac_power_lifting_switch",
        "ac_eco_switch",
    }


@pytest.mark.asyncio
async def test_raw_words_decode_as_measured_on_the_unit():
    # Values from the owner's scan (bluetti-registers#65): grid voltage raw
    # 236 on a 230 V grid (whole volts), pack voltage raw 5290 = 52.9 V
    # (0.01 V), and the IoT version 53011 "cbb5 000d" = 9041.17.
    conn = MockModbusConnection()
    unit = conn.for_unit(1)
    unit.holding[50236] = 236
    unit.holding[51219] = 5290
    unit.holding[53011] = 0xCBB5
    unit.holding[53012] = 0x000D
    device = AC240(unit)

    await device.async_update_with_retry()

    assert device.values["g_1_i_v"] == 236
    assert device.values["b_v"] == pytest.approx(52.9)
    assert device.values["d_iot_ver"] == "9041.17"
    assert device.get_field("g_1_i_p").unit == "VA"
