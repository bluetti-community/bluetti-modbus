from modbus_connection.model import RegisterField

from .field_extras import DeviceClass, FieldCategory, FieldStateClass


def set_category(reg: RegisterField, category: FieldCategory | None) -> None:
    reg.category = category


def set_state_class(reg: RegisterField, state_class: FieldStateClass | None) -> None:
    reg.state_class = state_class


def set_device_class(reg: RegisterField, device_class: DeviceClass | None) -> None:
    reg.device_class = device_class
