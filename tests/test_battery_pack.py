import pytest
from modbus_connection.mock import MockModbusConnection

from bluetti_modbus_lib.devices import Balco260
from bluetti_modbus_lib.devices.battery_pack import (
    AGGREGATE_SLAVE_ID,
    AGGREGATE_SUMMARY_FIELDS,
    EXPANSION_PACK_FIRST_SLAVE_ID,
    MAX_BATTERY_PACKS,
    PACK_INFO_FIELDS,
    aggregate_pack_summary,
    aggregate_pack_summary_component,
    battery_pack,
    battery_pack_component,
    pack_is_reporting,
    pack_slave_id,
)
from bluetti_modbus_lib.enums.pack_charging_status import PackChargingStatus


def test_max_battery_packs_is_five():
    # BLUETTI confirmed by email (2026-09-03) that a single Balco260
    # supports at most 5 BC260 packs.
    assert MAX_BATTERY_PACKS == 5


def test_expansion_packs_start_at_slave_41():
    # BLUETTI's answer by email (2026-09-17): "for individual battery pack
    # data, the unit ID starts from 41".
    assert EXPANSION_PACK_FIRST_SLAVE_ID == 41


def test_pack_slave_id_counts_from_the_first_expansion_pack():
    # Pack 1 is the built-in pack at the device's own address; pack 2 is
    # the first expansion pack, at 41, and they follow on from there.
    assert pack_slave_id(2) == 41
    assert pack_slave_id(3) == 42
    assert pack_slave_id(MAX_BATTERY_PACKS + 1) == 41 + MAX_BATTERY_PACKS - 1


@pytest.mark.parametrize("pack_num", [0, 1, MAX_BATTERY_PACKS + 2])
def test_pack_slave_id_rejects_packs_that_have_no_expansion_slot(pack_num):
    with pytest.raises(ValueError, match="pack_num must be"):
        pack_slave_id(pack_num)


def test_aggregate_slave_id_is_250():
    # BLUETTI confirmed by email (2026-08-29) that aggregate "Total"
    # fields are read at slave address 250 (0xFA) - 0xFA == 250.
    assert AGGREGATE_SLAVE_ID == 250


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
    # The two fields BLUETTI confirmed by email are read per-pack via slave
    # address - the starting point for this whole block turning out to work
    # the same way in theory, though real-hardware testing later found that
    # doesn't hold beyond these two (see MAX_BATTERY_PACKS' own comment).
    assert "b_soc" in PACK_INFO_FIELDS
    assert "b_soh" in PACK_INFO_FIELDS


def test_aggregate_summary_fields_are_within_the_confirmed_block():
    # "Pack Summary Information" - addresses 51001-51008.
    device = Balco260(None)
    assert len(AGGREGATE_SUMMARY_FIELDS) > 0
    for name in AGGREGATE_SUMMARY_FIELDS:
        field = device.get_field(name)
        assert field is not None
        assert 51001 <= field.address <= 51008


def test_aggregate_summary_fields_includes_num_battery_packs_and_totals():
    assert "d_num_battery_packs" in AGGREGATE_SUMMARY_FIELDS
    assert "b_soc_total" in AGGREGATE_SUMMARY_FIELDS
    assert "b_soh_total" in AGGREGATE_SUMMARY_FIELDS
    assert "b_c_total" in AGGREGATE_SUMMARY_FIELDS


def test_battery_pack_restricts_to_pack_info_fields():
    conn = MockModbusConnection()

    pack = battery_pack(conn, pack_slave_id(2))

    assert set(pack.field_names()) == PACK_INFO_FIELDS
    # d_num_inverters (50001) is outside the pack-info block - not part of
    # this restricted device at all.
    assert pack.get_field("d_num_inverters") is None


@pytest.mark.asyncio
async def test_battery_pack_reads_from_its_own_slave_address():
    conn = MockModbusConnection()
    conn.for_unit(1).holding[51221] = 50  # b_soc, main unit / pack 1
    conn.for_unit(41).holding[51221] = 85  # b_soc, pack 2's own slave address

    pack2 = battery_pack(conn, pack_slave_id(2))
    await pack2.async_update_with_retry()

    assert pack2.values["b_soc"] == 85


