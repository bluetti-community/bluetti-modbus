# Testing on real hardware (no coding experience required)

This project has no static per-model register map baked in from a datasheet. Every field this
library and its downstream integrations expose was confirmed by someone with the real device
comparing raw Modbus values against BLUETTI's own official register list and/or the Bluetti app.
That means **you don't need to write code, or even know Python, to make a real contribution** -
you need a device, a network connection to it, and a bit of patience. An AI assistant (ChatGPT,
Claude, or similar) can write and explain every script below for you - this guide includes
ready-to-use prompts for exactly that.

If you have a device model this project doesn't support yet, or you've noticed a sensor showing
a wrong/missing/impossible value, this guide walks you through gathering the evidence that turns
"something's wrong" into a fixable bug report or a mergeable PR.

## What you'll need

- The device's IP address on your local network (check the Bluetti app's device settings, or your
  router's connected-devices list).
- A computer on the *same* local network as the device (Modbus TCP, port 502, isn't routable over
  the internet - this has to be a phone hotspot, home Wi-Fi, whatever network the device itself is
  on).
- Python 3.10 or newer.

## 1. Install Python and this library

### Windows 11

1. Open the **Microsoft Store**, search for "Python 3.12", click **Install**.
2. Open **PowerShell** (Start menu -> type "PowerShell") and confirm it worked:
   ```
   python --version
   ```
3. Install this library with its CLI tool:
   ```
   pip install "bluetti-modbus[cli]"
   ```

### Linux / macOS

1. Python 3 is usually already installed:
   ```
   python3 --version
   ```
2. Install this library with its CLI tool (add `--user` if a global install is refused):
   ```
   pip3 install "bluetti-modbus[cli]"
   ```
   (on Windows the command is `python`/`pip`; on Linux/macOS it's usually `python3`/`pip3` - the
   rest of this guide uses `python`/`pip`, swap in the `3` if that's what your system needs)

## 2. Try the built-in reader first

`bluetti-modread` connects to a device and prints every field it knows how to decode - it's the
fastest way to see what's already working and what isn't:

```
bluetti-modread -c <device-ip> -p 502 -t balco260
```

Replace `balco260` with `ep2000` or `smeter` if that's your device (see the main
[README](README.md) for a sample of what the output looks like). If a beta profile for your
device exists on a branch (check open issues/PRs first), you can point pip at that branch instead
of a released version, e.g.:

```
pip install --force-reinstall "bluetti-modbus[cli] @ git+https://github.com/bluetti-community/bluetti-modbus@ac500-beta"
```

If this runs cleanly and every value looks sane compared to the Bluetti app, there may be nothing
to report. If a field is missing, obviously wrong (huge, negative-when-it-shouldn't-be, or
frozen), or the whole thing errors out (including "Illegal Data Address" - normal for a
device/model that doesn't have that register at all), keep going below.

## 3. Cross-checking a value you don't trust

Three complementary techniques, all used repeatedly to find and fix real bugs in this project:

**a) Compare against the official register spec.** BLUETTI publishes their own register list at
[bluetti-official/bluetti-modbus-tcp-slave][official-spec] (`doc/Bluetti-Open-Modbus-TCP-register-list.xlsx`).
Find the row for the address you're looking at (address, register count, data type, value range,
remarks, unit) and compare it against what this library currently does for that field - the
[naming convention doc][bluetti-registers-naming] shows how field names map to what the schema
declares.

**b) Compare against the Bluetti app at the same instant.** Open the app, note the value it shows
(power, SOC, whatever), and read the same field within a few seconds using `bluetti-modread` or a
raw scan (below). If they don't match even roughly, something in the decode is wrong - wrong
scale, wrong sign, or wrong width.

**c) Cross-check mathematically between related fields.** If a device has a single active
inverter, its "total" power reading and that one inverter's own reading must be *exactly* equal -
not approximately. This project used exactly that identity to prove a field the official spec
calls "uint" was actually signed: a live reading of 64325 on the single-inverter field, and -1211W
on the (already-confirmed-signed) total field at the same instant, are only explainable if 64325
is *also* meant to be read as a signed 16-bit value (64325 - 65536 = -1211). If you have two
fields that should mathematically match, use that instead of guessing.

## 4. Scanning raw registers directly

For a Balco 260 - or any device of the Balco family - there is a ready-made, read-only probe in
this repository: [`script/probe_unexplored_registers.py`](script/probe_unexplored_registers.py).
It reads one register per request, backs off and checks the device is still alive after every
timeout, and records in its own docstring what each block answered so far. Two runs are worth
knowing about:

