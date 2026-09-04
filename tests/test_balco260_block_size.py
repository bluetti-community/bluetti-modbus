from bluetti_modbus_lib.devices.balco260 import Balco260


def test_max_span_is_narrower_than_the_default():
    device = Balco260(None)

    assert device.max_span == 20
    assert device.max_gap == 5


def test_no_single_block_spans_more_than_max_span_registers():
    # Real hardware regression: read_holding_registers(50001, 31) - the
    # naturally-batched block covering d_num_inverters through
    # d_inverter_fault - failed twice months apart on a real Balco260, once
    # as a cancelled request and once as a malformed response (see this
    # branch's PR description for the tracebacks). BluettiDevice's default
    # max_span=50 let it grow that large; Balco260's own override should
    # keep every block at or under 20 registers.
    device = Balco260(None)

    plan = device._build_plan()

    for space, blocks in plan.blocks.items():
        for start, count in blocks:
            assert count <= 20, f"{space} block ({start}, {count}) exceeds max_span"


def test_the_previously_failing_block_is_now_split_in_two():
    device = Balco260(None)

    plan = device._build_plan()
    blocks = plan.blocks["holding"]

    # No block covers both d_num_inverters (50001) and d_inverter_fault's
    # last register (50031) any more.
    assert not any(
        start <= 50001 and start + count - 1 >= 50031 for start, count in blocks
    )
    # d_num_inverters (50001) is still read, just in a smaller block.
    assert any(start <= 50001 <= start + count - 1 for start, count in blocks)
    # d_inverter_fault (50027-50031) is still read too.
    assert any(start <= 50031 <= start + count - 1 for start, count in blocks)


def test_ep2000_and_smeter_keep_the_default_max_span():
    # This override is Balco260-specific - EP2000 is still unconfirmed
    # against real hardware (no evidence it has the same issue), and
    # S Meter's own address space doesn't have blocks this large anyway.
    from bluetti_modbus_lib.devices.ep2000 import EP2000
    from bluetti_modbus_lib.devices.smeter import SMeter

    assert EP2000(None).max_span == 50
    assert SMeter(None).max_span == 50
