from bluetti_modbus_lib.devices.fp import FP


class GapPlannedFP(FP):
    # FP as the planner would batch it without a declared map: max_gap=5
    # merging, the same way Balco260/Balco500 are read.
    register_ranges = None


def _blocks(device):
    return device._build_plan().blocks["holding"]


def test_settings_registers_are_read_in_runs_of_adjacent_declared_registers():
    # Real hardware regression (bluetti-community/hassio-bluetti-modbus#127):
    # dc_o_switch at 57005 sits within max_gap of both 57001 and 57009, so
    # gap-based planning fused 57001-57010 into one read covering
    # 57002-57004 and 57006-57008 - registers the device does not serve -
    # and a FridgePower answered read_holding_registers(57001, 10) with
    # silence until the 10 s timeout, every time. import.py's
    # ISOLATED_SETTINGS_DEVICES declares the settings block as runs of
    # adjacent declared registers instead.
    assert (57001, 10) in _blocks(GapPlannedFP(None))

    settings = [block for block in _blocks(FP(None)) if block[0] >= 57001]

    assert settings == [(57001, 1), (57005, 1), (57009, 2), (57016, 2)]


def test_no_settings_block_covers_an_undeclared_register():
    device = FP(None)
    declared = {
        address
        for field in (device.get_field(n) for n in device.field_names())
        for address in range(field.address, field.address + field.count)
    }

    for start, count in _blocks(device):
        if start < 57001:
            continue
        for address in range(start, start + count):
            assert address in declared, f"block ({start}, {count}) reads {address}"


def test_the_data_area_keeps_its_gap_planned_blocks():
    # The declared map only changes the settings block: everything below
    # 57001 reads in exactly the blocks the planner built on its own, the
    # ones a real FridgePower answered in full (bluetti-registers#38).
    declared = [block for block in _blocks(FP(None)) if block[0] < 57001]
    planned = [block for block in _blocks(GapPlannedFP(None)) if block[0] < 57001]

    assert declared == planned
    assert all(count <= 20 for _, count in declared)