```
pip install "modbus-connection[tmodbus]" "tmodbus[async-serial]"
python3 probe_unexplored_registers.py --host <device-ip>                                 # registers a Balco 260 is not documented to have
python3 probe_unexplored_registers.py --host <device-ip> --sweep-units --max-timeouts 0  # which Modbus slave ids answer, and with which pack
python3 probe_unexplored_registers.py --host <device-ip> --pack-block 1,41,42            # the whole pack block at those ids, side by side
```

The second one is what settles the multi-pack question (README, "Multiple battery packs"): on a
Balco 260 with BC260 packs it prints, per slave id, the pack type, serial number, voltage, current,
SOC, SOH and cycle count that id serves. The third reads every field of the pack block (the same
ones the built-in pack reports at slave 1) at the ids the sweep found, decoded the way the library
decodes them - the check that an id serves a *whole* pack, not just a few registers. Stop anything
else polling the device first (the Home Assistant integration entry in particular - disable it,
re-enable it afterwards).

**Not on an AC500 or an EP500Pro.** On a real AC500 (bluetti-registers#13, 2026-09-19) a
single-register read at any unit id other than 1 - 2, 41 to 46, 250 - got no reply and **froze the
unit's Modbus TCP stack until a power cycle**; disabling and re-enabling Modbus TCP on the web
page did not bring it back, and the same reads done by hand, without the probe, froze it again. An
EP500Pro given the same requests the same day answered them with silence and took new requests on
a fresh TCP connection - less severe, still nothing gained: nothing answered at those unit ids. A
Balco 260 shrugs an unknown unit id off; this family does not. Pass `--device ac500` (or
`ep500pro`): the probe then uses a liveness register that family serves (50001 is not one) and
refuses `--sweep-units`, `--pack-block`, `--unit` and every block that addresses another unit id.
Unit-1 reads of unserved *addresses* are fine there - both AC500 testers' scans got clean
"illegal data address" answers - so the plain run still works. Write your own scan for one of
these? Same rule: `unit_id=1`, nothing else.

When you need something the probe doesn't cover - a suspected wrong address, a field that isn't
mapped at all yet, or hunting for something new (a switch, a missing sensor) - a small scanning
script beats guessing. Here's a template (an AI assistant can adapt this for you - see the prompts
below):

```python
import asyncio
import sys

from tmodbus import create_async_tcp_client
from tmodbus.exceptions import TModbusError

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.128"
PORT = 502
START = 50995  # change to the address range you want to inspect
END = 51010


async def main() -> None:
    client = create_async_tcp_client(HOST, PORT, unit_id=1)
    async with client:
        for addr in range(START, END + 1):
            try:
                value = await client.read_holding_registers(addr, 1)
                print(f"{addr}: {value[0]}")
            except TModbusError as e:
                print(f"{addr}: no response ({e})")


asyncio.run(main())
```

Save it as `scan.py` (requires `pip install tmodbus`, already installed if you did step 1) and run:

```
python scan.py <device-ip>
```

Run it more than once, and ideally while changing something observable (toggling a switch in the
app, starting/stopping charging) - a register that changes in response is a strong signal you've
found the right one, the way `bluetti-community/bluetti-modbus-tcp-slave#5` found `dc_o_switch` at
address 57005 by toggling DC output and watching which register flipped.

**Keep scans to one register per request.** The template above does, and that is deliberate.
On a real Balco 260 (2026-09-14, 57 addresses outside its documented range) the device
answered every *1-register* read of an address it doesn't serve with a clean "illegal data
address" exception - 57 out of 57 - while every *2-register* read of one that was tried (7 out
of 7) got **no reply at all**. The link wasn't broken: the same device answered register 50001 immediately after each
of those silences. So a timeout while scanning unknown addresses is how this firmware says
"not here" to a multi-register request, not a sign the device is stuck - and a scan that reads
two registers at a time will look like a string of link failures while learning nothing. Read
a 32-bit field as two separate 1-register reads and combine the words yourself: the lower
address holds the low word (`value = word[addr] + word[addr + 1] * 65536`), which is what
every 32-bit field in this library assumes and what BLUETTI's own register list calls
"little-end storage".

This is also why "no response" in the template's output is worth splitting when you report it:
a Modbus exception means the address is confirmed unserved; a timeout means you probably asked
for more than one register.

## 5. What the device's own web page knows (mDNS name, Modbus TCP status, firmware)

Every BLUETTI device that speaks Modbus TCP also serves its own local web page - the
"Bluetti Manager" you used to turn Modbus TCP on. That page is not a static site: it talks
to the device over a WebSocket, as JSON messages, and those messages carry things the Modbus
registers never expose - the device's mDNS hostname, whether Modbus TCP is enabled and on
which port, firmware versions, network status. Reading them takes nothing but a browser.

