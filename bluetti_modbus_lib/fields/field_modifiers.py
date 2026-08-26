from modbus_connection.model import RegisterField

from .field_extras import DeviceClass, FieldCategory, FieldStateClass

_FIELD_CATEGORIES: dict[int, FieldCategory | None] = {}
_FIELD_STATE_CLASSES: dict[int, FieldStateClass | None] = {}
_FIELD_DEVICE_CLASSES: dict[int, DeviceClass | None] = {}


def set_category(reg: RegisterField, category: FieldCategory | None) -> None:
    cls = type(reg)

    # Attach property to the class if not already attached
    if not hasattr(cls, "category"):

        def getter(self):
            return _FIELD_CATEGORIES.get(id(self))

        def setter(self, value):
            _FIELD_CATEGORIES[id(self)] = value

        cls.category = property(getter, setter)

    reg.category = category


def set_state_class(reg: RegisterField, state_class: FieldStateClass | None) -> None:
    cls = type(reg)

    # Attach property to the class if not already attached
    if not hasattr(cls, "state_class"):

        def getter(self):
            return _FIELD_STATE_CLASSES.get(id(self))

        def setter(self, value):
            _FIELD_STATE_CLASSES[id(self)] = value

        cls.state_class = property(getter, setter)

    reg.state_class = state_class


def set_device_class(reg: RegisterField, device_class: DeviceClass | None) -> None:
    cls = type(reg)

    # Attach property to the class if not already attached
    if not hasattr(cls, "device_class"):

        def getter(self):
            return _FIELD_DEVICE_CLASSES.get(id(self))

        def setter(self, value):
            _FIELD_DEVICE_CLASSES[id(self)] = value

        cls.device_class = property(getter, setter)

    reg.device_class = device_class
