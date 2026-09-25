import requests

tag = "0.0.48"
url = f"https://github.com/bluetti-community/bluetti-registers/releases/download/{tag}/modbus-tcp.json"

output = "src/bluetti_modbus_lib/devices/"

print("Loading devices list schema")

schema = requests.get(url).json()


def to_camel_case(snake_str):
    return "".join(x.capitalize() for x in snake_str.lower().split("_"))


def get_type(t: str, name: str, device_name: str):
    upper = t.upper()

    if upper == "BOOL":
        return "UINT16"

    # A device serial number, spanning 4 registers as a little-endian uint64
    # - same PR as above.
    if upper == "SERIAL":
        return "UINT64"

    if upper != "UINT" and upper != "INT":
        return upper

    # These 3 share field names (and the 32-bit widening below) with
    # Balco260, where they're genuinely 2-register values confirmed on real
    # hardware - but a 3-run register scan against a real AC500
    # (bluetti-registers#13, ac500_Modbus_Registers_3_runs.csv) never once
    # found the "+1" register (50003/50005/50007) responding, only the base
    # address - and reading the pair as a block times out entirely on that
    # same unit (bluetti-official/bluetti-modbus-tcp-slave#5). Scoped to
    # AC500 and only these 3 names, not a blanket override: the same field
    # names' widening is still correct on Balco260/EP2000, and AC500's
    # other WIDE_UINT_FIELDS members (ac_o_e_total, g_o_e_total, ...)
    # aren't known to have this problem.
    if (
        device_name in SINGLE_REGISTER_TOTALS_DEVICES
        and name in AC500_SINGLE_REGISTER_OVERRIDES
    ):
        return "INT16" if upper == "INT" else "UINT16"

    if upper == "INT":
        return "INT32" if name in WIDE_INT_FIELDS else "INT16"

    if name in ["b_i_e", "b_o_e", *WIDE_UINT_FIELDS]:
        return "UINT32"

    return "UINT16"


AC500_SINGLE_REGISTER_OVERRIDES = {
    "ac_o_p_total",
    "pv_i_p_total",
    "g_i_p_total",
}
# AC200L (confirmed on a real unit, bluetti-community/bluetti-modbus#76)
# shares AC500's register layout for these three, read as single registers
# against the same unit's BLE readings - and, like AC500, has no official
# register list to confirm the "+1" register from. EP500P (read on two real
# units with the AC500 profile, bluetti-registers#35) carries AC500's
# overrides for the same reason.
SINGLE_REGISTER_TOTALS_DEVICES = {"AC500", "AC200L", "EP500P"}

# Devices whose fields are read one isolated block each rather than batched
# with max_gap=5 (see the register_ranges step below): AC500 - and AC200L,
# which has no official register list either, and on which widening a read
# across an unconfirmed address took the coordinator down in exactly the
# same way during its own development (bluetti-modbus#76). EP500P: same
# situation - AC500's register set read on a unit BLUETTI's list doesn't
# cover, and a 50-register batch (the EP2000 profile) timed out on it
# (bluetti-registers#35).
# Balcotrans (the Balco Transfer Hub) for a reason of its own, caught in a
# Home Assistant diagnostics dump of the raw blocks (bluetti-registers#29):
# it answers a block read with a word inserted partway through, and the
# rest of the block shifted one register late. Asked for 5 registers at
# 50210 it returned [63089, 4584, 2, 7550, 4585] where reading the same
# addresses one at a time gives [63089, 4584, 7550, 4585, 499] - so the
# DSP version decoded from a 2 and the grid frequency from the DSP's high
# word, 458.5 Hz. The device does not refuse the read and the count is
# right, which is why nothing failed loudly. Every reading that ever
# matched the app was taken field by field.
ISOLATED_RANGE_DEVICES = {"AC500", "AC200L", "EP500P", "Balcotrans"}