This is how two things in this project were settled: the S Meter's `getConfig`/`getVersion`
messages (which the Home Assistant integration now uses during discovery), and the Balco 260's
mDNS *hostname* (`blhems-<MAC>`, from `getNetworkStatusRsp`) turning out to be a different thing
from the mDNS *service name* ("Bluetti HEMS") that discovery actually matches on.

### How

1. Open `http://<device-ip>/` in a desktop browser and open the developer tools **before**
   logging in (F12, or right-click → Inspect). Go to the **Network** tab and set its filter to
   **WS** (WebSocket).
2. Log in (`admin`, your BLUETTI app account password - blank if you never set one). A single
   WebSocket connection appears in the list, to `ws://<device-ip>/8`. Click it, then open its
   **Messages** tab (Firefox: **Response**).
3. Walk through the page - the network status page, Settings → Modbus TCP, the firmware/about
   page. Each screen sends a request like `{"type": "getConfig", "data": {}}` and gets a
   `{"type": "getConfigRsp", "data": {...}}` back. Known so far:
   - `getConfigRsp` → `data.modbus_tcp.enable` / `.port` (S Meter: confirmed; this is what the
     integration checks before offering a discovered S Meter)
   - `getVersionRsp` → `data.firmwares[].version`
   - `getNetworkStatusRsp` → `data.mdns_hostname`, plus IP/MAC details (Balco 260: confirmed)

   On a Balco 260 the connection needs the token the page obtains at login - which is why you
   log in through the page rather than scripting it; the S Meter answers without any.
4. Copy the frames you want to report (right-click a message → Copy). **Redact** serial numbers,
   MAC addresses and the login token before posting.

Read only. Do not script writes against this API: it is undocumented, unconfirmed by BLUETTI,
and can change or disappear with a firmware update - which is also why the integration only
ever uses it best-effort, never as a requirement.

### What it tells you, and what it doesn't

The hostname in `getNetworkStatusRsp` is the device's *DNS* name. Home Assistant's discovery
matches on the mDNS *service instance name*, which is announced separately and can look
nothing like it (Balco 260: hostname `blhems-<MAC>`, service `_http._tcp` "Bluetti HEMS"). So
for a new model, report both:

- the WebSocket messages above (types and `data` keys, values redacted);
- an actual mDNS browse from a machine on the same network:
  `avahi-browse -rt _bluetti._tcp` and `avahi-browse -rt _http._tcp` (Linux),
  `dns-sd -B _bluetti._tcp` / `dns-sd -B _http._tcp` (macOS), or a few lines of
  python-zeroconf on the Home Assistant host (an AI assistant can write them). No result on
  both service types means the device does not announce itself at all (the AC200L2, for one)
  and is added by hand.

