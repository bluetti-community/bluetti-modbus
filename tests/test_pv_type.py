from bluetti_modbus_lib.enums.pv_type import PvType


def test_covers_all_6_real_values_including_100_and_101():
    # A previous attempt at this enum only covered 0-3 and was reverted
    # after every real Balco260 (which always reports 100) hit
    # modbus_connection's "no mapping for value X" fallback on every read
    # (bluetti-registers@8f5dadd) - this regression test locks in that the
    # "only available on some models" values are covered too.
    assert PvType.Reserve.value == 0
    assert PvType.Car.value == 1
    assert PvType.Adapter.value == 2
    assert PvType.Other.value == 3
    assert PvType.DcPv.value == 100
    assert PvType.AcPv.value == 101