# Devices whose settings block (57001 and up) is read as runs of adjacent
# declared registers, never bridged across an undeclared one, while the
# data area below keeps its normal gap-based batching. On the Balco family
# a block that touches a register the device does not serve gets no reply
# at all (bluetti-registers, "unserved registers"), and FP declares
# dc_o_switch at 57005 - within max_gap of both 57001 and 57009 - so the
# default planner fused 57001-57010 into one read that timed out on a real
# FridgePower and kept it out of Home Assistant (bluetti-community/
# hassio-bluetti-modbus#127). Balco260/Balco500 only escape this because
# their settings registers happen to sit more than max_gap apart.
SETTINGS_BLOCK_START = 57001
ISOLATED_SETTINGS_DEVICES = {"FP"}


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
#
# ac_o_p_total/pv_i_p_total/pv_ac_p/ac_o_e_total/pv_i_e_total/g_i_e_total/
# g_o_e_total/pv_ac_e added against the official Cassandra register list
# (bluetti-official/bluetti-modbus-tcp-slave's own
# doc/Bluetti-Open-Modbus-TCP-register-list.xlsx) - the same "Inverter
# Summary Information" 50002-50020 block g_i_p_local's own siblings sit in,
# previously never checked against that document for these specific names.
# g_i_p_local itself moved to WIDE_INT_FIELDS below - the official sheet
# documents it signed, not unsigned.
WIDE_UINT_FIELDS = {
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
    "ac_o_p_total",
    "pv_i_p_total",
    "pv_ac_p",
    "ac_o_e_total",
    "pv_i_e_total",
    "g_i_e_total",
    "g_o_e_total",
    "pv_ac_e",
}

