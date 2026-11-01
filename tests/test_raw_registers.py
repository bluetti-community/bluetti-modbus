import struct
from unittest.mock import AsyncMock

import pytest
from modbus_connection.exceptions import (
    IllegalDataAddressError,
    ModbusProtocolError,
    ModbusTimeoutError,
)
from modbus_connection.mock import MockModbusConnection

from bluetti_modbus_lib import (
    EP2000,
    FP,
    Balco260,
    Balcotrans,
    RegisterWrite,
    battery_pack_component,
)
from bluetti_modbus_lib.exceptions import BluettiModbusConnectionError


def _device(cls=Balco260):
    mock_conn = MockModbusConnection()
    return cls(mock_conn.for_unit(1)), mock_conn.for_unit(1)


def _confirmation_at(address: int, value: int) -> ModbusProtocolError:
    from tmodbus.exceptions import InvalidResponseError

    err = ModbusProtocolError("write_register(...): Expected response to match request")
    err.__cause__ = InvalidResponseError(
        "Expected response to match request",
        response_bytes=struct.pack(">BHH", 6, address, value),
    )
    return err


def test_readable_ranges_join_field_spans_across_small_gaps():
    device, _ = _device()

    ranges = device.readable_ranges()

    assert (50001, 50031) in ranges
    assert (57016, 57017) in ranges
    # 57503 is not served by a Balco 260 and no field reads it.
    assert not any(low <= 57503 <= high for low, high in ranges)


def test_readable_ranges_keep_declared_ranges_apart():
    device, _ = _device(FP)

    ranges = device.readable_ranges()

    assert (50001, 50019) in ranges
    assert (50020, 50031) in ranges


def test_readable_ranges_follow_a_restricted_pack_component():
    pack = battery_pack_component(MockModbusConnection().for_unit(41))

    ranges = pack.readable_ranges()

    assert ranges
    assert all(low >= 51000 for low, _ in ranges)


@pytest.mark.asyncio
async def test_read_registers_inside_a_range_returns_raw_words():
    device, unit = _device()
    unit.holding[57016] = 15
    unit.holding[57017] = 95

    assert await device.read_registers(57016, 2) == [15, 95]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("address", "count"),
    [
        (57503, 1),  # nothing in the profile reads it
        (57016, 3),  # runs past the last field
        (50030, 5),  # crosses into a gap the poll never reads
    ],
)
async def test_read_registers_outside_the_profile_is_refused(address, count):
    device, unit = _device()
    unit.read_holding_registers = AsyncMock()  # type: ignore[method-assign]

    with pytest.raises(ValueError, match="outside the ranges"):
        await device.read_registers(address, count)
    unit.read_holding_registers.assert_not_called()


@pytest.mark.asyncio
async def test_read_registers_across_two_declared_ranges_is_refused():
    device, _ = _device(Balcotrans)

    with pytest.raises(ValueError, match="outside the ranges"):
        await device.read_registers(50001, 3)


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [0, 21])
async def test_read_registers_count_is_bounded_by_max_span(count):
    device, _ = _device()

    with pytest.raises(ValueError, match="between 1 and 20"):
        await device.read_registers(50001, count)


@pytest.mark.asyncio
async def test_read_registers_wraps_a_modbus_failure():
    device, unit = _device()
    unit.read_holding_registers = AsyncMock(  # type: ignore[method-assign]
        side_effect=ModbusTimeoutError("no reply")
    )

    with pytest.raises(BluettiModbusConnectionError, match="no reply") as excinfo:
        await device.read_registers(50001, 1)
    assert isinstance(excinfo.value.__cause__, ModbusTimeoutError)


@pytest.mark.asyncio
async def test_write_register_confirmed_plainly_and_read_back():
    device, unit = _device()

    result = await device.write_register(57017, 95, settle=0)

    assert result == RegisterWrite(
        address=57017, value=95, confirmed_at=57017, read_back=95
    )
    assert result.applied
    assert unit.holding[57017] == 95


@pytest.mark.asyncio
async def test_write_register_reports_the_internal_confirmation_address():
    device, unit = _device()
    unit.holding[57016] = 20
    unit.write_register = AsyncMock(  # type: ignore[method-assign]
        side_effect=_confirmation_at(2022, 20)
    )

    result = await device.write_register(57016, 20, settle=0)

    assert result.confirmed_at == 2022
    assert result.applied


