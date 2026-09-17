from ..base_devices import BluettiDevice
from ..enums import *
from ..fields import FieldType, dotted_version_2part, field, nibble

# NOT a "GENERATED FILE" like the other devices/*.py in this package - those
# are generated from BLUETTI's own official register spec sheets (see
# bluetti-community/bluetti-registers), which don't cover the AC200L/
# AC200L2 (a portable power station, not one of BLUETTI's Modbus-documented
# grid-interactive models). This profile is instead cloned from AC500.py's
# own register set (see that file) and corrected by cross-referencing this
# integration's own raw-register diagnostics dump against the same physical
# AC200L2's simultaneously-live bluetti_bt (BLE/bluetti-bt-lib) readings -
# the two integrations reading the same hardware at the same time. AC200L2's
# own device-type string (d_inverter_type, 50200) self-identifies as
# "AC200L", not "AC200L2" - BLUETTI brands the L2 as a running firmware
# revision of the same AC200L product line, not a distinct Modbus identity.
#
# Confirmed exact matches against bluetti_bt_lib's AC200L readings on real
# hardware: d_inverter_type ("AC200L"), ac_o_p_total (353 == BLE's
# ac_output_power), g_i_p_total (353 == BLE's ac_input_power), d_ver_arm/
# d_ver_dsp ("2134.07"/"2098.22"), ac_o_switch/dc_o_switch (1/0 == BLE's
# ac_output/dc_output on/off), b_soc_total (100 == BLE's battery_soc),
# b_soc_low/b_soc_high (20/80 == BLE's soc_low/soc_high, found via a
# per-register scan of the 57000s block - see those fields' own comment).
#
# NOT found despite trying: a Modbus equivalent of BLE's CTRL_UPS_MODE.
# A per-register scan of the whole 57000-57060 neighborhood, plus a
# controlled before/after diff across an actual UPS-mode change on real
# hardware (Standard -> Customized, 2026-09-17), found no register that
# changed at all - so it isn't hiding in this control block the way
# b_soc_low/high were. It likely lives elsewhere in the address space, but
# a broader blind scan risks the same kind of failure this file's own git
# history already hit once (a wide contiguous register_ranges read spanning
# an invalid address took the whole coordinator down - see
# coordinator.py's own comment on this device's Modbus stack becoming
# unresponsive under load). Not worth the risk for one field that's
# already available via bluetti_bt (BLE) on the same hardware.
#
# Confirmed corrections (AC500's own scale is wrong for this model):
# - g_i_f: raw 599 read 5.99 Hz under AC500's scale=0.01; BLE's simultaneous
#   reading was 59.90 Hz. 599 * 0.1 == 59.9 - scale=0.1 here, not 0.01.
# - b_v_total: raw 5409 read 540.9 V under AC500's scale=0.1 - implausible
#   for this model's single ~51.2 V-nominal internal pack (not a stacked
#   multi-module 500 V+ system like a real AC500). 5409 * 0.01 == 54.09 V,
#   a plausible near-full-charge reading. scale=0.01 here, not 0.1.
#
# Inferred, NOT independently confirmed - no known-correct reference value
# was available to check against:
# - b_c_total: same 51001-51004 battery-totals block as b_v_total, so given
#   scale=0.01 here on the assumption the firmware encodes the whole block
#   the same way - but the battery was idle at 100% SoC during testing, so
#   this couldn't be checked against a nonzero real current. Revisit if a
#   charge/discharge reading looks off by 10x.
# - PV fields (pv_dc_count/pv_ac_count/pv_1_i_*/pv_2_i_*): all read 0/
#   Reserve with no panels connected during testing, same as AC500's own
#   unconfirmed PvType mapping (see sensor.py) - carried over unchanged from
#   AC500's addresses/scale, unverified.
# - ac_o_switch/dc_o_switch: confirmed correct for *reading* on/off state.
#   dc_o_switch's write was confirmed by the owner on real hardware
#   (2026-09-17: toggling it cycled both the USB and DC ports off and back
#   on as expected) - writable=True.
#   ac_o_switch is also writable=True now, enabled at the owner's explicit
#   request after that DC confirmation - accepted with full awareness that
#   this unit's AC output is the live load path for this same Home
#   Assistant install and its servers, so a write landing wrong here means
#   losing power to the very system controlling it. Unlike dc_o_switch,
#   this specific write has not itself been separately tested (the AC test
#   is the one write on this device you can't safely dry-run).
#
# d_num_battery_packs (51001) reads 3 on this single sealed-battery unit -
# clearly not a real pack count for this model, same category of
# known-unreliable-but-harmless register as AC500's own g_i_switch. Still
# declared/read (no reason to pay for a second round trip to drop it from
# register_ranges) but hidden from the UI - see const.py's
# AC200L_FIELDS_NOT_SHOWN.