@pytest.mark.asyncio
async def test_battery_pack_2_and_3_are_independent():
    conn = MockModbusConnection()
    conn.for_unit(41).holding[51221] = 85
    conn.for_unit(42).holding[51221] = 60

    pack2 = battery_pack(conn, pack_slave_id(2))
    pack3 = battery_pack(conn, pack_slave_id(3))
    await pack2.async_update_with_retry()
    await pack3.async_update_with_retry()

    assert pack2.values["b_soc"] == 85
    assert pack3.values["b_soc"] == 60


def test_aggregate_pack_summary_restricts_to_aggregate_fields():
    conn = MockModbusConnection()

    summary = aggregate_pack_summary(conn)

    assert set(summary.field_names()) == AGGREGATE_SUMMARY_FIELDS
    # b_soc (51221) is a per-pack field, not part of the aggregate block.
    assert summary.get_field("b_soc") is None


@pytest.mark.asyncio
async def test_aggregate_pack_summary_reads_from_slave_250():
    # Real-hardware regression: a Balco260 with 3 confirmed BC260 packs
    # read d_num_battery_packs as 0 at its own slave address (1), and as 4
    # (1 main + 3 packs, matching the BLUETTI app) at slave 250.
    conn = MockModbusConnection()
    conn.for_unit(1).holding[51001] = 0
    conn.for_unit(250).holding[51001] = 4

    summary = aggregate_pack_summary(conn)
    await summary.async_update_with_retry()

    assert summary.values["d_num_battery_packs"] == 4


@pytest.mark.asyncio
async def test_battery_pack_component_reads_the_unit_it_is_given():
    # A caller handed units, not a connection (Home Assistant's shared
    # connections), opens the pack's slave address itself.
    conn = MockModbusConnection()
    conn.for_unit(41).holding[51221] = 85

    pack = battery_pack_component(conn.for_unit(pack_slave_id(2)))
    await pack.async_update_with_retry()

    assert set(pack.field_names()) == PACK_INFO_FIELDS
    assert pack.values["b_soc"] == 85


@pytest.mark.asyncio
async def test_aggregate_pack_summary_component_reads_the_unit_it_is_given():
    conn = MockModbusConnection()
    conn.for_unit(AGGREGATE_SLAVE_ID).holding[51001] = 4

    summary = aggregate_pack_summary_component(conn.for_unit(AGGREGATE_SLAVE_ID))
    await summary.async_update_with_retry()

    assert set(summary.field_names()) == AGGREGATE_SUMMARY_FIELDS
    assert summary.values["d_num_battery_packs"] == 4


@pytest.mark.asyncio
async def test_aggregate_pack_summary_decodes_a_real_four_pack_read():
    # 51001-51008 as a Balco260 with three BC260 packs answered them at
    # the aggregate slave, idle at full charge.
    conn = MockModbusConnection()
    unit = conn.for_unit(AGGREGATE_SLAVE_ID)
    for address, raw in zip(
        range(51001, 51009), [4, 265, 8, 100, 98, 0, 0, 45600], strict=True
    ):
        unit.holding[address] = raw

    summary = aggregate_pack_summary_component(unit)
    await summary.async_update_with_retry()

    assert summary.values == {
        "d_num_battery_packs": 4,
        "b_v_total": pytest.approx(26.5),
        "b_c_total": pytest.approx(0.8),
        "b_soc_total": 100,
        "b_soh_total": 98,
        "b_status": PackChargingStatus.Idle,
        "b_time_to_full_total": 0,
        "b_time_to_empty_total": 45600,
    }


def test_a_reporting_pack_has_its_type_string_and_a_voltage():
    # Slot 42 of a Balco260 with three BC260 packs (2026-09-18, #55).
    assert pack_is_reporting(
        {"b_type": "BC260", "b_serial": 2610110280905, "b_v": 27.2}
    )


def test_a_silent_pack_answers_its_serial_number_and_zeros():
    # Slot 41 of that same unit: the inverter knows the pack, the pack
    # reports nothing - b_c's raw 0 decodes to None.
    values = {
        "b_type": "",
        "b_serial": 2615112301352,
        "b_v": 0.0,
        "b_c": None,
        "b_soc": 0,
    }
    assert not pack_is_reporting(values)


def test_an_empty_slot_is_not_reporting():
    assert not pack_is_reporting({"b_type": "", "b_serial": 0, "b_v": 0.0})
    assert not pack_is_reporting({})


def test_a_pack_whose_type_string_read_failed_still_counts_by_its_voltage():
    # Slot 43 of that unit answered a transient timeout on the type string
    # in one run while voltage, SOC and cycles came through.
    assert pack_is_reporting({"b_v": 27.1, "b_soc": 79})
