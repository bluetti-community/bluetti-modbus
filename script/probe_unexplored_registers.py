#!/usr/bin/env python3
"""Probe a Balco 260 for Modbus registers it is not documented to have.

Reads, one field at a time, registers outside BLUETTI's official Balco 260
list and reports which ones answer with data, which read as zero, and which
the device rejects. Strictly read-only (FC 0x03 only). Its blocks:

- The EP2000 blocks (summary-ext, per-phase, der-status, ems-control,
  battery-control): every register bluetti-registers declares for EP2000 but
  not for Balco 260. Probed on a real Balco 260 on 2026-09-14: all 57 came
  back "illegal data address". Kept here to re-run after a firmware update.
- The internal-v2 block: the device's own internal register space - the one
  the BLUETTI app speaks over BLE ("ProtocolAddrV2", tabulated from app
  v3.0.9 by https://github.com/mikemccllstr/voltkeeper). The Modbus TCP
  slave demonstrably translates documented writes into that space (a Write
  Single Register to 57016 is confirmed at 2022 - see bluetti-modbus's
  BluettiDevice.write); this block asks whether it also *serves* that space
  to a TCP client. Six of its entries are settings whose values are known
  through documented registers (2022 <-> 57016 and so on), so the script
  reads both and prints them side by side: matching values would mean the
  internal space is reachable, and every other entry becomes worth reading;
  "illegal data address" on all of them closes the question. Probed on a
  real Balco 260 on 2026-09-16: all 54 came back "illegal data address" -
  the slave translates documented writes into that space but does not
  serve it. Kept for the same reason as the EP2000 blocks. Only readable
  registers are listed - the app's write-only ones (control events, power
  off, factory reset, OTA start) are left out even though FC 0x03 could not
  trigger them.
- The balco-set block (opt-in, --blocks balco-set): not unexplored at all -
  one register from each block of BLUETTI's own BalcoXX register list, plus
  its five writable registers. For a device that is in the Balco family but
  is not a Balco 260 (a Balco Transfer Hub, a Balco 500), it maps which of
  the documented blocks the firmware actually serves, one safe request per
  block, before anyone points a full Balco 260 profile at it. A Transfer Hub
  (2026-09-17) answered a single-register read of an unserved address with
  silence rather than the Balco 260's "illegal data address", so on such a
  device run this with --max-timeouts 0: every timeout is still followed by
  a reconnect and a liveness check, which stops the run on its own if the
  device really has stopped answering.
- The pack-41 block (opt-in, --blocks pack-41): the app addresses battery
  packs of 2nd-generation IoT home systems at Modbus slave 41 and up. Over
  TCP, packs are documented at slave 2..N and the aggregate summary at 250,
  so this is a long shot; an unknown slave id most likely times out, which
  the recovery below handles.
- The inv-31, pack-91 and pack-92 blocks (opt-in): the app's own slave ids
  for a balcony system (app 3.1.4, ConnConstantsV2: DC/DC at 1, inverter at
  31, packs at 91 and up) - not the home-system ids the pack-41 block tries.
  Each reads a documented register (50002, 51219, 51221) plus one internal
  pack address at that slave id, so the answer separates "the slave routes
  documented registers per unit" from "it serves the internal pack space
  there": on a Balco 260 whose packs 2 and up read as zero at the documented
  slave ids (bluetti-modbus#55), a pack answering at 91 would be the lead.
  Run on a one-pack Balco 260 on 2026-09-17: slave 91 and slave 92 both
  answered 51219/51221 with the pack's own voltage and SOC (26.9 V, 69 %),
  slave 31 answered 50002 and 1100 with "illegal data address", and 6000
  was illegal at 91 and 92 - the slave id is honoured, documented pack
  registers are served at 91+, the internal space is not. Whether 92 is
  "pack 2, falling back to pack 1" or "any id from 91 up is the pack block"
  is what the sweep below is for.
- The sweep (--sweep-units, optionally with an explicit list of ids): one
  register from each documented block (50001, 50219, 51001, 53011), the
  pack's type and serial number (51200, 51206) and its voltage, current,
  SOC, SOH and cycle count (51219-51223) at every slave id in the list, so a run shows which blocks each id serves and, on
  a system with two packs or more, which ids return *different* packs - a
  BC260 at its own id should read "BC260" and its own serial number, where
  an alias of the aggregate view repeats the built-in pack's "Balco260".
  The default list is sized for the largest supported system, a Balco 260
  with five BC260 packs: the documented-by-assumption ids 2-6, BLUETTI's
  41-46 (one past the last possible pack, to see an empty slot), the app's
  balcony ids 91-96, plus 1, 31, 90 and 250 - 21 ids, about four minutes
  on a device that rejects unknown addresses quickly. --sweep-units alone
  probes only the sweep; add --blocks to probe other blocks in the same
  run. Run on the same
  one-pack Balco 260 on 2026-09-17: slave 1 serves all six (51001 as 0,
  the known "count only at 250" rule); 2 and 3 serve 50219 (the per-inverter
  PV charging power) and the pack block as zeros and reject 50001/53011 -
  they look like inverter slots; 31 and 41 serve the pack block as zeros and
  reject the rest - 41 being an empty expansion slot, per BLUETTI's answer
  that expansion packs answer at 41 and up; 90-94 and 250 all answer
  51001 = 1 and the pack's own 51219/51221 (250 alone also serves 50001, as
  0) and reject the rest, i.e. 90-94 look like aliases of the aggregate
  view. Only a system with two packs or more can show pack 2 at 42 (or
  anywhere else) - that run is what bluetti-modbus#55 is waiting for.
  First multi-pack run, 2026-09-17, a Balco 260 with two BC260 attached:
  slave 41 answered the pack block as zeros *except the serial number* -
  a real one, different from the built-in pack's and with a different
  prefix - while 42-46 were all zeros and the pack count at 250 read 1;
  90-96 and 250 repeated the built-in pack field for field (serial
  included), which settles those as aliases of the aggregate view. So 41
  is where an expansion pack lives, but the device was counting no pack
  beyond the built-in one at that moment - whether the packs were asleep,
  off or not recognised is the open question, to be rerun with the packs
  known to be active in the app. Settled 2026-09-18 on a Balco 260 with
  three BC260 packs: 42 and 43 answered the whole block with each pack's
  own type ("BC260"), serial, voltage, SOC, SOH, cycle count, firmware and
  energies, 250 counted 4 - the packs are at 41 and up, as BLUETTI said;
  41 on that unit, and on a second unit with no pack attached, served a
  serial number and zeros for everything else (a pack the inverter knows
  but that is not reporting) - see the library's pack_is_reporting().
- The pack block (--pack-block 1,41,42): the follow-up to a sweep, on the
  ids that answered with a pack - every field of the "Each Pack Base
  Information" block (51200-51249) as the library declares it for a Balco
  260, read at each id and printed side by side, decoded the way the
  library decodes it (type, serial number, firmware versions, voltage,
  current, SOC, SOH, cycle count, cell/NTC counts, energies, protection
  and alarm words). Include slave 1: that is the built-in pack, the
  reference every other column should differ from field by field if the id
  really serves another pack. 36 registers per id, about half a minute
  each.

Requires only the library the integration already uses:

    pip install "modbus-connection[tmodbus]"

Run it from a machine on the same LAN as the device:

    python3 probe_unexplored_registers.py --host 192.168.1.50
    python3 probe_unexplored_registers.py --host 192.168.1.50 --sweep-units --max-timeouts 0

Before running, disable the Bluetti Modbus integration entry in Home
Assistant (or stop anything else polling the device): the Balco 260 accepts
very few simultaneous Modbus TCP connections, and a second poller is the
known way to get its Modbus stack stuck.

What "safe" means here, and why each guard exists:

- One *register* per request, never a multi-register read of an unknown
  address. Confirmed on a real Balco 260 (2026-09-14, 11 unknown fields):
  every 1-register read of an unserved address came back as a clean
  "illegal data address" exception, and every 2-register read of one got
  no reply at all (a timeout, with the device otherwise alive) - the same
  behaviour behind the AC500's isolated-block read plan. So a multi-word
  field is read word by word here and reassembled (--batched restores the
  single request, to reproduce that timeout deliberately).
- Requests are paced (--delay) through modbus-connection's own
  message_spacing, and the connection is kept open for the whole run - a
  fresh connection per read is the pattern that has made this device
  unresponsive under load before.
- A timeout or a corrupted reply is treated as "the link may be stuck": the
  link is dropped, re-opened after --recover-delay, and a known-good
  register (50001, Number of Inverters) is re-read to confirm the device is
  still answering. After --max-timeouts of those in a row the run stops
  rather than keep hammering the device.
- "Illegal data address" is the benign, expected answer for a register the
  firmware doesn't serve, and just gets recorded.

Nothing here writes to the device.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime

from modbus_connection import ModbusTcpParams
from modbus_connection.exceptions import (
    IllegalDataAddressError,
    ModbusConnectionError,
    ModbusDesyncError,
    ModbusError,
    ModbusExceptionError,
    ModbusProtocolError,
    ModbusTimeoutError,
)
from modbus_connection.tmodbus import ModbusConnection

# Register 50001 "Number of Inverters" (uint, 1~10) is in every Balco 260's
# documented range - used as the liveness check before probing and after
# every link recovery.
SANITY_ADDRESS = 50001
SANITY_RANGE = range(1, 11)

# (name, address, register count, what declares it, unit, block)
#
# The EP2000 blocks: every field bluetti-registers declares for EP2000 but not
# for Balco 260 (modbus-tcp/ep2000.json vs modbus-tcp/balco260.json,
# 2026-09-14), "what declares it" being the field's type there. None of
# these is in BLUETTI's official BalcoXX register list.
#
# The internal-v2 and pack-41 blocks: the app's ProtocolAddrV2 constant for
# that address (see the module docstring); one register each, since the
# question is only whether the address is served at all - a block that
# answers can be read wider afterwards. The inv-31/pack-91/pack-92 blocks mix
# both: the official register list's name for a documented address, the
# ProtocolAddrV2 constant for an internal one.
CANDIDATES: list[tuple[str, int, int, str, str, str]] = [
    ("d_manufacturer", 50032, 16, "string", "", "summary-ext"),
    ("d_reactive_p_total", 50048, 2, "int", "", "summary-ext"),
    ("d_apparent_p_total", 50050, 2, "int", "", "summary-ext"),
    ("b_p", 50052, 2, "uint", "W", "summary-ext"),
    ("d_rated_p_max", 50054, 2, "int", "", "summary-ext"),
    ("d_rated_p_max_continuous", 50056, 2, "int", "", "summary-ext"),
    ("d_rated_va_max_continuous", 50058, 2, "int", "", "summary-ext"),
    ("d_rated_var_max_continuous", 50060, 2, "int", "", "summary-ext"),
    ("d_rated_var_max_continuous_neg", 50062, 2, "int", "", "summary-ext"),
    ("d_rated_pf_min_over_excited", 50064, 2, "int", "", "summary-ext"),
    ("d_rated_pf_min_under_excited", 50066, 2, "int", "", "summary-ext"),
    ("d_online_component", 50068, 1, "uint", "", "summary-ext"),
    ("d_rated_v", 50069, 1, "uint", "V", "summary-ext"),
    ("d_rated_f", 50070, 1, "uint", "Hz", "summary-ext"),
    ("g_1_p_active", 50288, 2, "uint", "W", "per-phase"),
    ("g_2_p_active", 50290, 2, "uint", "W", "per-phase"),
    ("g_3_p_active", 50292, 2, "uint", "W", "per-phase"),
    ("g_1_p_reactive", 50294, 2, "uint", "W", "per-phase"),
    ("g_2_p_reactive", 50296, 2, "uint", "W", "per-phase"),
    ("g_3_p_reactive", 50298, 2, "uint", "W", "per-phase"),
    ("g_1_p_apparent", 50300, 2, "uint", "W", "per-phase"),
    ("g_2_p_apparent", 50302, 2, "uint", "W", "per-phase"),
    ("g_3_p_apparent", 50304, 2, "uint", "W", "per-phase"),
    ("d_inverter_1_p_active_internal", 50306, 2, "uint", "W", "per-phase"),
    ("d_inverter_2_p_active_internal", 50308, 2, "uint", "W", "per-phase"),
    ("d_inverter_3_p_active_internal", 50310, 2, "uint", "W", "per-phase"),
    ("d_hw_ver", 50400, 2, "string", "", "der-status"),
    ("d_p_active", 50402, 1, "uint", "W", "der-status"),
    ("d_p_reactive", 50403, 1, "uint", "W", "der-status"),
    ("d_f", 50404, 1, "uint", "Hz", "der-status"),
    ("d_operational_mode_status", 50405, 1, "uint", "", "der-status"),
    ("d_connection_status", 50406, 1, "uint", "", "der-status"),
    ("d_alarm_status", 50407, 1, "uint", "", "der-status"),
    ("d_inverter_der_status", 50408, 1, "uint", "", "der-status"),
    ("d_local_control_mode_status", 50409, 1, "uint", "", "der-status"),
    ("d_storage_mode_status", 50410, 1, "uint", "", "der-status"),
    ("d_ems_ctrl", 57030, 1, "uint", "", "ems-control"),
    ("d_p_active_target_l1", 57032, 2, "uint", "W", "ems-control"),
    ("d_p_active_target_l2", 57034, 2, "uint", "W", "ems-control"),
    ("d_p_active_target_l3", 57036, 2, "uint", "W", "ems-control"),
    ("d_p_reactive_target_l1", 57038, 2, "uint", "W", "ems-control"),
    ("d_p_reactive_target_l2", 57040, 2, "uint", "W", "ems-control"),
    ("d_p_reactive_target_l3", 57042, 2, "uint", "W", "ems-control"),
    ("d_p_apparent_target_l1", 57044, 2, "uint", "W", "ems-control"),
    ("d_p_apparent_target_l2", 57046, 2, "uint", "W", "ems-control"),
    ("d_p_apparent_target_l3", 57048, 2, "uint", "W", "ems-control"),
    ("d_p_output_level_pct", 57050, 1, "uint", "W", "ems-control"),
    ("d_p_limit_timeout", 57051, 1, "uint", "W", "ems-control"),
    ("d_p_limit_ramp_time", 57052, 1, "uint", "W", "ems-control"),
    ("d_p_limit_ramp_rate_pct", 57053, 1, "uint", "W", "ems-control"),
    # Patrick762 calls this one d_control_mode, with enum AppControl=0,
    # SCM=11, Standby=12, ForceCharge=13, ForceDischarge=14 (his
    # bluetti-registers commit 2c56877 / bluetti-modbus-lib 282fefd).
    # Not served on a real Balco 260 (2026-09-14: illegal data address).
    ("d_battery_control", 57503, 1, "uint", "", "battery-control"),
    ("d_export_limit", 57504, 2, "uint", "W", "battery-control"),
    ("d_storage_set_point", 57506, 2, "uint", "W", "battery-control"),
    ("d_op_mod_connect", 57508, 1, "uint", "", "battery-control"),
    ("d_op_mod_gen_lim_w", 57509, 2, "uint", "W", "battery-control"),
    ("d_op_mod_load_lim_w", 57511, 2, "uint", "W", "battery-control"),
    ("d_ramp_rate", 57513, 1, "uint", "", "battery-control"),
    # Validation first: settings whose value is known through a documented
    # register - see CROSS_CHECK.
    ("v2_ac_switch", 2011, 1, "AC_SWITCH", "", "internal-v2"),
    ("v2_dc_switch", 2012, 1, "DC_SWITCH", "", "internal-v2"),
    ("v2_sys_low_power", 2022, 1, "SYS_LOW_POWER", "%", "internal-v2"),
    ("v2_sys_high_power", 2023, 1, "SYS_HIGH_POWER", "%", "internal-v2"),
    ("v2_ctrl_grid", 2207, 1, "CTRL_GRID", "", "internal-v2"),
    ("v2_ctrl_feed", 2208, 1, "CTRL_FEED", "", "internal-v2"),
    # Then what would be worth having if the space is served.
    ("v2_base_config", 1, 1, "BASE_CONFIG", "", "internal-v2"),
    ("v2_app_home_data", 100, 1, "APP_HOME_DATA", "", "internal-v2"),
    ("v2_inv_base_info", 1100, 1, "INV_BASE_INFO", "", "internal-v2"),
    ("v2_inv_pv_info", 1200, 1, "INV_PV_INFO", "", "internal-v2"),
    ("v2_inv_grid_info", 1300, 1, "INV_GRID_INFO", "", "internal-v2"),
    ("v2_inv_load_info", 1400, 1, "INV_LOAD_INFO", "", "internal-v2"),
    ("v2_inv_inv_info", 1500, 1, "INV_INV_INFO", "", "internal-v2"),
    ("v2_inv_meter_info", 1700, 1, "INV_METER_INFO", "", "internal-v2"),
    ("v2_inv_meter_settings", 1900, 1, "INV_METER_SETTINGS", "", "internal-v2"),
    ("v2_inv_base_settings", 2000, 1, "INV_BASE_SETTINGS", "", "internal-v2"),
    ("v2_system_time", 2001, 1, "SYSTEM_TIME", "", "internal-v2"),
    ("v2_working_mode", 2005, 1, "WORKING_MODE", "", "internal-v2"),
    ("v2_charging_mode", 2020, 1, "CHARGING_MODE", "", "internal-v2"),
    ("v2_super_power_mode", 2021, 1, "CTRL_SUPER_POWER_MODE", "", "internal-v2"),
    ("v2_soc_holding_low", 2075, 1, "SOC_HOLDING_LOW", "%", "internal-v2"),
    ("v2_pack_num_set_show", 2080, 1, "PACK_NUM_SET_SHOW", "", "internal-v2"),
    ("v2_inv_num_set", 2081, 1, "INV_NUM_SET", "", "internal-v2"),
    ("v2_soc_holding_high", 2083, 1, "SOC_HOLDING_HIGH", "%", "internal-v2"),
    ("v2_inv_advance_settings", 2200, 1, "INV_ADVANCE_SETTINGS", "", "internal-v2"),
    ("v2_inv_voltage", 2209, 1, "INV_VOLTAGE", "", "internal-v2"),
    ("v2_inv_freq", 2210, 1, "INV_FREQ", "", "internal-v2"),
    ("v2_grid_max_power", 2213, 1, "GRID_MAX_POWER", "W", "internal-v2"),
    ("v2_grid_max_current", 2214, 1, "GRID_MAX_CURRENT", "A", "internal-v2"),
    ("v2_feed_max_power", 2215, 1, "FEED_MAX_POWER", "W", "internal-v2"),
    ("v2_feed_max_current", 2216, 1, "FEED_MAX_CURRENT", "A", "internal-v2"),
    ("v2_grid_plus_mode", 2225, 1, "CTRL_GRID_PLUS_MODE", "", "internal-v2"),
    ("v2_ems_ctrl_mode", 2241, 1, "EMS_CTRL_MODE_SET", "", "internal-v2"),
    ("v2_meter_ctrl_grid", 2267, 1, "METER_CTRL_GRID", "", "internal-v2"),
    ("v2_multi_peak_enable", 2304, 1, "MULTI_PEAK_ENABLE", "", "internal-v2"),
    ("v2_log_history_info", 3000, 1, "LOG_HISTORY_INFO", "", "internal-v2"),
    ("v2_total_energy_info", 3500, 1, "INV_TOTAL_ENERGY_INFO", "", "internal-v2"),
    (
        "v2_curr_year_energy_info",
        3600,
        1,
        "INV_CURR_YEAR_ENERGY_INFO",
        "",
        "internal-v2",
    ),
    ("v2_time_ctrl_info", 5000, 1, "TIME_CTRL_INFO_START", "", "internal-v2"),
    ("v2_pack_main_info", 6000, 1, "PACK_MAIN_INFO", "", "internal-v2"),
    ("v2_pack_item_info", 6100, 1, "PACK_ITEM_INFO", "", "internal-v2"),
    ("v2_pack_settings_info", 7000, 1, "PACK_SETTINGS_INFO", "", "internal-v2"),
    ("v2_pack_bmu_info", 7200, 1, "PACK_BMU_INFO", "", "internal-v2"),
    ("v2_iot_base_info", 11000, 1, "IOT_BASE_INFO", "", "internal-v2"),
    ("v2_iot_settings_info", 12002, 1, "IOT_SETTINGS_INFO", "", "internal-v2"),
    ("v2_iot_matter_info", 13088, 1, "IOT_MATTER_INFO", "", "internal-v2"),
    ("v2_comm_soc_settings", 19000, 1, "COMM_SOC_SETTINGS", "", "internal-v2"),
    (
        "v2_comm_scheduled_chg_dsg",
        19200,
        1,
        "COMM_SCHEDULED_CHG_DSG",
        "",
        "internal-v2",
    ),
    ("v2_node_info", 21000, 1, "NODE_INFO", "", "internal-v2"),
    ("v2_tou_ctrl_enable", 26000, 1, "TOU_CTRL_ENABLE", "", "internal-v2"),
    ("v2_tou_ctrl", 26001, 1, "TOU_CTRL", "", "internal-v2"),
    ("v2_boot_software_info", 29772, 1, "BOOT_SOFTWARE_INFO", "", "internal-v2"),
    ("v2_active_info", 30001, 1, "ACTIVE_INFO", "", "internal-v2"),
    ("v2_comm_data_other", 40000, 1, "COMM_DATA_OTHER", "", "internal-v2"),
    # Opt-in - see OPT_IN_BLOCKS and the module docstring. One register from
    # each documented BalcoXX block ("what declares it" is the official
    # register list's own abbreviation), then the writable set.
    ("d_num_inverters", 50001, 1, "Number of Inverters", "", "balco-set"),
    ("ac_o_p_total", 50002, 1, "Total AC Output Power", "W", "balco-set"),
    ("d_serial", 50206, 1, "Inverter Serial Number (1st word)", "", "balco-set"),
    ("pv_i_p_local", 50219, 1, "PV Charging Power (Single)", "W", "balco-set"),
    ("d_num_battery_packs", 51001, 1, "Number of Packs", "", "balco-set"),
    ("b_soc_total", 51004, 1, "Total SOC", "%", "balco-set"),
    ("b_v", 51219, 1, "Pack Voltage", "V", "balco-set"),
    ("b_soc", 51221, 1, "Pack SOC", "%", "balco-set"),
    ("d_iot_serial", 53007, 1, "IOT Serial Number (1st word)", "", "balco-set"),
    ("d_iot_ver", 53011, 1, "IOT Version", "", "balco-set"),
    ("meter_status", 55111, 1, "AC Meter Status", "", "balco-set"),
    ("ac_o_switch", 57001, 1, "AC load output switch", "", "balco-set"),
    ("g_i_switch", 57009, 1, "AC grid charging switch", "", "balco-set"),
    ("g_o_switch", 57010, 1, "AC grid feed-in switch", "", "balco-set"),
    ("b_soc_low", 57016, 1, "Battery empty SOC threshold", "%", "balco-set"),
    ("b_soc_high", 57017, 1, "Battery full SOC threshold", "%", "balco-set"),
    ("pack41_main_info", 6000, 1, "PACK_MAIN_INFO", "", "pack-41"),
    ("pack41_item_info", 6100, 1, "PACK_ITEM_INFO", "", "pack-41"),
    ("pack41_settings_info", 7000, 1, "PACK_SETTINGS_INFO", "", "pack-41"),
    ("pack41_bmu_info", 7200, 1, "PACK_BMU_INFO", "", "pack-41"),
    ("inv31_ac_o_p_total", 50002, 1, "Total AC Output Power", "W", "inv-31"),
    ("inv31_base_info", 1100, 1, "INV_BASE_INFO", "", "inv-31"),
    ("pack91_b_v", 51219, 1, "Pack Voltage", "V", "pack-91"),
    ("pack91_b_soc", 51221, 1, "Pack SOC", "%", "pack-91"),
    ("pack91_main_info", 6000, 1, "PACK_MAIN_INFO", "", "pack-91"),
    ("pack92_b_soc", 51221, 1, "Pack SOC", "%", "pack-92"),
    ("pack92_main_info", 6000, 1, "PACK_MAIN_INFO", "", "pack-92"),
]

# internal-v2 address -> the documented register that holds the same setting,
# read right after it so the two values sit side by side in the output.
CROSS_CHECK: dict[int, tuple[int, str]] = {
    2011: (57001, "ac_o_switch"),
    2012: (57005, "dc_o_switch"),  # AC500 only - not served by a Balco 260
    2022: (57016, "b_soc_low"),
    2023: (57017, "b_soc_high"),
    2207: (57009, "g_i_switch"),
    2208: (57010, "g_o_switch"),
}

# Blocks read at a slave id other than --unit.
BLOCK_UNIT: dict[str, int] = {"pack-41": 41, "inv-31": 31, "pack-91": 91, "pack-92": 92}
# Blocks only probed when named explicitly in --blocks - see the docstring.
OPT_IN_BLOCKS = frozenset({"balco-set", *BLOCK_UNIT})

# Read at every slave id of a --sweep-units run: one register from each
# documented block, so an id that answers shows which blocks it serves -
# plus the pack's type and serial number, which say *which* pack an id
# serves: the built-in pack reads "Balco260" for b_type at the device's own
# slave id, so an expansion pack at its own id should read "BC260" and a
# serial number of its own, where a mere alias of the aggregate view repeats
# the built-in pack's.
# (name, address, register count, what declares it, unit)
SWEEP_FIELDS: list[tuple[str, int, int, str, str]] = [
    ("d_num_inverters", 50001, 1, "Number of Inverters", ""),
    ("pv_i_p_local", 50219, 1, "PV Charging Power (Single)", "W"),
    ("d_num_battery_packs", 51001, 1, "Number of Packs", ""),
    ("b_type", 51200, 6, "Pack Type", ""),
    ("b_serial", 51206, 4, "Pack Serial Number", ""),
    ("b_v", 51219, 1, "Pack Voltage", "V"),
    ("b_c", 51220, 1, "Pack Current", "A"),
    ("b_soc", 51221, 1, "Pack SOC", "%"),
    ("b_soh", 51222, 1, "Pack SOH", "%"),
    ("b_cycle_count", 51223, 1, "Pack Cycle Count", ""),
    ("d_iot_ver", 53011, 1, "IOT Version", ""),
]
DEFAULT_SWEEP_UNITS = "1,2,3,4,5,6,31,41,42,43,44,45,46,90,91,92,93,94,95,96,250"


def sweep_candidates(spec: str) -> list[tuple[str, int, int, str, str, str]]:
    """SWEEP_FIELDS at each slave id in spec, as blocks named sweep-<id>."""
    out: list[tuple[str, int, int, str, str, str]] = []
    for text in spec.split(","):
        if not text.strip():
            continue
        slave = int(text)
        block = f"sweep-{slave}"
        BLOCK_UNIT[block] = slave
        out += [
            (f"u{slave}_{name}", address, count, declared, unit, block)
            for name, address, count, declared, unit in SWEEP_FIELDS
        ]
    CANDIDATES.extend(out)
    return out


# The whole "Each Pack Base Information" block (51200-51249) as the library
# declares it for a Balco 260 - what battery_pack() reads for an expansion
# pack, and what the main device reads for its built-in one - for a
# --pack-block run: every field at each given slave id, decoded the way the
# library decodes it, side by side. (name, address, register count, kind)
PACK_BLOCK_FIELDS: list[tuple[str, int, int, str]] = [
    ("b_type", 51200, 6, "str"),
    ("b_serial", 51206, 4, "u64"),
    ("b_ver_count", 51210, 1, "u16"),
    ("b_ver_1", 51211, 2, "ver"),
    ("b_ver_2", 51213, 2, "ver"),
    ("b_ver_3", 51215, 2, "ver"),
    ("b_ver_4", 51217, 2, "ver"),
    ("b_v", 51219, 1, "0.1V"),
    ("b_c", 51220, 1, "cur"),
    ("b_soc", 51221, 1, "u16"),
    ("b_soh", 51222, 1, "u16"),
    ("b_cycle_count", 51223, 1, "u16"),
    ("b_cell_count", 51234, 1, "u16"),
    ("b_ntc_count", 51235, 1, "u16"),
    ("b_i_e", 51236, 2, "u32"),
    ("b_o_e", 51238, 2, "u32"),
    ("b_protect", 51240, 2, "u32"),
    ("b_error", 51242, 1, "u16"),
    ("b_alarm_residential", 51245, 1, "u16"),
    ("b_alarm_portable", 51246, 2, "u32"),
]


def pack_block_candidates(spec: str) -> list[tuple[str, int, int, str, str, str]]:
    """PACK_BLOCK_FIELDS at each slave id in spec, as blocks named packblock-<id>."""
    out: list[tuple[str, int, int, str, str, str]] = []
    for text in spec.split(","):
        if not text.strip():
            continue
        slave = int(text)
        block = f"packblock-{slave}"
        BLOCK_UNIT[block] = slave
        out += [
            (f"u{slave}_{name}", address, count, kind, "", block)
            for name, address, count, kind in PACK_BLOCK_FIELDS
        ]
    CANDIDATES.extend(out)
    return out


def _words_of(words_hex: str) -> list[int]:
    """The registers back from a record's words_hex ("6ab3 f24d 025f 0000")."""
    return [int(w, 16) for w in words_hex.split()]