# Signed 32-bit equivalent of WIDE_UINT_FIELDS above - bluetti-registers
# documents these as content "int", not "uint", per the same official
# Cassandra register list. Real-world trigger: a live Balco260 diagnostics
# dump showed d_inverter_total decode to 64923 (impossible for this device
# class) while charging - a single-register unsigned read of what's
# actually a 2-register signed value that goes negative in that mode.
WIDE_INT_FIELDS = {
    "g_i_p_total",
    "d_inverter_total",
    "g_i_p_local",
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

# Per-device override of BluettiDevice's default max_span=50 (max registers
# per single block read) - real Balco260 hardware failed twice, months
# apart, on the same naturally-batched 31-register block (50001-50031):
# once as a cancelled request, once as a malformed/truncated response
# (bluetti-community/bluetti-modbus#46's own read-plan investigation; see
# that PR's sibling issue for the real tracebacks). BluettiDevice's own
# docstring already notes "this device's Modbus TCP stack is known to
# become unresponsive under load" - not address-specific, so this narrows
# every large block, not just the one that happened to get reported.
# Chosen with real headroom below the failing 31 (splits it into 20+11)
# without fragmenting reads too far (10 blocks become 15) - not proven to
# be the exact safe threshold, just a well-margined starting point pending
# extended real-hardware monitoring (see this branch's PR description).
# FP (FridgePower) shares the Balco 260's register set and IoT module and
# answered the Balco 260 plan - built with this same override - in full on
# real hardware (bluetti-registers#38); it keeps the override rather than
# being the first Balco-family device read with 50-register blocks.
# Balcotrans (the Balco Transfer Hub): 10, and that one is measured rather
# than prudent. On a real hub the 15-register block this profile used to
# ask for came back correct for its first ten registers - the type string
# and the serial number, matching the device's own web page - and wrong for
# everything past them: both firmware versions and the grid frequency, at
# offsets 10 to 14, read values the same registers never return when they
# are read one at a time (bluetti-registers#29). The device answers, it
# just stops serving real data after the tenth register of a block.
MAX_SPAN_OVERRIDES = {"Balco260": 20, "FP": 20, "Balcotrans": 10}

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
        t=FieldType.{get_type(str(f["content"]), f["name"], name)},
        address={f["address"]},"""

        # "writeable" is a real protocol fact bluetti-registers' own schema
        # already carries - not something invented here. Bounded ones get a
        # probatio validator instead of a bare True, so an out-of-range
        # write is rejected before it ever reaches the device.
        #
        # Balco260 and AC500 only for now, even though EP2000 shares (and
        # adds to) the same writeable fields in the schema - EP2000 is still
        # spec-derived, not verified against real hardware (see the
        # README), and writing to an unconfirmed device's control
        # registers is a materially bigger risk than reading from it.
        # AC500's ac_o_switch/dc_o_switch are each independently confirmed
        # writable on real hardware by a different tester (see
        # bluetti-official/bluetti-modbus-tcp-slave#5) - g_i_switch isn't
        # (confirmed non-functional there instead), so it no longer carries
        # writeable: true in the schema at all.
        # AC200L: dc_o_switch write confirmed on real hardware by its owner,
        # ac_o_switch writeable at that owner's explicit request
        # (bluetti-modbus#76); its b_soc_low/b_soc_high carry no writeable
        # flag in the schema at all (bluetti-registers' AC200L overrides).
        # EP500P: ac_o_switch/dc_o_switch switch the outputs on real hardware
        # (bluetti-registers#35, its second owner); b_soc_low/b_soc_high
        # refuse a write there and g_i_switch's effect is unseen, so the
        # schema carries no writeable flag for those (EP500P overrides).
        if name in ("Balco260", "AC500", "AC200L", "EP500P", "FP") and f.get(
            "writeable"
        ):
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

        if "length" in f and f["content"] in ("string", "string_swapped"):
            fields += f"\n        length={f['length']},"

        if "length" in f and f["content"] not in ("string", "string_swapped"):
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

    max_span_line = ""
    if name in MAX_SPAN_OVERRIDES:
        max_span_line = f"    max_span = {MAX_SPAN_OVERRIDES[name]}\n\n"

    content = f"""{range_import}from ..base_devices import BluettiDevice
from ..enums import *
from ..fields import FieldType, {fields_import}

# GENERATED FILE! DO NOT EDIT!


class {name}(BluettiDevice):
{max_span_line}{fields.lstrip(chr(10))}
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
    if name in ISOLATED_RANGE_DEVICES or name in ISOLATED_SETTINGS_DEVICES:
        import importlib

        # Imported (not read from a standalone file location) so its own
        # relative imports (`from ..base_devices import ...`) resolve
        # normally - this script only runs against an editable/installed
        # checkout (see sync-devices.yml/python-publish.yml), so the
        # package is always importable here.
        module = importlib.import_module(
            "bluetti_modbus_lib.devices." + file_name.removesuffix(".py")
        )
        module = importlib.reload(module)
        instance = getattr(module, name)(None)
        if name in ISOLATED_RANGE_DEVICES:
            ranges = sorted(
                {
                    (field.address, field.address + field.count - 1)
                    for field in (instance.get_field(n) for n in instance.field_names())
                }
            )
        else:
            # ISOLATED_SETTINGS_DEVICES: the data area's ranges are the
            # blocks the planner builds on its own (so those reads do not
            # change), the settings block is split into runs of adjacent
            # declared registers - 57009-57010 stay one read, 57005 is
            # read alone rather than fused with its unserved neighbours.
            ranges = [
                (start, start + count - 1)
                for start, count in instance._build_plan().blocks["holding"]
                if start < SETTINGS_BLOCK_START
            ]
            settings = sorted(
                address
                for field in (instance.get_field(n) for n in instance.field_names())
                for address in range(field.address, field.address + field.count)
                if field.address >= SETTINGS_BLOCK_START
            )
            for address in settings:
                if (
                    ranges
                    and ranges[-1][1] == address - 1
                    and ranges[-1][0] >= SETTINGS_BLOCK_START
                ):
                    ranges[-1] = (ranges[-1][0], address)
                else:
                    ranges.append((address, address))
        ranges_literal = "".join(f"\n        ({lo}, {hi})," for lo, hi in ranges)
        with open(output + file_name, encoding="utf-8") as f:
            regenerated = f.read()
        regenerated = regenerated.replace(
            f"class {name}(BluettiDevice):\n",
            f"class {name}(BluettiDevice):\n    register_ranges = ({ranges_literal}\n    )\n\n",
        )
        with open(output + file_name, "w", encoding="utf-8") as f:
            f.write(regenerated)
