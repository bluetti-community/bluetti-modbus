from ..base_devices import BluettiDevice
from ..enums import *
from ..fields import FieldType, dotted_version_2part, field, nibble

# GENERATED FILE! DO NOT EDIT!


class AC240(BluettiDevice):
    register_ranges = (
        (50002, 50002),
        (50004, 50004),
        (50006, 50006),
        (50008, 50008),
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
        (50235, 50235),
        (50236, 50236),
        (50237, 50237),
        (50245, 50245),
        (50247, 50247),
        (50255, 50255),
        (50256, 50256),
        (50257, 50257),
        (50267, 50267),
        (50268, 50268),
        (50269, 50269),
        (50270, 50270),
        (50271, 50271),
        (51001, 51001),
        (51002, 51002),
        (51003, 51003),
        (51004, 51004),
        (51211, 51212),
        (51219, 51219),
        (51221, 51221),
        (51222, 51222),
        (53001, 53006),
        (53007, 53010),
        (53011, 53012),
        (57001, 57001),
        (57005, 57005),
        (57009, 57009),
        (57016, 57016),
        (57017, 57017),
        (57022, 57022),
        (57024, 57024),
    )

    ac_o_p_total = field(
        t=FieldType.UINT16,
        address=50002,
        unit="W",
        count=1,
    )
    pv_i_p_total = field(
        t=FieldType.UINT16,
        address=50004,
        unit="W",
        count=1,
    )
    g_i_p_total = field(
        t=FieldType.INT16,
        address=50006,
        unit="VA",
        count=1,
    )
    d_inverter_total = field(
        t=FieldType.INT16,
        address=50008,
        unit="W",
        count=1,
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

    g_i_f = field(
        t=FieldType.UINT16,
        address=50214,
        unit="Hz",
        scale=0.1,
    )
    g_i_p_local = field(
        t=FieldType.UINT16,
        address=50215,
        unit="VA",
        count=1,
    )
    ac_o_p_local = field(
        t=FieldType.UINT16,
        address=50217,
        unit="VA",
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
    g_1_i_p = field(
        t=FieldType.UINT16,
        address=50235,
        unit="VA",
    )
    g_1_i_v = field(
        t=FieldType.UINT16,
        address=50236,
        unit="V",
        scale=1,
    )
    g_1_i_c = field(
        t=FieldType.INT16,
        address=50237,
        unit="A",
        scale=0.1,
    )
    ac_1_o_p = field(
        t=FieldType.UINT16,
        address=50245,
        unit="VA",
    )
    ac_1_o_c = field(
        t=FieldType.UINT16,
        address=50247,
        unit="A",
        scale=0.1,
    )
    d_inverter_1_status = field(
        t=FieldType.ENUM,
        address=50255,
        enum_type=InverterStatus,
    )
    d_inverter_1_p = field(
        t=FieldType.INT16,
        address=50256,
        unit="W",
    )
    ac_1_o_v = field(
        t=FieldType.UINT16,
        address=50257,
        unit="V",
        scale=1,
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
    b_ver_1 = dotted_version_2part(51211)

    b_v = field(
        t=FieldType.UINT16,
        address=51219,
        unit="V",
        scale=0.01,
    )
    b_soc = field(
        t=FieldType.UINT16,
        address=51221,
        unit="%",
    )
    b_soh = field(
        t=FieldType.UINT16,
        address=51222,
        unit="%",
    )
    d_iot_model = field(
        t=FieldType.STRING_SWAPPED,
        address=53001,
        length=6,
    )
    d_iot_serial = field(
        t=FieldType.UINT64,
        address=53007,
    )
    d_iot_ver = dotted_version_2part(53011)

    ac_o_switch = field(
        t=FieldType.UINT16,
        address=57001,
        writable=True,
    )
    dc_o_switch = field(
        t=FieldType.UINT16,
        address=57005,
        writable=True,
    )
    g_i_switch = field(
        t=FieldType.UINT16,
        address=57009,
        writable=True,
    )
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
    ac_power_lifting_switch = field(
        t=FieldType.UINT16,
        address=57022,
        writable=True,
    )
    ac_eco_switch = field(
        t=FieldType.UINT16,
        address=57024,
        writable=True,
    )
