from modbus_connection import ModbusConnection

from .balco260 import Balco260

# BLUETTI confirmed by email (2026-08-29, to the maintainer) that b_soc/b_soh
# (51221/51222) are per-pack values, read "using the corresponding slave
# address, for example, slave address 1" - and confirmed again by email
# (2026-09-03) that a single Balco260 supports at most 5 BC200 packs.
#
# Real-hardware testing (2026-09-05, a Balco260 with 3 confirmed, app-active
# BC200 packs) found this doesn't hold for the *rest* of the "Each Pack Base
# Information" block the way BLUETTI's general description implied: slave
# addresses 2 and up all read a clean, error-free 0 for these fields, on
# this device *and* on a second Balco260 with zero packs attached - i.e. the
# same "empty" response regardless of how many real packs exist. Kept here,
# not removed, since b_soc/b_soh's per-pack behavior at slave 1 (this
# device's own default address) is independently correct - see
# aggregate_pack_summary() below for the one part of the multi-pack story
# that *is* confirmed against real hardware.
MAX_BATTERY_PACKS = 5

# BLUETTI confirmed by email (2026-08-29) that b_soc_total/b_soh_total
# (51004/51005) and b_c_total (51003) are aggregate values across every
# attached pack, read at "the aggregate slave address 250 (0xFA)" - not the
# main device's own slave address. Real-hardware testing (2026-09-05)
# confirmed this for the entire "Pack Summary Information" block (51001-
# 51008, which also includes d_num_battery_packs): reading it at slave 250
# on a Balco260 with 3 real BC200 packs correctly returned 4 (1 main + 3
# packs, matching the Bluetti app's own count) for d_num_battery_packs,
# where reading the same register at the device's own slave address always
# read 0 regardless of how many packs were actually attached.
AGGREGATE_SLAVE_ID = 250


def _field_names_in_range(low: int, high: int) -> frozenset[str]:
    # Derived from Balco260's own field addresses rather than hand-listed,
    # so this never drifts if bluetti-registers changes either block. Reads
    # the class-level field registry directly - no live device/connection
    # needed for this, just the declared schema.
    return frozenset(
        name
        for name, field in Balco260._register_fields.items()
        if low <= field.address <= high
    )


PACK_INFO_FIELDS = _field_names_in_range(51200, 51249)
AGGREGATE_SUMMARY_FIELDS = _field_names_in_range(51001, 51008)


def battery_pack(connection: ModbusConnection, slave_id: int) -> Balco260:
    """A Balco260 component restricted to one BC200 pack's own registers.

    Pack 1 is the same Modbus slave address as the main Balco260 device
    (already covered by its own fields). Packs 2 and up need their own
    component, restricted to just the "Each Pack Base Information" block, at
    their own slave address - this is what this function builds. See
    MAX_BATTERY_PACKS' own comment for this mechanism's actual confirmed
    scope - it does not currently extend to every field in that block on
    real hardware, only b_soc/b_soh at slave 1.
    """
    device = Balco260(connection.for_unit(slave_id))
    device.restrict_fields(PACK_INFO_FIELDS)
    return device


def aggregate_pack_summary(connection: ModbusConnection) -> Balco260:
    """A Balco260 component restricted to the aggregate "Pack Summary"
    block (51001-51008: d_num_battery_packs, b_v_total, b_c_total,
    b_soc_total, b_soh_total, b_status, b_time_to_full_total,
    b_time_to_empty_total) - see AGGREGATE_SLAVE_ID's own comment for why
    this needs its own component at a different slave address rather than
    being part of the main Balco260 device's own read.
    """
    device = Balco260(connection.for_unit(AGGREGATE_SLAVE_ID))
    device.restrict_fields(AGGREGATE_SUMMARY_FIELDS)
    return device
