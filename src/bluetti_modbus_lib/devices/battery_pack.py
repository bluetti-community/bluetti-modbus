from collections.abc import Mapping
from typing import Any

from modbus_connection import ModbusConnection

from .balco260 import Balco260

# BLUETTI confirmed by email (2026-08-29, to the maintainer) that b_soc/b_soh
# (51221/51222) are per-pack values, read "using the corresponding slave
# address, for example, slave address 1" - and confirmed again by email
# (2026-09-03) that a single Balco260 supports at most 5 BC260 packs.
#
# Real-hardware testing (2026-09-05, a Balco260 with 3 confirmed, app-active
# BC260 packs) found slave addresses 2 and up reading a clean, error-free 0
# for the whole "Each Pack Base Information" block - which turned out to be
# the wrong addresses, not missing data: the packs live at 41 and up, see
# EXPANSION_PACK_FIRST_SLAVE_ID.
MAX_BATTERY_PACKS = 5

# BLUETTI's answer (by email, 2026-09-17) to the finding above: "for
# individual battery pack data, the unit ID starts from 41" - the expansion
# packs were never at slave 2, 3, ... A slave-id sweep on a one-pack
# Balco260 the same day agrees as far as one pack can: 41 serves the "Each
# Pack Base Information" block as zeros (an empty expansion slot - that
# device's own built-in pack is read at slave 1), while 2 and 3 serve it as
# zeros *alongside* the per-inverter PV charging power register (50219, the
# one register of the "(Single)" inverter block a Balco260 does populate),
# i.e. they look like inverter slots, not pack slots. Confirmed on
# multi-pack hardware on 2026-09-18 (bluetti-community/bluetti-modbus#55): a
# Balco260 with three BC260 packs answered the whole block at 42 and 43
# with each pack's own type string ("BC260"), serial number, voltage, SOC,
# SOH, cycle count, firmware version and energies - different from each
# other and from the built-in pack at slave 1 - with d_num_battery_packs
# reading 4 at the aggregate slave. Slot 41 on that same unit, and on a
# second Balco260 with no pack attached, answered a serial number and zeros
# for everything else - a firmware issue BLUETTI has since confirmed and
# plans to fix (2026-09-20); until then see pack_is_reporting(). BLUETTI
# has also said a future firmware will list the unit ids in use and the
# serial number behind each. 90-96 and 250 repeat the built-in pack field
# for field: aliases of the aggregate view, not packs.
EXPANSION_PACK_FIRST_SLAVE_ID = 41

# BLUETTI confirmed by email (2026-08-29) that b_soc_total/b_soh_total
# (51004/51005) and b_c_total (51003) are aggregate values across every
# attached pack, read at "the aggregate slave address 250 (0xFA)" - not the
# main device's own slave address. Real-hardware testing (2026-09-05)
# confirmed this for the entire "Pack Summary Information" block (51001-
# 51008, which also includes d_num_battery_packs): reading it at slave 250
# on a Balco260 with 3 real BC260 packs correctly returned 4 (1 main + 3
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


def pack_slave_id(pack_num: int) -> int:
    """The Modbus slave address of battery pack number pack_num.

    Pack 1 is the Balco260's built-in pack, read at the device's own slave
    address as part of its own fields; pack 2 is the first BC260 expansion
    pack, at EXPANSION_PACK_FIRST_SLAVE_ID, pack 3 the next one at the
    following address, and so on up to MAX_BATTERY_PACKS expansion packs.
    This is the numbering d_num_battery_packs (read at AGGREGATE_SLAVE_ID)
    counts in: 4 for a Balco260 with three BC260 packs.
    """
    if not 2 <= pack_num <= MAX_BATTERY_PACKS + 1:
        msg = (
            f"pack_num must be 2..{MAX_BATTERY_PACKS + 1} (pack 1 is the built-in "
            f"pack at the device's own slave address), got {pack_num}"
        )
        raise ValueError(msg)
    return EXPANSION_PACK_FIRST_SLAVE_ID + pack_num - 2


def pack_is_reporting(values: Mapping[str, Any]) -> bool:
    """Whether a pack's read carries live data, or just its serial number.

    Real multi-pack hardware (2026-09-18, #55) showed a slot that serves a
    serial number but reports nothing else: type string empty, voltage,
    SOC, SOH, cycle count, versions and energies all 0 - a firmware issue
    BLUETTI has confirmed and plans to fix. Such a slot must not be shown
    as "0 %, 0 V" (or, worse, as 3000 A: b_c's raw 0 is 30000 below its
    reference); a consumer treats it as absent until it reports. A
    reporting pack always has its type string and a non-zero voltage.
    """
    return bool(values.get("b_type")) or bool(values.get("b_v"))


def battery_pack(connection: ModbusConnection, slave_id: int) -> Balco260:
    """A Balco260 component restricted to one BC260 pack's own registers.

    Pack 1 is the same Modbus slave address as the main Balco260 device
    (already covered by its own fields). Packs 2 and up need their own
    component, restricted to just the "Each Pack Base Information" block, at
    their own slave address - this is what this function builds; get that
    address from pack_slave_id(), not from the pack number itself (see
    EXPANSION_PACK_FIRST_SLAVE_ID's own comment). See MAX_BATTERY_PACKS' own
    comment for how this was confirmed, and pack_is_reporting() for the one
    thing to check on the values before showing them.
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