def _decode_pack_value(kind: str, words: list[int]) -> str:
    """One pack-block value as the library would show it (little-endian words)."""
    raw = sum(w << (16 * i) for i, w in enumerate(words))
    if kind == "str":
        text = b"".join((w & 0xFFFF).to_bytes(2, "little") for w in words)
        return repr(text.decode("ascii", errors="replace").rstrip("\x00"))
    if kind == "ver":
        return f"{raw // 10000}.{(raw // 100) % 100:02d}.{raw % 100:02d}"
    if kind == "0.1V":
        return f"{raw / 10:.1f}V"
    if kind == "cur":
        # reference_offset_current(51220, reference=30000) in the library.
        return f"{abs(raw - 30000) / 10:.1f}A ({raw})"
    return str(raw)


CONTROL_MODE_NAMES = {
    0: "AppControl",
    11: "SCM",
    12: "Standby",
    13: "ForceCharge",
    14: "ForceDischarge",
}


def decode(words: list[int]) -> dict[str, object]:
    """Every plausible reading of the raw words - the Balco's real type is unknown."""
    out: dict[str, object] = {}
    w0 = words[0]
    out["uint16"] = w0
    out["int16"] = w0 - 0x10000 if w0 >= 0x8000 else w0
    if len(words) >= 2:
        # Little-endian word order is what bluetti_modbus_lib uses for every
        # 32-bit field ("Register Data principle: Little-end storage" in
        # BLUETTI's own spec) - the big-endian reading is shown only to make
        # a wrong assumption obvious.
        u32_le = words[0] | (words[1] << 16)
        u32_be = (words[0] << 16) | words[1]
        out["uint32_le"] = u32_le
        out["int32_le"] = u32_le - 0x1_0000_0000 if u32_le >= 0x8000_0000 else u32_le
        out["uint32_be"] = u32_be
    raw = b"".join((w & 0xFFFF).to_bytes(2, "little") for w in words)
    swapped = b"".join((w & 0xFFFF).to_bytes(2, "big") for w in words)
    out["ascii"] = raw.decode("ascii", errors="replace").rstrip("\x00")
    out["ascii_swapped"] = swapped.decode("ascii", errors="replace").rstrip("\x00")
    return out


