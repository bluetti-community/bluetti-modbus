import inspect

import bluetti_modbus_lib
from bluetti_modbus_lib import devices as devices_module
from bluetti_modbus_lib.base_devices import BluettiDevice


def test_every_device_class_is_re_exported_at_the_top_level():
    # Regression test: Balco500 was added to devices/__init__.py but not to
    # the package root's own import list (a real gap this exact check would
    # have caught - see bluetti-community/bluetti-modbus#59's follow-up).
    # `from bluetti_modbus_lib import <Device>` is the documented import
    # style (see README.md's own examples), so every BluettiDevice subclass
    # the devices subpackage defines needs a matching top-level re-export,
    # not just the devices subpackage itself.
    device_classes = {
        name
        for name, obj in inspect.getmembers(devices_module, inspect.isclass)
        if issubclass(obj, BluettiDevice) and obj is not BluettiDevice
    }
    missing = {name for name in device_classes if not hasattr(bluetti_modbus_lib, name)}
    assert missing == set()
