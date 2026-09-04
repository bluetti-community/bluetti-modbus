import requests

# Beta: bluetti-registers' ac500-beta branch, tagged ac500-beta-7 - not a
# real bluetti-registers release. See devices/ac500.py's own generated-file
# note and this branch's PR description for why AC500 stays off main until
# ItsMe00007/gjniewenhuijse confirm it against real hardware. beta-2 fixed
# g_i_f's scale; beta-3 added ac_o_switch; beta-4 added g_i_switch,
# g_o_switch, dc_o_switch (all confirmed working on real AC500 hardware,
# bluetti-official/bluetti-modbus-tcp-slave#5); beta-5 merged in
# bluetti-registers' main (b_ver_count) so Balco260/EP2000 don't regress
# when regenerating from this beta tag - that merge also silently widened
# g_i_p_local/ac_o_p_local/pv_i_p_local/pv_i_e_local to 2 registers on
# AC500 (correct for Balco260, unverified for AC500); beta-6 reverted
# those 4 back to 1 register after a real-hardware timeout reading the +1
# address; beta-7 removes pv_3/pv_4 - BLUETTI's own AC500 manual documents
# only 2 DC PV inputs on this model.
tag = "ac500-beta-7"
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

    # A device serial number, spanning 4 registers as a little-endian uint64
    # - same PR as above.
    if upper == "SERIAL":
        return "UINT64"

    if upper != "UINT" and upper != "INT":
        return upper

    if upper == "INT":
        return "INT16"

    if name in ["b_i_e", "b_o_e", *WIDE_UINT_FIELDS]:
        return "UINT32"

    return "UINT16"


# bluetti-registers documents each of these as spanning 2 registers
# (MULTI_REGISTER_FIELD_LENGTHS in that repo's fields.py), same as b_i_e/
# b_o_e above - but field()'s UINT16 branch never actually reads the second
# register (the `count` it's given is silently dropped, only ENUM/STRING
# fields use it), so every one of these has been decoding only the low
# 16 bits since bluetti-registers#6759c94 first documented the wider width.
# Correct for a typical reading that fits in 16 bits (the dropped high word
# is 0), silently wrong for any value that doesn't.
#
# Scoped to fields real Balco260 hardware has (EP2000 shares these same
# names/addresses - see test_ep2000_shares_balco260s_confirmed_addresses -
# so they're fixed there too "for free"), deliberately excluding EP2000-only
# multi-register uint fields (g_1_p_active, d_p_active_target_l1, d_export_
# limit, etc.) - those are SunSpec/DER-style registers, which commonly pack
# a mantissa and a separate scale factor rather than one plain wide integer,
# and EP2000 is still spec-derived, unconfirmed hardware (see the README) -
# widening them the same way as these confirmed Balco260 fields would be a
# guess, not a verified fix. b_error (length 3) is also left alone: there's
# no 3-register FieldType, and it's an already-undecoded raw bitmap with no
# displayed value to verify a fix against.
WIDE_UINT_FIELDS = {
    "g_i_p_local",
    "ac_o_p_local",
    "pv_i_p_local",
    "pv_ac_p_local",
    "g_i_e_local",
    "g_o_e_local",
    "ac_o_e_local",
    "pv_i_e_local",
    "pv_ac_e_local",
    "b_protect",
    "b_alarm_portable",
}


# Fields whose real decode is not a plain scaled register and are built by
# name below instead of through the generic field(t=..., ...) call - see
# reference_offset_current()'s own docstring for why b_c needs this.
REFERENCE_OFFSET_CURRENT_FIELDS = {"b_c": 30000}

# Single documented bit inside an otherwise-"reserved" register - see
# bit_flag()'s own docstring. d_status (55111, S Meter): bit0/1 reserved,
# bit2 online status (bluetti-registers#14 / the official Cassandra Protocol
# register list's own remark on that address).
BIT_FLAG_FIELDS = {"d_status": 2}

# Documented 4-bit nibble inside an otherwise packed register - see
# nibble()'s own docstring. pv_dc_count/pv_ac_count (Balco260/EP2000, both
# 50267, "PV connection quantity per inverter"): bit0-3/bit4-7 respectively,
# per the official register spec's own remark on that address.
# name -> is the high nibble (bit4-7), not the low one (bit0-3).
NIBBLE_FIELDS = {"pv_dc_count": False, "pv_ac_count": True}