def hexwords(words: list[int]) -> str:
    return " ".join(f"{w:04x}" for w in words)


class _PartiallyServed(Exception):
    """A multi-word field whose first word(s) answered but a later one didn't."""

    def __init__(self, words: list[int]) -> None:
        super().__init__(f"{len(words)} word(s) served before an illegal data address")
        self.words = words


class Prober:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.conn = ModbusConnection(
            ModbusTcpParams(host=args.host, port=args.port),
            timeout=args.timeout,
            message_spacing=args.delay,
        )
        self.unit = self.conn.for_unit(args.unit)
        self.units = {block: self.conn.for_unit(u) for block, u in BLOCK_UNIT.items()}
        self.consecutive_bad = 0
        self.results: list[dict[str, object]] = []

    async def sanity(self) -> bool:
        try:
            words = await self.unit.read_holding_registers(SANITY_ADDRESS, 1)
        except ModbusError as err:
            print(f"  liveness check failed: {type(err).__name__}: {err}")
            return False
        ok = words[0] in SANITY_RANGE
        print(
            f"  liveness check: register {SANITY_ADDRESS} = {words[0]} ({'ok' if ok else 'unexpected'})"
        )
        return ok

    async def recover(self) -> bool:
        """Drop and re-open the link, then confirm the device still answers."""
        print(
            f"  dropping the link and waiting {self.args.recover_delay}s before re-opening..."
        )
        try:
            await self.conn.disconnect()
        except ModbusError:
            pass
        await asyncio.sleep(self.args.recover_delay)
        try:
            await self.conn.connect()
        except ModbusError as err:
            print(f"  could not re-open the link: {type(err).__name__}: {err}")
            return False
        return await self.sanity()

    async def _read_words(self, address: int, count: int, block: str = "") -> list[int]:
        """One register per request unless --batched - see the module docstring."""
        unit = self.units.get(block, self.unit)
        if self.args.batched or count == 1:
            return await unit.read_holding_registers(address, count)
        words: list[int] = []
        for i in range(count):
            try:
                words += await unit.read_holding_registers(address + i, 1)
            except IllegalDataAddressError:
                if words:
                    raise _PartiallyServed(words) from None
                raise
        return words

    async def probe_one(
        self, name: str, address: int, count: int, content: str, unit: str, block: str
    ) -> bool:
        """Read one candidate. Returns False when the run should stop."""
        rec: dict[str, object] = {
            "name": name,
            "address": address,
            "count": count,
            "declared": content,
            "unit": unit,
            "block": block,
        }
        if block in BLOCK_UNIT:
            rec["slave_id"] = BLOCK_UNIT[block]
        label = f"{name:32s} {address:<6} x{count:<2}"
        try:
            words = await self._read_words(address, count, block)
        except IllegalDataAddressError:
            rec["status"] = "illegal-address"
            print(f"{label} -> not served (illegal data address)")
            self.consecutive_bad = 0
        except _PartiallyServed as err:
            rec["status"] = "partial"
            rec["words_hex"] = hexwords(err.words)
            rec["decoded"] = decode(err.words)
            print(
                f"{label} -> PARTIAL: {len(err.words)}/{count} word(s) served "
                f"[{rec['words_hex']}], the rest is an illegal data address"
            )
            self.consecutive_bad = 0
        except ModbusExceptionError as err:
            rec["status"] = f"modbus-exception:{type(err).__name__}"
            rec["error"] = str(err)
            print(f"{label} -> device exception {type(err).__name__}")
            self.consecutive_bad = 0
        except (ModbusTimeoutError, ModbusProtocolError, ModbusDesyncError) as err:
            rec["status"] = (
                "timeout" if isinstance(err, ModbusTimeoutError) else "protocol-error"
            )
            rec["error"] = str(err)
            self.consecutive_bad += 1
            limit = f"/{self.args.max_timeouts}" if self.args.max_timeouts else ""
            print(
                f"{label} -> {rec['status']} ({self.consecutive_bad}{limit} in a row)"
            )
            self.results.append(rec)
            if (
                self.args.max_timeouts
                and self.consecutive_bad >= self.args.max_timeouts
            ):
                print(
                    "  too many timeouts in a row - stopping so the device is left alone."
                )
                return False
            return await self.recover()
        except ModbusConnectionError as err:
            rec["status"] = "connection-error"
            rec["error"] = str(err)
            print(f"{label} -> connection error: {err}")
            self.results.append(rec)
            return await self.recover()
        else:
            self.consecutive_bad = 0
            words_hex = hexwords(words)
            decoded = decode(words)
            rec["words_hex"] = words_hex
            rec["decoded"] = decoded
            if any(words):
                rec["status"] = "data"
                extra = ""
                if name == "d_battery_control" and words[0] in CONTROL_MODE_NAMES:
                    extra = (
                        f"  (Patrick762's ControlMode: {CONTROL_MODE_NAMES[words[0]]})"
                    )
                print(
                    f"{label} -> DATA  [{words_hex}]  u16={words[0]}"
                    + (f" u32le={decoded['uint32_le']}" if count >= 2 else "")
                    + (f" ascii={decoded['ascii']!r}" if content == "string" else "")
                    + extra
                )
            else:
                rec["status"] = "zero"
                print(f"{label} -> zero  [{words_hex}]")
            if address in CROSS_CHECK:
                await self._cross_check(rec, address, words[0])
        self.results.append(rec)
        return True

    async def _cross_check(
        self, rec: dict[str, object], address: int, value: int
    ) -> None:
        """An internal-v2 address answered: read the documented register that
        holds the same setting and show both, so a match (or not) is visible
        on the spot rather than reconstructed from two runs.
        """
        doc_address, doc_name = CROSS_CHECK[address]
        try:
            (doc_value,) = await self.unit.read_holding_registers(doc_address, 1)
        except ModbusError as err:
            rec["cross_check"] = {
                "address": doc_address,
                "name": doc_name,
                "error": f"{type(err).__name__}: {err}",
            }
            print(
                f"{'':32s} documented {doc_name} ({doc_address}) could not be read: {err}"
            )
            return
        rec["cross_check"] = {
            "address": doc_address,
            "name": doc_name,
            "value": doc_value,
            "match": doc_value == value,
        }
        verdict = "SAME VALUE" if doc_value == value else "differs"
        print(
            f"{'':32s} documented {doc_name} ({doc_address}) = {doc_value} -> {verdict}"
        )

    async def run(self, candidates: list[tuple[str, int, int, str, str, str]]) -> int:
        print(
            f"connecting to {self.args.host}:{self.args.port} unit {self.args.unit} "
            f"(timeout {self.args.timeout}s, {self.args.delay}s between requests)"
        )
        try:
            await self.conn.connect()
        except ModbusError as err:
            print(f"could not connect: {type(err).__name__}: {err}")
            return 2
        try:
            if not await self.sanity():
                print(
                    "the device does not answer a register it is documented to have - not probing anything."
                )
                return 2
            print(f"\nprobing {len(candidates)} candidate fields, one request each\n")
            for i, cand in enumerate(candidates):
                if not await self.probe_one(*cand):
                    for name, address, count, content, unit, block in candidates[
                        i + 1 :
                    ]:
                        self.results.append(
                            {
                                "name": name,
                                "address": address,
                                "count": count,
                                "declared": content,
                                "unit": unit,
                                "block": block,
                                "status": "skipped",
                            }
                        )
                    break
            print("\nfinal liveness check")
            await self.sanity()
        finally:
            await self.conn.close()
        return 0

    def report(self) -> None:
        # The results file first: it is the point of the run, and a
        # formatting slip in the tables below must never cost it (it did
        # once - 2026-09-17, multi-register values in the sweep matrix).
        payload = {
            "device": "balco260",
            "host": self.args.host,
            "unit": self.args.unit,
            "probed_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "results": self.results,
        }
        with open(self.args.output, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"\nfull results written to {self.args.output}")
        by_status: dict[str, list[str]] = {}
        for r in self.results:
            by_status.setdefault(str(r["status"]), []).append(str(r["name"]))
        print("\n=== summary ===")
        for status, names in sorted(by_status.items()):
            print(f"  {status:22s} {len(names):3d}")
        if "data" in by_status or "partial" in by_status:
            print("\n=== fields that answered with non-zero or partial data ===")
            for r in self.results:
                if r["status"] in ("data", "partial"):
                    print(
                        f"  {r['name']:32s} {r['address']:<6} {r['status']:8s} [{r['words_hex']}]"
                    )
        sweep = [r for r in self.results if str(r["block"]).startswith("sweep-")]
        if sweep:
            print(
                "\n=== sweep: value per slave id (- illegal address, T timeout, ? other) ==="
            )
            rows: list[list[str]] = [
                ["slave"] + [str(a) for _, a, _, _, _ in SWEEP_FIELDS]
            ]
            for block in dict.fromkeys(str(r["block"]) for r in sweep):
                cells = [str(BLOCK_UNIT[block])]
                for name, address, count, _, _ in SWEEP_FIELDS:
                    hit = next(
                        (
                            r
                            for r in sweep
                            if r["block"] == block and r["address"] == address
                        ),
                        None,
                    )
                    if hit is None:
                        cells.append("")
                    elif hit["status"] == "data" and name == "b_type":
                        decoded = hit["decoded"]
                        assert isinstance(decoded, dict)
                        cells.append(repr(decoded["ascii"]))
                    elif hit["status"] in ("data", "zero"):
                        # Little-endian word order for the multi-register
                        # serial number, as bluetti_modbus_lib decodes it.
                        words = _words_of(str(hit["words_hex"]))
                        cells.append(
                            str(sum(w << (16 * i) for i, w in enumerate(words)))
                        )
                    elif hit["status"] == "partial":
                        cells.append("part")
                    elif hit["status"] == "illegal-address":
                        cells.append("-")
                    elif hit["status"] == "timeout":
                        cells.append("T")
                    else:
                        cells.append("?")
                rows.append(cells)
            widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
            for row in rows:
                print(
                    "  "
                    + " ".join(c.rjust(w) for c, w in zip(row, widths, strict=True))
                )
        packs = [r for r in self.results if str(r["block"]).startswith("packblock-")]
        if packs:
            print(
                "\n=== pack block per slave id (- illegal address, T timeout, ? other) ==="
            )
            blocks = list(dict.fromkeys(str(r["block"]) for r in packs))
            rows = [["field", "addr"] + [str(BLOCK_UNIT[b]) for b in blocks]]
            for name, address, count, kind in PACK_BLOCK_FIELDS:
                cells = [name, str(address)]
                for block in blocks:
                    hit = next(
                        (
                            r
                            for r in packs
                            if r["block"] == block and r["address"] == address
                        ),
                        None,
                    )
                    if hit is None:
                        cells.append("")
                    elif hit["status"] in ("data", "zero"):
                        words = _words_of(str(hit["words_hex"]))
                        cells.append(_decode_pack_value(kind, words))
                    elif hit["status"] == "partial":
                        cells.append("part")
                    elif hit["status"] == "illegal-address":
                        cells.append("-")
                    elif hit["status"] == "timeout":
                        cells.append("T")
                    else:
                        cells.append("?")
                rows.append(cells)
            widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
            for row in rows:
                print(
                    "  "
                    + row[0].ljust(widths[0])
                    + " "
                    + " ".join(
                        c.rjust(w) for c, w in zip(row[1:], widths[1:], strict=True)
                    )
                )
        print(f"\n(full results in {self.args.output})")


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--host", help="IP address of the Balco 260")
    p.add_argument("--port", type=int, default=502)
    p.add_argument("--unit", type=int, default=1, help="Modbus unit id (default 1)")
    p.add_argument(
        "--timeout", type=float, default=5.0, help="seconds to wait for each reply"
    )
    p.add_argument("--delay", type=float, default=0.5, help="seconds between requests")
    p.add_argument(
        "--recover-delay",
        type=float,
        default=5.0,
        help="seconds to leave the device alone after a timeout before reconnecting",
    )
    p.add_argument(
        "--max-timeouts",
        type=int,
        default=3,
        help="stop after this many timeouts/corrupted replies in a row; 0 means never "
        "stop for that reason alone (each timeout is still followed by a reconnect "
        "and a liveness check, which stops the run if the device no longer answers)",
    )
    p.add_argument(
        "--blocks",
        help="comma-separated subset of blocks to probe: "
        + ",".join(sorted({c[5] for c in CANDIDATES}))
        + f" ({','.join(sorted(OPT_IN_BLOCKS))} only when named here)",
    )
    p.add_argument(
        "--sweep-units",
        nargs="?",
        const=DEFAULT_SWEEP_UNITS,
        metavar="IDS",
        help="read one register from each documented block at every one of these "
        f"comma-separated slave ids (default list: {DEFAULT_SWEEP_UNITS}); alone, "
        "probes only the sweep - see the module docstring",
    )
    p.add_argument(
        "--pack-block",
        metavar="IDS",
        help='read the whole "Each Pack Base Information" block (51200-51249, every '
        "field the library reads for a pack) at each of these comma-separated slave "
        "ids and print them side by side, decoded - the follow-up to a sweep, on the "
        "ids that answered; alone, probes only that",
    )
    p.add_argument(
        "--only",
        help="comma-separated field names and/or addresses to probe, nothing else "
        "(e.g. d_battery_control,57504,d_hw_ver)",
    )
    p.add_argument(
        "--skip",
        help="comma-separated field names and/or addresses to leave out "
        "(e.g. g_1_p_active,50290)",
    )
    p.add_argument(
        "--output",
        default=None,
        help="JSON results file (default: probe-balco260-<timestamp>.json)",
    )
    p.add_argument(
        "--batched",
        action="store_true",
        help="read a multi-word field in one request, the way the library does - on a "
        "Balco 260 this gets no reply at all for an unserved address (see the module docstring)",
    )
    p.add_argument(
        "--list",
        action="store_true",
        help="print the candidate fields and exit, without connecting",
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help="skip the 'is Home Assistant stopped?' confirmation",
    )
    args = p.parse_args(argv)
    if args.output is None:
        args.output = f"probe-balco260-{datetime.now().astimezone().strftime('%Y%m%d-%H%M%S')}.json"
    return args


