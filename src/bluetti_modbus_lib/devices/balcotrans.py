from ..base_devices import BluettiDevice
from ..enums import *
from ..fields import FieldType, dotted_version, field

# GENERATED FILE! DO NOT EDIT!


class Balcotrans(BluettiDevice):
    max_span = 20

    d_num_inverters = field(
        t=FieldType.UINT16,
        address=50001,
    )
    ac_o_p_total = field(
        t=FieldType.UINT32,
        address=50002,
        unit="W",
        count=2,
    )
    pv_i_p_total = field(
        t=FieldType.UINT32,
        address=50004,
        unit="W",
        count=2,
    )
    d_inverter_total = field(
        t=FieldType.INT32,
        address=50008,
        unit="W",
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
        t=FieldType.INT16,
        address=50237,
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
        t=FieldType.INT16,
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
    b_v_total = field(
        t=FieldType.UINT16,
        address=51002,
        unit="V",
        scale=0.1,
    )
    b_soc_total = field(
        t=FieldType.UINT16,
        address=51004,
        unit="%",
    )
