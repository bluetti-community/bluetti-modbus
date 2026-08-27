import requests

tag = "0.0.24"
url = f"https://github.com/bluetti-community/bluetti-registers/releases/download/{tag}/modbus-tcp.json"

output = "src/bluetti_modbus_lib/devices/"

print("Loading devices list schema")

schema = requests.get(url).json()


def to_camel_case(snake_str):
    return "".join(x.capitalize() for x in snake_str.lower().split("_"))


def get_type(t: str, name: str):
    upper = t.upper()

    if upper == "BOOL":
        return "UINT16"

    if upper != "UINT" and upper != "INT":
        return upper

    if upper == "INT":
        return "INT16"

    if name in ["b_i_e", "b_o_e"]:
        return "UINT32"

    return "UINT16"


for d in schema:
    name = d["name"]
    file_name = str(name).lower() + ".py"
    fields = ""

    for f in d["fields"]:
        fields += f"""
    {f["name"]} = field(
        t=FieldType.{get_type(str(f["content"]), f["name"])},
        address={f["address"]},"""

        if "unit" in f:
            fields += f'\n        unit="{f["unit"]}",'

        if "scale" in f:
            fields += f"\n        scale={f['scale']},"

        # bluetti-registers' schema also carries "category"/"state_class"/
        # "device_class" per field, but this library deliberately doesn't
        # surface them: those are Home Assistant entity concepts, not
        # Modbus/protocol ones, and belong in whichever integration
        # consumes this library, not in the library itself.

        if "length" in f and f["content"] == "string":
            fields += f"\n        length={f['length']},"

        if "length" in f and f["content"] != "string":
            fields += f"\n        count={f['length']},"

        # TODO enum building
        if "options" in f:
            fields += f"\n        enum_type={to_camel_case(f['options'])},"

        fields += "\n    )"

    content = f"""from ..base_devices import BluettiDevice
from ..enums import *
from ..fields import FieldType, field

# GENERATED FILE! DO NOT EDIT!


class {name}(BluettiDevice):
{fields}
"""

    with open(output + file_name, "w", encoding="utf-8") as f:
        f.write(content)
