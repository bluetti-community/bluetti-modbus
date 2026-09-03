import pytest
from modbus_connection.mock import MockModbusConnection

from bluetti_modbus_lib.devices import Balco260
from bluetti_modbus_lib.devices.battery_pack import (
    MAX_BATTERY_PACKS,
    PACK_INFO_FIELDS,
    battery_pack,
)


def test_max_battery_packs_is_five():
    # BLUETTI confirmed by email (2026-09-03) that a single Balco260
    # supports at most 5 BC200 packs.
    assert MAX_BATTERY_PACKS == 5


def test_pack_info_fields_are_within_the_confirmed_block():
    # "Each Pack Base Information" - bluetti-official's Cassandra Protocol
    # register list, addresses 51200-51249.
    device = Balco260(None)
    assert len(PACK_INFO_FIELDS) > 0
    for name in PACK_INFO_FIELDS:
        field = device.get_field(name)
        assert field is not None
        assert 51200 <= field.address <= 51249


def test_pack_info_fields_includes_soc_and_soh():
    # The two fields bluetti-community/bluetti-modbus#8 already confirmed
    # are read per-pack via slave address - the starting point for this
    # whole block turning out to work the same way.
    assert "b_soc" in PACK_INFO_FIELDS
    assert "b_soh" in PACK_INFO_FIELDS


def test_battery_pack_restricts_to_pack_info_fields():
    conn = MockModbusConnection()

    pack = battery_pack(conn, 2)

    assert set(pack.field_names()) == PACK_INFO_FIELDS
    # d_num_inverters (50001) is outside the pack-info block - not part of
    # this restricted device at all.
    assert pack.get_field("d_num_inverters") is None


@pytest.mark.asyncio
async def test_battery_pack_reads_from_its_own_slave_address():
    conn = MockModbusConnection()
    conn.for_unit(1).holding[51221] = 50  # b_soc, main unit / pack 1
    conn.for_unit(2).holding[51221] = 85  # b_soc, pack 2's own slave address

    pack2 = battery_pack(conn, 2)
    await pack2.async_update_with_retry()

    assert pack2.values["b_soc"] == 85


@pytest.mark.asyncio
async def test_battery_pack_2_and_3_are_independent():
    conn = MockModbusConnection()
    conn.for_unit(2).holding[51221] = 85
    conn.for_unit(3).holding[51221] = 60

    pack2 = battery_pack(conn, 2)
    pack3 = battery_pack(conn, 3)
    await pack2.async_update_with_retry()
    await pack3.async_update_with_retry()

    assert pack2.values["b_soc"] == 85
    assert pack3.values["b_soc"] == 60
