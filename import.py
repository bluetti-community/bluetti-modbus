import requests

tag = "0.0.20"
url = f"https://github.com/Patrick762/bluetti-registers/releases/download/{tag}/modbus-tcp.json"

output = "bluetti_modbus_lib/devices/"

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
            fields += f'\n\t\tunit="{f["unit"]}",'

        if "scale" in f:
            fields += f"\n\t\tscale={f["scale"]},"

        if "category" in f:
            fields += f"\n\t\tcategory=FieldCategory.{str(f["category"]).upper()},"

        if "state_class" in f:
            fields += (
                f"\n\t\tstate_class=FieldStateClass.{str(f["state_class"]).upper()},"
            )

        if "device_class" in f:
            fields += (
                f"\n\t\tdevice_class=DeviceClass.{str(f["device_class"]).upper()},"
            )

        if "length" in f and f["content"] == "string":
            fields += f"\n\t\tlength={f["length"]},"

        if "length" in f and f["content"] != "string":
            fields += f"\n\t\tcount={f["length"]},"

        # TODO enum building
        if "options" in f:
            fields += f"\n\t\tenum_type={to_camel_case(f["options"])},"

        fields += "\n\t)"

    content = f"""from ..base_devices import BluettiDevice
from ..fields import field, FieldType
from ..fields.field_extras import FieldCategory, FieldStateClass, DeviceClass
from ..enums import *

# GENERATED FILE! DO NOT EDIT!

class {name}(BluettiDevice):
    {fields}
"""

    with open(output + file_name, "w") as f:
        f.write(content)
