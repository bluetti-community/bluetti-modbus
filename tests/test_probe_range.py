"""Tests for script/probe_unexplored_registers.py's --range selection.

A fresh module per test: the candidate synthesisers append to the module's
own CANDIDATES list, the way the probe needs them to.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture
def probe() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "probe_unexplored_registers",
        Path(__file__).parents[1] / "script" / "probe_unexplored_registers.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_a_span_becomes_one_single_register_candidate_per_address(probe):
    candidates = probe.range_candidates("50001-50004")

    assert [(name, address, count) for name, address, count, *_ in candidates] == [
        ("addr_50001", 50001, 1),
        ("addr_50002", 50002, 1),
        ("addr_50003", 50003, 1),
        ("addr_50004", 50004, 1),
    ]


def test_several_spans_and_a_bare_address(probe):
    addresses = [
        address for _, address, *_ in probe.range_candidates("50001-50002,57503")
    ]

    assert addresses == [50001, 50002, 57503]


def test_the_range_candidates_join_the_candidate_list(probe):
    # _matches() resolves --only/--skip against CANDIDATES, so a synthesised
    # address has to be in there like any other.
    probe.range_candidates("50001")

    assert any(c[1] == 50001 and c[5] == "range" for c in probe.CANDIDATES)


def test_a_span_that_ends_below_its_start_is_refused(probe):
    with pytest.raises(ValueError, match="below the start"):
        probe.range_candidates("50100-50001")


def test_a_span_wider_than_the_cap_is_refused(probe):
    with pytest.raises(ValueError, match="the cap is"):
        probe.range_candidates(f"1-{probe.MAX_RANGE_ADDRESSES + 1}")


def test_range_alone_probes_only_the_range(probe):
    args = probe.parse_args(
        ["--device", "transfer-hub", "--range", "50001-50003", "--list"]
    )

    candidates = probe.select_candidates(args)

    assert {c[5] for c in candidates} == {"range"}
    assert len(candidates) == 3


def test_a_bad_span_prints_one_line_and_exits(probe, capsys):
    code = probe.main(["--device", "transfer-hub", "--range", "50100-50001"])

    assert code == 2
    assert "below the start" in capsys.readouterr().out


def test_an_address_with_a_count_is_one_candidate_of_that_width(probe):
    # A 32-bit value or a string is one field, read one register per
    # request all the same - see _read_words().
    candidates = probe.range_candidates("50200:6")

    assert [(name, address, count) for name, address, count, *_ in candidates] == [
        ("addr_50200x6", 50200, 6)
    ]


def test_widths_and_spans_mix_in_one_spec(probe):
    candidates = probe.range_candidates("50008:2,51001-51002")

    assert [(address, count) for _, address, count, *_ in candidates] == [
        (50008, 2),
        (51001, 1),
        (51002, 1),
    ]


def test_a_count_below_one_is_refused(probe):
    with pytest.raises(ValueError, match="count must be positive"):
        probe.range_candidates("50200:0")


def test_the_cap_counts_registers_not_candidates(probe):
    with pytest.raises(ValueError, match="the cap is"):
        probe.range_candidates(f"50200:{probe.MAX_RANGE_ADDRESSES + 1}")
