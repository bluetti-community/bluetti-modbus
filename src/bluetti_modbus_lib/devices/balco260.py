from probatio import Range

from ..base_devices import BluettiDevice
from ..enums import *
from ..fields import FieldType, dotted_version, field, nibble, reference_offset_current

# GENERATED FILE! DO NOT EDIT!


class Balco260(BluettiDevice):
    max_span = 20

    d_num_inverters = field(
        t=FieldType.UINT16,
        address=50001,
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
    pv_ac_p = field(
        t=FieldType.UINT16,
        address=50010,
        unit="W",
    )
    ac_o_e_total = field(
        t=FieldType.UINT16,
        address=50012,
        unit="kWh",
        scale=0.1,
    )
    pv_i_e_total = field(
        t=FieldType.UINT16,
        address=50014,
        unit="kWh",
        scale=0.1,
    )
    g_i_e_total = field(
        t=FieldType.UINT16,
        address=50016,
        unit="kWh",
        scale=0.1,
    )
    g_o_e_total = field(
        t=FieldType.UINT16,
        address=50018,
        unit="kWh",
        scale=0.1,
    )
    pv_ac_e = field(
        t=FieldType.UINT16,
        address=50020,
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
    d_inverter_fault = field(
        t=FieldType.ENUM,
        address=50027,
        count=5,
        enum_type=InverterFault,
    )
    d_inverter_type = field(
        t=FieldType.STRING,
        address=50200,
        length=6,
    )
    d_serial = field(
        t=FieldType.UINT64,
        address=50206,
    )
    d_ver_arm = dotted_version(50210)

    d_ver_dsp = dotted_version(50212)

    g_i_f = field(
        t=FieldType.UINT16,
        address=50214,
        unit="Hz",
        scale=0.1,
    )
    g_i_p_local = field(
        t=FieldType.UINT32,
        address=50215,
        unit="W",
        count=2,
    )
    ac_o_p_local = field(
        t=FieldType.UINT32,
        address=50217,
        unit="W",
        count=2,
    )
    pv_i_p_local = field(
        t=FieldType.UINT32,
        address=50219,
        unit="W",
        count=2,
    )
    pv_ac_p_local = field(
        t=FieldType.UINT32,
        address=50221,
        unit="W",
        count=2,
    )
    g_i_e_local = field(
        t=FieldType.UINT32,
        address=50223,
        unit="kWh",
        scale=0.1,
        count=2,
    )
    g_o_e_local = field(
        t=FieldType.UINT32,
        address=50225,
        unit="kWh",
        scale=0.1,
        count=2,
    )
    ac_o_e_local = field(
        t=FieldType.UINT32,
        address=50227,
        unit="kWh",
        scale=0.1,
        count=2,
    )
    pv_i_e_local = field(
        t=FieldType.UINT32,
        address=50229,
        unit="kWh",
        scale=0.1,
        count=2,
    )
    pv_ac_e_local = field(
        t=FieldType.UINT32,
        address=50231,
        unit="kWh",
        scale=0.1,
        count=2,
    )
    d_self_consumption = field(
        t=FieldType.UINT16,
        address=50233,
        unit="%",
    )
    d_phase_count = field(
        t=FieldType.UINT16,
        address=50234,
    )
    g_1_i_p = field(
        t=FieldType.UINT16,
        address=50235,
        unit="W",
    )
    g_1_i_v = field(
        t=FieldType.UINT16,
        address=50236,
        unit="V",
        scale=0.1,
    )
    g_1_i_c = field(
        t=FieldType.UINT16,
        address=50237,
        unit="A",
        scale=0.1,
    )
    g_2_i_p = field(
        t=FieldType.UINT16,
        address=50238,
        unit="W",
    )
    g_2_i_v = field(
        t=FieldType.UINT16,
        address=50239,
        unit="V",
        scale=0.1,
    )
    g_2_i_c = field(
        t=FieldType.UINT16,
        address=50240,
        unit="A",
        scale=0.1,
    )
    g_3_i_p = field(
        t=FieldType.UINT16,
        address=50241,
        unit="W",
    )
    g_3_i_v = field(
        t=FieldType.UINT16,
        address=50242,
        unit="V",
        scale=0.1,
    )
    g_3_i_c = field(
        t=FieldType.UINT16,
        address=50243,
        unit="A",
        scale=0.1,
    )
    ac_phase_count = field(
        t=FieldType.UINT16,
        address=50244,
    )
    ac_1_o_p = field(
        t=FieldType.UINT16,
        address=50245,
        unit="W",
    )
    ac_1_o_v = field(
        t=FieldType.UINT16,
        address=50246,
        unit="V",
        scale=0.1,
    )
    ac_1_o_c = field(
        t=FieldType.UINT16,
        address=50247,
        unit="A",
        scale=0.1,
    )
    ac_2_o_p = field(
        t=FieldType.UINT16,
        address=50248,
        unit="W",
    )
    ac_2_o_v = field(
        t=FieldType.UINT16,
        address=50249,
        unit="V",
        scale=0.1,
    )
    ac_2_o_c = field(
        t=FieldType.UINT16,
        address=50250,
        unit="A",
        scale=0.1,
    )
    ac_3_o_p = field(
        t=FieldType.UINT16,
        address=50251,
        unit="W",
    )
    ac_3_o_v = field(
        t=FieldType.UINT16,
        address=50252,
        unit="V",
        scale=0.1,
    )
    ac_3_o_c = field(
        t=FieldType.UINT16,
        address=50253,
        unit="A",
        scale=0.1,
    )
    d_inverter_phase_count = field(
        t=FieldType.UINT16,
        address=50254,
    )
    d_inverter_1_status = field(
        t=FieldType.ENUM,
        address=50255,
        enum_type=InverterStatus,
    )
    d_inverter_1_p = field(
        t=FieldType.UINT16,
        address=50256,
        unit="W",
    )
    d_inverter_1_v = field(
        t=FieldType.UINT16,
        address=50257,
        unit="V",
        scale=0.1,
    )
    d_inverter_1_c = field(
        t=FieldType.UINT16,
        address=50258,
        unit="A",
        scale=0.1,
    )
    d_inverter_2_status = field(
        t=FieldType.ENUM,
        address=50259,
        enum_type=InverterStatus,
    )
    d_inverter_2_p = field(
        t=FieldType.UINT16,
        address=50260,
        unit="W",
    )
    d_inverter_2_v = field(
        t=FieldType.UINT16,
        address=50261,
        unit="V",
        scale=0.1,
    )
    d_inverter_2_c = field(
        t=FieldType.UINT16,
        address=50262,
        unit="A",
        scale=0.1,
    )
    d_inverter_3_status = field(
        t=FieldType.ENUM,
        address=50263,
        enum_type=InverterStatus,
    )
    d_inverter_3_p = field(
        t=FieldType.UINT16,
        address=50264,
        unit="W",
    )
    d_inverter_3_v = field(
        t=FieldType.UINT16,
        address=50265,
        unit="V",
        scale=0.1,
    )
    d_inverter_3_c = field(
        t=FieldType.UINT16,
        address=50266,
        unit="A",
        scale=0.1,
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
    pv_2_i_v = field(
        t=FieldType.UINT16,
        address=50274,
        unit="V",
        scale=0.1,
    )
    pv_2_i_c = field(
        t=FieldType.UINT16,
        address=50275,
        unit="A",
        scale=0.1,
    )
    pv_3_i_type = field(
        t=FieldType.ENUM,
        address=50276,
        enum_type=PvType,
    )
    pv_3_i_p = field(
        t=FieldType.UINT16,
        address=50277,
        unit="W",
    )
    pv_3_i_v = field(
        t=FieldType.UINT16,
        address=50278,
        unit="V",
        scale=0.1,
    )
    pv_3_i_c = field(
        t=FieldType.UINT16,
        address=50279,
        unit="A",
        scale=0.1,
    )
    pv_4_i_type = field(
        t=FieldType.ENUM,
        address=50280,
        enum_type=PvType,
    )
    pv_4_i_p = field(
        t=FieldType.UINT16,
        address=50281,
        unit="W",
    )
    pv_4_i_v = field(
        t=FieldType.UINT16,
        address=50282,
        unit="V",
        scale=0.1,
    )
    pv_4_i_c = field(
        t=FieldType.UINT16,
        address=50283,
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
    b_soh_total = field(
        t=FieldType.UINT16,
        address=51005,
        unit="%",
    )
    b_status = field(
        t=FieldType.ENUM,
        address=51006,
        enum_type=PackChargingStatus,
    )
    b_time_to_full_total = field(
        t=FieldType.UINT16,
        address=51007,
        unit="min",
    )
    b_time_to_empty_total = field(
        t=FieldType.UINT16,
        address=51008,
        unit="min",
    )
    b_type = field(
        t=FieldType.STRING,
        address=51200,
        length=6,
    )
    b_serial = field(
        t=FieldType.UINT64,
        address=51206,
        count=4,
    )
    b_ver_1 = dotted_version(51211)

    b_ver_2 = dotted_version(51213)

    b_ver_3 = dotted_version(51215)

    b_ver_4 = dotted_version(51217)

    b_v = field(
        t=FieldType.UINT16,
        address=51219,
        unit="V",
        scale=0.1,
    )
    b_c = reference_offset_current(51220, reference=30000)

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
    b_cycle_count = field(
        t=FieldType.UINT16,
        address=51223,
    )
    b_t_avg = field(
        t=FieldType.INT16,
        address=51224,
        unit="°C",
    )
    b_cell_count = field(
        t=FieldType.UINT16,
        address=51234,
    )
    b_ntc_count = field(
        t=FieldType.UINT16,
        address=51235,
    )
    b_i_e = field(
        t=FieldType.UINT32,
        address=51236,
        unit="Wh",
    )
    b_o_e = field(
        t=FieldType.UINT32,
        address=51238,
        unit="Wh",
    )
    b_protect = field(
        t=FieldType.UINT32,
        address=51240,
        count=2,
    )
    b_error = field(
        t=FieldType.UINT16,
        address=51242,
        count=3,
    )
    b_alarm_residential = field(
        t=FieldType.UINT16,
        address=51245,
    )
    b_alarm_portable = field(
        t=FieldType.UINT32,
        address=51246,
        count=2,
    )
    b_time_to_full = field(
        t=FieldType.UINT16,
        address=51248,
        unit="min",
    )
    b_time_to_empty = field(
        t=FieldType.UINT16,
        address=51249,
        unit="min",
    )
    d_iot_model = field(
        t=FieldType.STRING,
        address=53001,
        length=6,
    )
    d_iot_serial = field(
        t=FieldType.UINT64,
        address=53007,
    )
    d_iot_ver = dotted_version(53011)

    ac_o_switch = field(
        t=FieldType.UINT16,
        address=57001,
        writable=True,
    )
    g_i_switch = field(
        t=FieldType.UINT16,
        address=57009,
        writable=True,
    )
    g_o_switch = field(
        t=FieldType.UINT16,
        address=57010,
        writable=True,
    )
    b_soc_low = field(
        t=FieldType.UINT16,
        address=57016,
        writable=Range(min=0, max=100),
        unit="%",
    )
    b_soc_high = field(
        t=FieldType.UINT16,
        address=57017,
        writable=Range(min=0, max=100),
        unit="%",
    )