for d in schema:
    name = d["name"]
    file_name = str(name).lower() + ".py"
    fields = ""
    uses_reference_offset_current = False
    uses_dotted_version = False
    uses_dotted_version_2part = False
    uses_bit_flag = False
    uses_nibble = False
    uses_range = False

    for f in d["fields"]:
        if f["name"] in REFERENCE_OFFSET_CURRENT_FIELDS:
            uses_reference_offset_current = True
            reference = REFERENCE_OFFSET_CURRENT_FIELDS[f["name"]]
            fields += f"""
    {f["name"]} = reference_offset_current({f["address"]}, reference={reference})
"""
            continue

        # Every "version" content field shares the same encoding (major*10000
        # + minor*100 + patch) - see dotted_version()'s own docstring. Applies
        # by content type, not by name, since bluetti-registers already tags
        # every such field uniformly.
        if str(f["content"]).upper() == "VERSION":
            uses_dotted_version = True
            fields += f"""
    {f["name"]} = dotted_version({f["address"]})
"""
            continue

        # 2-part "major*100 + minor" version - a different encoding than
        # "VERSION" above, confirmed so far only on AC500 (bluetti-
        # registers#13) - see dotted_version_2part()'s own docstring.
        if str(f["content"]).upper() == "VERSION2":
            uses_dotted_version_2part = True
            fields += f"""
    {f["name"]} = dotted_version_2part({f["address"]})
"""
            continue

        if f["name"] in BIT_FLAG_FIELDS:
            uses_bit_flag = True
            bit = BIT_FLAG_FIELDS[f["name"]]
            fields += f"""
    {f["name"]} = bit_flag({f["address"]}, bit={bit})
"""
            continue

        if f["name"] in NIBBLE_FIELDS:
            uses_nibble = True
            high = NIBBLE_FIELDS[f["name"]]
            fields += f"""
    {f["name"]} = nibble({f["address"]}, high={high})
"""
            continue

        fields += f"""
    {f["name"]} = field(
        t=FieldType.{get_type(str(f["content"]), f["name"])},
        address={f["address"]},"""

        # "writeable" is a real protocol fact bluetti-registers' own schema
        # already carries - not something invented here. Bounded ones get a
        # probatio validator instead of a bare True, so an out-of-range
        # write is rejected before it ever reaches the device.
        #
        # Balco260 only for now, even though EP2000 shares (and adds to)
        # the same writeable fields in the schema - EP2000 is still
        # spec-derived, not verified against real hardware (see the
        # README), and writing to an unconfirmed device's control
        # registers is a materially bigger risk than reading from it.
        if name == "Balco260" and f.get("writeable"):
            if "num_min" in f and "num_max" in f:
                uses_range = True
                fields += (
                    f"\n        writable=Range(min={f['num_min']}, max={f['num_max']}),"
                )
            else:
                fields += "\n        writable=True,"

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

    extra_imports = []
    if uses_reference_offset_current:
        extra_imports.append("reference_offset_current")
    if uses_dotted_version:
        extra_imports.append("dotted_version")
    if uses_dotted_version_2part:
        extra_imports.append("dotted_version_2part")
    if uses_bit_flag:
        extra_imports.append("bit_flag")
    if uses_nibble:
        extra_imports.append("nibble")
    # ruff (isort) sorts a module's names alphabetically within one import -
    # match that here so the generated file doesn't fail lint every time.
    fields_import = ", ".join(sorted(["field", *extra_imports]))
    # ruff (isort) groups a third-party import above and separate from this
    # package's own relative ones, with a blank line between the groups.
    range_import = "from probatio import Range\n\n" if uses_range else ""

    content = f"""{range_import}from ..base_devices import BluettiDevice
from ..enums import *
from ..fields import FieldType, {fields_import}

# GENERATED FILE! DO NOT EDIT!


class {name}(BluettiDevice):
{fields.lstrip(chr(10))}
"""

    with open(output + file_name, "w", encoding="utf-8") as f:
        f.write(content)

    # AC500 needs every field read as its own isolated block: real hardware
    # testing (bluetti-community/bluetti-modbus#45, comment on bluetti-
    # official/bluetti-modbus-tcp-slave#5) showed BluettiDevice's default
    # max_gap=5 block-batching still merges several of AC500's fields into
    # one combined read spanning addresses this device gives no evidence
    # for (e.g. 50010, confirmed "Illegal Data Address" per bluetti-
    # registers#13) - the whole batch then times out even though every
    # individually-declared field is fine on its own. register_ranges
    # declares exactly the addresses each field actually reads, so
    # modbus_connection's planner can never bridge across an address this
    # device has no evidence for. Introspected from the freshly generated
    # class rather than re-derived by hand here, so it can't drift from
    # whatever field()/uint16()/etc. actually build.
    if name == "AC500":
        import importlib

        # Imported (not read from a standalone file location) so its own
        # relative imports (`from ..base_devices import ...`) resolve
        # normally - this script only runs against an editable/installed
        # checkout (see sync-devices.yml/python-publish.yml), so the
        # package is always importable here.
        module = importlib.import_module("bluetti_modbus_lib.devices.ac500")
        module = importlib.reload(module)
        instance = module.AC500(None)
        ranges = sorted(
            {
                (field.address, field.address + field.count - 1)
                for field in (instance.get_field(n) for n in instance.field_names())
            }
        )
        ranges_literal = "".join(f"\n        ({lo}, {hi})," for lo, hi in ranges)
        with open(output + file_name, encoding="utf-8") as f:
            regenerated = f.read()
        regenerated = regenerated.replace(
            f"class {name}(BluettiDevice):\n",
            f"class {name}(BluettiDevice):\n    register_ranges = ({ranges_literal}\n    )\n\n",
        )
        with open(output + file_name, "w", encoding="utf-8") as f:
            f.write(regenerated)
