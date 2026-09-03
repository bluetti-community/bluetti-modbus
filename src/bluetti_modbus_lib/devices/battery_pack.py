from modbus_connection import ModbusConnection

from .balco260 import Balco260

# BLUETTI confirmed by email (2026-09-03, to the maintainer) that the entire
# "Each Pack Base Information" block (51200-51249: type, serial, firmware
# versions, voltage, current, SOC, SOH, cycle count, temperature, cell/NTC
# counts, energy totals, protection/error/alarm bitmaps, estimated
# charge/discharge time) uses the same per-pack Modbus slave address pattern
# already confirmed for SOC/SOH alone in bluetti-community/bluetti-modbus#8 -
# and that a single Balco260 supports at most 5 BC200 packs.
MAX_BATTERY_PACKS = 5


def _pack_info_field_names() -> frozenset[str]:
    # Derived from Balco260's own field addresses rather than hand-listed,
    # so this never drifts if bluetti-registers changes the block. Reads the
    # class-level field registry directly - no live device/connection needed
    # for this, just the declared schema.
    return frozenset(
        name
        for name, field in Balco260._register_fields.items()
        if 51200 <= field.address <= 51249
    )


PACK_INFO_FIELDS = _pack_info_field_names()


def battery_pack(connection: ModbusConnection, slave_id: int) -> Balco260:
    """A Balco260 component restricted to one BC200 pack's own registers.

    Pack 1 is the same Modbus slave address as the main Balco260 device
    (already covered by its own fields - see d_num_battery_packs, address
    51001, for how many packs are actually attached). Packs 2 and up need
    their own component, restricted to just the "Each Pack Base Information"
    block, at their own slave address - this is what this function builds.
    """
    device = Balco260(connection.for_unit(slave_id))
    device.restrict_fields(PACK_INFO_FIELDS)
    return device
