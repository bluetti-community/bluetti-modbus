from modbus_connection.model.fields import NumberField

from bluetti_modbus_lib.fields.field_extras import (
    DeviceClass,
    FieldCategory,
    FieldStateClass,
)
from bluetti_modbus_lib.fields.field_modifiers import (
    set_category,
    set_device_class,
    set_state_class,
)


def _field() -> NumberField:
    return NumberField(0)


def test_set_category_is_visible_on_the_instance():
    reg = _field()
    set_category(reg, FieldCategory.DIAGNOSTIC)
    assert reg.category is FieldCategory.DIAGNOSTIC


def test_set_state_class_is_visible_on_the_instance():
    reg = _field()
    set_state_class(reg, FieldStateClass.MEASUREMENT)
    assert reg.state_class is FieldStateClass.MEASUREMENT


def test_set_device_class_is_visible_on_the_instance():
    reg = _field()
    set_device_class(reg, DeviceClass.VOLTAGE)
    assert reg.device_class is DeviceClass.VOLTAGE


def test_untagged_field_has_no_category_via_getattr_default():
    # This is the actual access pattern used by BluettiModbusClient - a
    # plain instance attribute that was never set raises AttributeError,
    # so callers rely on getattr(..., None) rather than a bare access.
    reg = _field()
    assert getattr(reg, "category", None) is None
    assert getattr(reg, "state_class", None) is None
    assert getattr(reg, "device_class", None) is None


def test_tagging_one_field_does_not_leak_into_another():
    reg1 = _field()
    reg2 = _field()

    set_category(reg1, FieldCategory.CONFIG)

    assert reg1.category is FieldCategory.CONFIG
    assert getattr(reg2, "category", None) is None
