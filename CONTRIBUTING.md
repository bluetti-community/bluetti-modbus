# Contributing

Contributions - bug reports, fixes, new fields, device coverage - are welcome.

## Before you start

- `src/bluetti_modbus_lib/devices/balco260.py` and `ep2000.py` are
  **generated** from [bluetti-registers][bluetti-registers] by `import.py`
  (see the `GENERATED FILE! DO NOT EDIT!` header at the top of each). A
  [scheduled workflow](.github/workflows/sync-devices.yml) already keeps them
  in sync weekly - if a field is wrong, missing, or misnamed, the fix belongs
  in `bluetti-registers`, not here. Everything else in `src/` is regular,
  hand-maintained code.
- This library is read-only by design (see the README's Architecture
  section) - it decodes what a device reports, it does not write control
  registers. A PR adding write support is a bigger design conversation worth
  opening an issue for first.
- `bluetti_modbus_lib.devices.*` (Balco260/EP2000/SMeter) is the integration
  surface other applications should build on; `bluetti_modbus_lib.modbus`
  (`BluettiModbusClient`) exists only for the `bluetti-modread` CLI and
  standalone/manual use.
- EP2000 support is currently spec-derived: BLUETTI's own official register
  list confirms the register map (see `bluetti-registers`' provenance for
  each field), but it isn't yet verified against real EP2000 hardware - the
  original removal's report of a closed port 502 on one specific unit
  ([bluetti-official/bluetti-home-assistant#125][ep2000-issue]) is still
  unexplained. If you have an EP2000 and can confirm it actually answers
  Modbus TCP, that report is exactly the kind of real-world confirmation
  this project values.

## Setting up a development environment

Python 3.13+, plain `venv` + `pip` (no Poetry, no Node tooling):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[cli]"
```

## Running the checks

```bash
script/run_checks.sh
```

This installs whatever's still missing and runs exactly what CI runs:
`ruff format --check`, `ruff check`, `mypy --strict`, and the test suite with
**100% coverage required** (`pytest --cov-fail-under=100`) - a PR that drops
coverage won't pass CI.

To auto-fix formatting and safe lint issues instead of just checking:

```bash
script/format_code.sh
```

## Tests

New behavior needs a test. `tests/` mirrors `src/bluetti_modbus_lib/` one
file per module; `modbus_connection`'s own mock connection
(`modbus_connection.mock`) is what the existing tests use to simulate a
device without real hardware - follow that pattern rather than hand-rolling
mocks.

## Submitting a change

Open a pull request against `main`. Keep it focused - a real device-coverage
fix and an unrelated refactor are two PRs, not one. CI (`tests.yml`) has to
be green before merge.

[bluetti-registers]: https://github.com/bluetti-community/bluetti-registers
[ep2000-issue]: https://github.com/bluetti-official/bluetti-home-assistant/issues/125