class AC200L(BluettiDevice):
    register_ranges = (
        (50002, 50002),
        (50004, 50004),
        (50006, 50006),
        (50012, 50013),
        (50018, 50019),
        (50022, 50022),
        (50023, 50026),
        (50200, 50205),
        (50206, 50209),
        (50210, 50211),
        (50212, 50213),
        (50214, 50214),
        (50215, 50215),
        (50217, 50217),
        (50219, 50219),
        (50229, 50229),
        (50267, 50267),
        (50268, 50268),
        (50269, 50269),
        (50270, 50270),
        (50272, 50272),
        (50273, 50273),
        (51001, 51001),
        (51002, 51002),
        (51003, 51003),
        (51004, 51004),
        (57001, 57001),
        (57005, 57005),
        (57009, 57009),
        (57016, 57016),
        (57017, 57017),
    )

    ac_o_p_total = field(
        t=FieldType.UINT16,
        address=50002,
        unit="W",
    )
    pv_i_p_total = field(
        t=FieldType.UINT16,
        address=50004,
        unit="W",
    )
    g_i_p_total = field(
        t=FieldType.INT16,
        address=50006,
        unit="W",
    )
    ac_o_e_total = field(
        t=FieldType.UINT32,
        address=50012,
        unit="kWh",
        scale=0.1,
        count=2,
    )
    g_o_e_total = field(
        t=FieldType.UINT32,
        address=50018,
        unit="kWh",
        scale=0.1,
        count=2,
    )
    d_inverter_status = field(
        t=FieldType.ENUM,
        address=50022,
        enum_type=InverterStatus,
    )
    d_inverter_warning = field(
        t=FieldType.ENUM,
        address=50023,
        count=4,
        enum_type=InverterWarning,
    )
    d_inverter_type = field(
        t=FieldType.STRING_SWAPPED,
        address=50200,
        length=6,
    )
    d_serial = field(
        t=FieldType.UINT64,
        address=50206,
    )
    d_ver_arm = dotted_version_2part(50210)

    d_ver_dsp = dotted_version_2part(50212)

    # Confirmed: raw 599 * 0.1 == 59.9 Hz, matching bluetti_bt's simultaneous
    # 59.90 Hz reading. AC500's own scale=0.01 is wrong for this model - see
    # module docstring above.
    g_i_f = field(
        t=FieldType.UINT16,
        address=50214,
        unit="Hz",
        scale=0.1,
    )
    g_i_p_local = field(
        t=FieldType.UINT16,
        address=50215,
        unit="W",
        count=1,
    )
    ac_o_p_local = field(
        t=FieldType.UINT16,
        address=50217,
        unit="W",
        count=1,
    )
    pv_i_p_local = field(
        t=FieldType.UINT16,
        address=50219,
        unit="W",
        count=1,
    )
    pv_i_e_local = field(
        t=FieldType.UINT16,
        address=50229,
        unit="kWh",
        scale=0.1,
        count=1,
    )
    pv_dc_count = nibble(50267, high=False)

    pv_ac_count = nibble(50267, high=True)

    pv_1_i_type = field(
        t=FieldType.ENUM,
        address=50268,
        enum_type=PvType,
    )
    pv_1_i_p = field(
        t=FieldType.UINT16,
        address=50269,
        unit="W",
    )
    pv_1_i_v = field(
        t=FieldType.UINT16,
        address=50270,
        unit="V",
        scale=0.1,
    )
    pv_2_i_type = field(
        t=FieldType.ENUM,
        address=50272,
        enum_type=PvType,
    )
    pv_2_i_p = field(
        t=FieldType.UINT16,
        address=50273,
        unit="W",
    )
    d_num_battery_packs = field(
        t=FieldType.UINT16,
        address=51001,
    )
    # Confirmed: raw 5409 * 0.01 == 54.09 V, plausible for this model's
    # single ~51.2 V-nominal pack near full charge. AC500's own scale=0.1
    # (implying 540.9 V) is wrong for this model - see module docstring.
    b_v_total = field(
        t=FieldType.UINT16,
        address=51002,
        unit="V",
        scale=0.01,
    )
    # Inferred from b_v_total's own correction, same register block - NOT
    # independently confirmed against a nonzero real current. See module
    # docstring.
    b_c_total = field(
        t=FieldType.UINT16,
        address=51003,
        unit="A",
        scale=0.01,
    )
    b_soc_total = field(
        t=FieldType.UINT16,
        address=51004,
        unit="%",
    )
    # writable=True - enabled at the owner's explicit request, aware this is
    # the live AC load path for this same HA install. See module docstring.
    ac_o_switch = field(
        t=FieldType.UINT16,
        address=57001,
        writable=True,
    )
    # writable=True - write confirmed on real hardware by the owner
    # (2026-09-17). See module docstring.
    dc_o_switch = field(
        t=FieldType.UINT16,
        address=57005,
        writable=True,
    )
    g_i_switch = field(
        t=FieldType.UINT16,
        address=57009,
    )
    # Confirmed by a per-register scan of the 57000s control block (not in
    # AC500's own field set - AC500 has no SoC threshold registers at all):
    # 57016/57017 read 20/80, exactly matching bluetti_bt's simultaneous
    # soc_low/soc_high (20%/80%). Same addresses as Balco260's own
    # b_soc_low/b_soc_high (see that file) - this block is apparently
    # shared across more than one Bluetti product line. writable=False for
    # now (unlike Balco260's Range-validated writable) - these are battery
    # protection thresholds, not tested for writing on this hardware, and
    # getting a write wrong here risks the battery's own longevity, not
    # just an inconvenience like the AC/DC switches.
    b_soc_low = field(
        t=FieldType.UINT16,
        address=57016,
        unit="%",
    )
    b_soc_high = field(
        t=FieldType.UINT16,
        address=57017,
        unit="%",
    )
