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