@pytest.mark.asyncio
async def test_write_register_reads_back_until_the_device_serves_the_new_value():
    device, unit = _device()
    unit.write_register = AsyncMock()  # type: ignore[method-assign]
    unit.read_holding_registers = AsyncMock(  # type: ignore[method-assign]
        side_effect=[[15], [16]]
    )

    result = await device.write_register(57016, 16, settle=0)

    assert result.read_back == 16
    assert unit.read_holding_registers.await_count == 2


@pytest.mark.asyncio
async def test_write_register_reports_a_value_the_device_did_not_take():
    device, unit = _device()
    unit.write_register = AsyncMock()  # type: ignore[method-assign]
    unit.read_holding_registers = AsyncMock(  # type: ignore[method-assign]
        return_value=[0]
    )

    result = await device.write_register(57009, 1, settle=0)

    assert result.read_back == 0
    assert not result.applied
    assert unit.read_holding_registers.await_count == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "address",
    [
        57005,  # a setting register a Balco 260 has no field for
        50001,  # a field, but not a setting register
        57503,  # an EP2000-only register
    ],
)
async def test_write_register_refuses_a_register_outside_the_list(address):
    device, unit = _device()
    unit.write_register = AsyncMock()  # type: ignore[method-assign]

    with pytest.raises(ValueError, match="not a setting this device writes"):
        await device.write_register(address, 1, settle=0)
    unit.write_register.assert_not_called()


@pytest.mark.asyncio
async def test_write_register_refuses_the_ep2000s_own_settings():
    device, _ = _device(EP2000)

    with pytest.raises(ValueError, match="not a setting this device writes"):
        await device.write_register(57503, 1, settle=0)


@pytest.mark.asyncio
async def test_write_register_applies_the_fields_own_bound():
    # b_soc_low is 5-90 on a Balco 260, narrower than the register's 0-100.
    device, _ = _device()

    with pytest.raises(ValueError, match="out of range for 57016"):
        await device.write_register(57016, 95, settle=0)


@pytest.mark.asyncio
async def test_write_register_bounds_a_field_without_a_validator():
    # ac_o_switch is writable=True: the register's own 0/1 applies.
    device, _ = _device()

    with pytest.raises(ValueError, match=r"out of range for 57001 \(0-1\)"):
        await device.write_register(57001, 2, settle=0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("cls", "address"),
    [
        (FP, 57001),  # powers the fridge, never written on purpose
        (FP, 57017),  # refuses writes on a real FridgePower
        (EP2000, 57009),  # untested on hardware
    ],
)
async def test_write_register_refuses_a_field_the_profile_keeps_read_only(cls, address):
    device, unit = _device(cls)
    unit.write_register = AsyncMock()  # type: ignore[method-assign]

    with pytest.raises(ValueError, match="not a setting this device writes"):
        await device.write_register(address, 1, settle=0)
    unit.write_register.assert_not_called()


@pytest.mark.asyncio
async def test_write_register_wraps_a_refused_write():
    device, unit = _device()
    unit.write_register = AsyncMock(  # type: ignore[method-assign]
        side_effect=IllegalDataAddressError("illegal data address")
    )

    with pytest.raises(BluettiModbusConnectionError) as excinfo:
        await device.write_register(57010, 1, settle=0)
    assert isinstance(excinfo.value.__cause__, IllegalDataAddressError)


@pytest.mark.asyncio
async def test_write_register_raises_a_confirmation_with_another_value():
    device, unit = _device()
    unit.write_register = AsyncMock(  # type: ignore[method-assign]
        side_effect=_confirmation_at(2208, 0)
    )

    with pytest.raises(BluettiModbusConnectionError):
        await device.write_register(57010, 1, settle=0)


@pytest.mark.asyncio
async def test_write_register_raises_a_response_that_is_no_confirmation():
    device, unit = _device()
    unit.write_register = AsyncMock(  # type: ignore[method-assign]
        side_effect=ModbusProtocolError("garbled")
    )

    with pytest.raises(BluettiModbusConnectionError, match="garbled"):
        await device.write_register(57010, 1, settle=0)
