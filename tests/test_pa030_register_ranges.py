import pytest
from modbus_connection.mock import MockModbusConnection

from bluetti_modbus_lib.devices.pa030 import PA030


def test_every_field_is_its_own_read_block():
    # Same invariant as AC500's, AC200L's and EP500P's own tests, for the
    # same reason: BLUETTI's register list does not cover this model, so no
    # block may bridge an address the device hasn't confirmed
    # (import.py's ISOLATED_RANGE_DEVICES). Real-hardware evidence on *this*
    # device: the AC500 profile's one-field blocks all read on an Apex 300,
    # 31 of them without an error (bluetti-registers#49).
    device = PA030(None)

    plan = device._build_plan()

    field_count = len(list(device.field_names()))
    block_count = len(plan.blocks["holding"])
    # pv_dc_count/pv_ac_count share one address (50267, high/low nibble),
    # same as AC500 - they collapse into a single block.
    assert block_count == field_count - 1


@pytest.mark.asyncio
async def test_a_unit_on_the_grid_decodes_as_its_app_shows():
    # Raw words read one register at a time from an Apex 300 charging from
    # the grid with a B500K attached (bluetti-registers#49). The app showed
    # 583 W from the grid, 18 % overall, 11 % on the unit's own pack and BMS
    # v1073.08.
    words = {
        50006: 0x0249,
        50008: 0xFDB7,
        50009: 0xFFFF,
        50234: 1,
        50235: 584,
        50236: 2316,
        50237: 25,
        50254: 1,
        50255: 3,
        50256: 0xFDBA,
        50257: 2311,
        50258: 25,
        51004: 18,
        51005: 100,
        51006: 1,
        51007: 912,
        51008: 912,
        51200: 0x5041,
        51201: 0x3033,
        51202: 0x0030,
        51206: 0x293A,
        51207: 0xFA10,
        51208: 0x0251,
        51210: 1,
        51211: 0xA32C,
        51212: 0x0001,
        51221: 12,
        51234: 16,
        51235: 4,
    }
    unit = MockModbusConnection().for_unit(1)
    for address in range(50001, 57020):
        unit.holding[address] = words.get(address, 0)
    device = PA030(unit)

    await device.async_update_with_retry()

    values = device.values
    assert values["g_i_p_total"] == 585
    assert values["d_inverter_total"] == -585
    assert values["d_inverter_1_p"] == -582
    assert values["g_1_i_v"] == 231.6
    assert values["b_soc_total"] == 18
    assert values["b_status"].name == "Charging"
    assert values["b_type"] == "AP300"
    assert values["b_serial"] == 2551110969658
    assert values["b_ver_1"] == "1073.08"
    assert values["b_soc"] == 12
