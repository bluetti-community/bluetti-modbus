"""Tests for script/write_probe.py's register and value checks."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture
def write_probe() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "write_probe", Path(__file__).parents[1] / "script" / "write_probe.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASE = ["--host", "192.0.2.1", "--device", "pa030"]


@pytest.mark.parametrize("value", [0, 1, 2, 4])
def test_the_charging_mode_takes_each_known_mode(write_probe, value):
    args = write_probe.parse_args([*BASE, "--register", "57023", "--value", str(value)])
    assert (args.register, args.value) == (57023, value)
    assert args.output.startswith("write-pa030-57023-")


@pytest.mark.parametrize("value", [3, 5, -1])
def test_the_charging_mode_refuses_a_value_no_unit_has_shown(write_probe, value):
    with pytest.raises(SystemExit):
        write_probe.parse_args([*BASE, "--register", "57023", "--value", str(value)])


@pytest.mark.parametrize("register", [57011, 57012])
def test_a_same_value_only_register_takes_no_value(write_probe, register, capsys):
    args = write_probe.parse_args([*BASE, "--register", str(register)])
    assert (args.register, args.value) == (register, None)
    with pytest.raises(SystemExit):
        write_probe.parse_args([*BASE, "--register", str(register), "--value", "24"])
    assert "same-value write only" in capsys.readouterr().err


def test_a_same_value_write_needs_no_value(write_probe):
    args = write_probe.parse_args([*BASE, "--register", "57023"])
    assert args.value is None


def test_a_threshold_keeps_its_percent_range(write_probe):
    assert (
        write_probe.parse_args([*BASE, "--register", "57017", "--value", "100"]).value
        == 100
    )
    with pytest.raises(SystemExit):
        write_probe.parse_args([*BASE, "--register", "57017", "--value", "101"])


def test_an_unlisted_register_is_refused(write_probe):
    with pytest.raises(SystemExit):
        write_probe.parse_args([*BASE, "--register", "57024"])


def test_the_ac_output_still_needs_its_flag(write_probe):
    with pytest.raises(SystemExit):
        write_probe.parse_args([*BASE, "--register", "57001"])
    args = write_probe.parse_args([*BASE, "--register", "57001", "--allow-ac-output"])
    assert args.register == 57001