def _selector(spec: str) -> set[str]:
    """'a,50288, b' -> {'a', '50288', 'b'}: a field name or an address, as typed."""
    return {s.strip() for s in spec.split(",") if s.strip()}


def _matches(cand: tuple[str, int, int, str, str, str], selector: set[str]) -> bool:
    return cand[0] in selector or str(cand[1]) in selector


def select_candidates(
    args: argparse.Namespace,
) -> list[tuple[str, int, int, str, str, str]]:
    """Apply --blocks, then --only, then --skip, in that order."""
    candidates = [c for c in CANDIDATES if c[5] not in OPT_IN_BLOCKS]
    if args.blocks or args.sweep_units or args.pack_block:
        wanted = _selector(args.blocks) if args.blocks else set()
        candidates = [c for c in CANDIDATES if c[5] in wanted]
    if args.sweep_units:
        candidates += sweep_candidates(args.sweep_units)
    if args.pack_block:
        candidates += pack_block_candidates(args.pack_block)
    if args.only:
        only = _selector(args.only)
        candidates = [c for c in candidates if _matches(c, only)]
        unknown = only - {c[0] for c in CANDIDATES} - {str(c[1]) for c in CANDIDATES}
        if unknown:
            print(
                f"warning: --only names nothing in the candidate list: {sorted(unknown)}"
            )
    if args.skip:
        skip = _selector(args.skip)
        candidates = [c for c in candidates if not _matches(c, skip)]
    return candidates


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    candidates = select_candidates(args)
    if not candidates:
        print("nothing left to probe after --blocks/--only/--skip")
        return 2
    if args.list:
        cur = None
        for name, address, count, content, unit, block in candidates:
            if block != cur:
                cur = block
                at = f" (slave id {BLOCK_UNIT[block]})" if block in BLOCK_UNIT else ""
                print(f"\n[{block}]{at}")
            print(f"  {name:32s} {address:<6} x{count:<2} {content:7s} {unit}")
        print(f"\n{len(candidates)} candidate fields")
        return 0
    if not args.host:
        print("--host is required (or use --list)")
        return 2
    if not args.yes:
        print(
            "The Balco 260 accepts very few simultaneous Modbus TCP connections.\n"
            "Disable the Bluetti Modbus integration entry in Home Assistant (and stop\n"
            "anything else polling this device) before continuing."
        )
        if (
            input("Is nothing else polling the device right now? [y/N] ")
            .strip()
            .lower()
            != "y"
        ):
            return 1
    prober = Prober(args)
    rc = asyncio.run(prober.run(candidates))
    prober.report()
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
