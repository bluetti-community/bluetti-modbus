from bluetti_modbus_lib.devices.ep500p import EP500P


def test_every_field_is_its_own_read_block():
    # Same invariant as AC500's and AC200L's own tests, for the same reason:
    # no official register list to derive confirmed gaps from, so no block
    # may bridge an address the device hasn't confirmed (import.py's
    # ISOLATED_RANGE_DEVICES). Real-hardware evidence on *this* device: the
    # EP2000 profile's 50-register batch got no reply at all from an
    # EP500P, while the AC500 profile's one-field blocks all read
    # (bluetti-registers#35).
    device = EP500P(None)

    plan = device._build_plan()

    field_count = len(list(device.field_names()))
    block_count = len(plan.blocks["holding"])
    # pv_dc_count/pv_ac_count share one address (50267, high/low nibble),
    # same as AC500 - they collapse into a single block.
    assert block_count == field_count - 1
