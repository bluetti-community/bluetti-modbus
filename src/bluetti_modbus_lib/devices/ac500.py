from ..base_devices import BluettiDevice
from ..enums import *
from ..fields import FieldType, dotted_version_2part, field, nibble

# GENERATED FILE! DO NOT EDIT!


class AC500(BluettiDevice):
    register_ranges = (
        (50002, 50002),
        (50004, 50004),
        (50006, 50006),
        (50008, 50008),
        (50012, 50012),
        (50018, 50018),
        (50022, 50022),
        (50023, 50026),
        (50200, 50205),
        (50206, 50206),
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
        (50271, 50271),
        (50272, 50272),
        (50273, 50273),
        (50275, 50275),
        (51001, 51001),
        (51002, 51002),
        (51003, 51003),
        (51004, 51004),
        (57001, 57001),
        (57005, 57005),
        (57009, 57009),
        (57010, 57010),
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
        t=FieldType.UINT16,
        address=50006,
        unit="W",
    )
    d_inverter_total = field(
        t=FieldType.UINT16,
        address=50008,
        unit="W",
    )
    ac_o_e_total = field(
        t=FieldType.UINT16,
        address=50012,
        unit="kWh",
        scale=0.1,
    )
    g_o_e_total = field(
        t=FieldType.UINT16,
        address=50018,
        unit="kWh",
        scale=0.1,
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
        t=FieldType.STRING,
        address=50200,
        length=6,
    )
    d_serial = field(
        t=FieldType.UINT16,
        address=50206,
    )
    d_ver_arm = dotted_version_2part(50210)

    d_ver_dsp = dotted_version_2part(50212)

    g_i_f = field(
        t=FieldType.UINT16,
        address=50214,
        unit="Hz",
        scale=0.01,
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
    pv_1_i_c = field(
        t=FieldType.UINT16,
        address=50271,
        unit="A",
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
    pv_2_i_c = field(
        t=FieldType.UINT16,
        address=50275,
        unit="A",
        scale=0.1,
    )
    d_num_battery_packs = field(
        t=FieldType.UINT16,
        address=51001,
    )
    b_v_total = field(
        t=FieldType.UINT16,
        address=51002,
        unit="V",
        scale=0.1,
    )
    b_c_total = field(
        t=FieldType.UINT16,
        address=51003,
        unit="A",
        scale=0.1,
    )
    b_soc_total = field(
        t=FieldType.UINT16,
        address=51004,
        unit="%",
    )
    ac_o_switch = field(
        t=FieldType.UINT16,
        address=57001,
    )
    dc_o_switch = field(
        t=FieldType.UINT16,
        address=57005,
    )
    g_i_switch = field(
        t=FieldType.UINT16,
        address=57009,
    )
    g_o_switch = field(
        t=FieldType.UINT16,
        address=57010,
    )
