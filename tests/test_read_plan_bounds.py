"""Read-plan efficiency regression tests for the devices Balco260/AC500's own
test files don't already cover (test_balco260_block_size.py,
test_ac500_register_ranges.py) - EP2000, S Meter, and Balco 500 have never
had their actual block plan checked against their own max_span before,
only confirmed (in test_balco260_block_size.py's own
test_ep2000_and_smeter_keep_the_default_max_span) to still declare the
default value. A future bluetti-registers field addition could silently
push a block past it - as already happened once for real on Balco260 (see
test_balco260_block_size.py) - with nothing here to catch it.
"""

from bluetti_modbus_lib.devices import EP2000, Balco500, SMeter


def test_no_ep2000_block_exceeds_its_own_max_span():
    device = EP2000(None)

    plan = device._build_plan()

    for space, blocks in plan.blocks.items():
        for start, count in blocks:
            assert count <= device.max_span, (
                f"{space} block ({start}, {count}) exceeds max_span={device.max_span}"
            )


def test_no_smeter_block_exceeds_its_own_max_span():
    device = SMeter(None)

    plan = device._build_plan()

    for space, blocks in plan.blocks.items():
        for start, count in blocks:
            assert count <= device.max_span, (
                f"{space} block ({start}, {count}) exceeds max_span={device.max_span}"
            )


def test_no_balco500_block_exceeds_its_own_max_span():
    device = Balco500(None)

    plan = device._build_plan()

    for space, blocks in plan.blocks.items():
        for start, count in blocks:
            assert count <= device.max_span, (
                f"{space} block ({start}, {count}) exceeds max_span={device.max_span}"
            )