Where to send it: [hassio-bluetti-modbus issues](https://github.com/bluetti-community/hassio-bluetti-modbus/issues)
- both discovery and what the device's web page reports are Home Assistant integration
matters, not register data.

## 6. Don't have this exact model? Adapt a similar one

If your device shares a protocol family with one already supported (BLUETTI's AC500 and Balco260
share most of the same "EBOX" register layout, for example), the fastest path is usually:

1. Start from the closest existing device's field list (e.g. `src/bluetti_modbus_lib/devices/balco260.py`).
2. Query each address manually with a Modbus TCP client (a phone app works fine, or the scan
   script above) and drop any address that comes back "Illegal Data Address" on your device.
3. Iterate on the rest - some fields will need a different scale, width, or sign; some may need to
   move or disappear entirely.

This is exactly how AC500 support started (`bluetti-registers#13`): a user pruned Balco260's
register list down to what their AC500 actually answered, refined it with ChatGPT's help, and
reported back the open questions.

## 7. Using an AI assistant

You do not need to already know Python, Modbus, or this codebase - an AI assistant genuinely
can write and explain all of the above for you, and interpret the raw numbers you get back. Below
are four prompts you can copy, fill in, and paste as-is.

**Prompt: write me a scan script**
```
I have a Bluetti [MODEL] (a home battery/inverter system) that speaks Modbus TCP on port 502.
I want to scan a range of "holding registers" to see what values come back, using Python and the
`tmodbus` library (pip install tmodbus).

Please write me a short async Python script that:
- Connects to my device at IP <MY_DEVICE_IP>, port 502, unit_id=1
- Reads holding registers one at a time from address <START> to <END>
- Prints "ADDRESS: VALUE" for each one that responds, and "ADDRESS: no response (error message)"
  for ones that don't (catch tmodbus.exceptions.TModbusError)
- Uses create_async_tcp_client from tmodbus

Keep it simple, no retries needed.
```

**Prompt: help me interpret a raw value**
```
I'm working on an open-source Modbus integration for a Bluetti battery/inverter
(bluetti-community on GitHub). I read a Modbus holding register and the raw value doesn't make
sense as-is - I want help figuring out the correct decoding.

- Register address: <ADDRESS>
- Register count (consecutive 16-bit registers this field spans): <COUNT>
- Raw register value(s), in order: <RAW_VALUES, e.g. [64336, 65535]>
- What the official Bluetti register spec says the type is: <e.g. "uint">
- What I expect the decoded value to represent right now, and why (e.g. from the Bluetti app or a
  known device state): <e.g. "inverter power in Watts; the app shows it's charging at ~1200W, so
  I'd expect roughly -1200">

Walk me through decoding this as signed vs. unsigned, 16-bit vs. 32-bit, little-endian word order
(first register = low 16 bits), and tell me which interpretation actually matches what I expect.
```

**Prompt: help me compare against the official spec**
```
I'm cross-checking a Modbus register field for a Bluetti [MODEL] against BLUETTI's own official
register list. Here's the row from their spec (address, register count, name, data type, range,
remarks, unit):

<PASTE THE SPEC ROW HERE>

And here's what's currently used in the code / what I decoded:

<PASTE THE CURRENT FIELD DEFINITION OR DECODED VALUE HERE>

Does this match the spec? If not, what's the discrepancy and how should it be fixed?
```

**Prompt: help me write a good GitHub issue**
```
I found what looks like a bug in a Bluetti Modbus register decoding (or a missing/wrong sensor)
in an open-source project (bluetti-community on GitHub). Help me write a clear, well-organized
GitHub issue including:
- My device model and firmware versions
- The specific register address(es) and field name involved
- The raw values I read, and the exact commands/script I used to get them
- What I expected to see (e.g. from the Bluetti app) vs. what the integration currently shows
- Any relevant excerpt from the official register spec

Here's my raw notes/data - please turn it into a clean issue report:
<PASTE YOUR NOTES, SCREENSHOTS DESCRIPTIONS, RAW SCAN OUTPUT, ETC. HERE>
```

## 8. What makes a great report

Two real examples from this project's history, worth reading before you post:

- [bluetti-registers#13][ac500-registers-issue] - a user with no prior familiarity with this
  codebase pruned Balco260's field list down to what their AC500 actually answered, used ChatGPT
  to build a working configuration, and reported back a precise, numbered list of open questions.
  That single issue became the seed of AC500 support.
- [bluetti-modbus-tcp-slave#5][ac500-modread-issue] - the resulting back-and-forth: real register
  scans, raw hex dumps, repeated `bluetti-modread` runs after each fix, and one contributor asking
  ChatGPT to explain a serial number's word-order encoding on the spot. Every fix in that thread
  was driven by a specific number someone actually read off their device, not a guess.

What made both of those reports actionable, and what to aim for in yours:

- **Specific numbers, not descriptions.** "It shows 65205W" beats "the power looks wrong."
- **Multiple readings across different states** (charging vs. idle, one device turned off vs. on)
  - a value that's wrong in one specific way often reveals itself by *how* it changes.
- **Firmware versions** (`bluetti-modread` prints `d_ver_arm`/`d_ver_dsp`/etc.) - behavior can
  differ across firmware, so this narrows down whether a fix applies to everyone.
- **What you expected and why** - the Bluetti app's own display is the usual ground truth.

## Where to report it

- **A specific field's value/type/address/scale is wrong, or a field is missing** ->
  [bluetti-registers issues][bluetti-registers-issues] (this is the source of truth every other
  repo generates from).
- **A whole device model isn't supported, or the library's connection/decoding logic itself is
  broken** -> [bluetti-modbus issues][bluetti-modbus-issues] (this repo).
- **The Home Assistant integration itself misbehaves** (entities not created, wrong platform,
  crash in HA logs) even though the raw values are correct -> [hassio-bluetti-modbus
  issues][hassio-issues].

Not sure which? Open it wherever's easiest - a maintainer will move it if needed.

[official-spec]: https://github.com/bluetti-official/bluetti-modbus-tcp-slave
[bluetti-registers-naming]: https://github.com/bluetti-community/bluetti-registers
[bluetti-registers-issues]: https://github.com/bluetti-community/bluetti-registers/issues
[bluetti-modbus-issues]: https://github.com/bluetti-community/bluetti-modbus/issues
[hassio-issues]: https://github.com/bluetti-community/hassio-bluetti-modbus/issues
[ac500-registers-issue]: https://github.com/bluetti-community/bluetti-registers/issues/13
[ac500-modread-issue]: https://github.com/bluetti-official/bluetti-modbus-tcp-slave/issues/5
