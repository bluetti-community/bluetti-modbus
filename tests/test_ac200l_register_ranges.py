from bluetti_modbus_lib.devices.ac200l import AC200L


def test_every_field_is_its_own_read_block():
    # Same invariant as AC500's own test (test_ac500_register_ranges.py) -
    # for the same reason. Real hardware regression on *this* device during
    # development: widening register_ranges from three confirmed single
    # addresses (57001/57005/57009) to a single contiguous (57000, 57030)
    # block - to search for a Modbus equivalent of a BLE-only field - spanned
    # several confirmed-"Illegal Data Address" registers in between and took
    # the whole coordinator down (no partial-success fallback; the entry
    # failed to set up at all). AC200L has no official BLUETTI register
    # spec to derive confirmed gaps from (bluetti-registers#31), so - like
    # AC500 - every field stays its own block rather than bridging over any
    # address this device hasn't confirmed: import.py's ISOLATED_RANGE_DEVICES.
    device = AC200L(None)

    plan = device._build_plan()

    field_count = len(list(device.field_names()))
    block_count = len(plan.blocks["holding"])
    # pv_dc_count/pv_ac_count share one address (50267, high/low nibble),
    # same as AC500 - they collapse into a single block.
    assert block_count == field_count - 1
