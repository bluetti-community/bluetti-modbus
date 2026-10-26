import pytest
from modbus_connection.mock import MockModbusConnection

from bluetti_modbus_lib import (
    FAULT_DESCRIPTIONS,
    WARNING_DESCRIPTIONS,
    InverterFault,
    InverterWarning,
)
from bluetti_modbus_lib.devices import Balco260


def test_every_code_has_its_description_and_nothing_else():
    assert set(FAULT_DESCRIPTIONS) == {m.name for m in InverterFault if m}
    assert set(WARNING_DESCRIPTIONS) == {m.name for m in InverterWarning if m}


def test_codes_sit_at_the_bit_of_their_register():
    # E001 is bit 0 of 50027, E017 bit 0 of 50028, E065 bit 0 of 50031;
    # E113 is bit 0 of 50023, E129 bit 0 of 50024.
    assert InverterFault.E001 == 1
    assert InverterFault.E017 == 1 << 16
    assert InverterFault.E065 == 1 << 64
    assert InverterWarning.E113 == 1
    assert InverterWarning.E129 == 1 << 16


async def _read(words: dict[int, int]) -> dict:
    unit = MockModbusConnection().for_unit(1)
    for address in range(50001, 57020):
        unit.holding[address] = words.get(address, 0)
    device = Balco260(unit)
    await device.async_update_with_retry()
    return device.values


@pytest.mark.asyncio
async def test_a_set_bit_reads_as_its_code():
    # A Balco 260 that showed E012 in the BLUETTI app read 2048 in 50027
    # (bit 11): "Main relay failure". A Balco 500 read 10 in 50023 (bits 1
    # and 3): grid voltage and grid frequency too low.
    values = await _read({50027: 2048, 50023: 10, 50031: 1})

    fault = values["d_inverter_fault"]
    assert [m.name for m in fault] == ["E012", "E065"]
    assert FAULT_DESCRIPTIONS["E012"] == "Main relay failure"
    warning = values["d_inverter_warning"]
    assert [m.name for m in warning] == ["E114", "E116"]


@pytest.mark.asyncio
async def test_no_bit_set_reads_as_no_fault():
    values = await _read({})

    assert values["d_inverter_fault"] == InverterFault.NoFault
    assert values["d_inverter_warning"] == InverterWarning.NoWarning
    assert list(values["d_inverter_fault"]) == []
