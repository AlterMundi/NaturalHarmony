# Natural Harmony Task List

## Current Status
- Branch objective: complete refactor cleanup and align docs/tests with implementation.
- Runtime critical mock crash fix: done.
- Test suite modernization: done for `tests/`.
- Documentation alignment: in progress.

## Completed
- [x] Fix `MockOscSender` missing broadcast methods.
- [x] Remove obsolete test modules referencing removed APIs.
- [x] Add current KeyMapper-focused tests.
- [x] Ensure `tests/` suite passes in project venv.
- [x] Add project license file.
- [x] Stop `pytest` from collecting hardware scripts via `pytest.ini`.
- [x] Remove `.gitignore` conflict for tracked `TASKS.md`.

## In Progress
- [ ] Final review for docs consistency across `README.md`, `SPEC.md`, and visualizer docs.

## Next Priorities
- [ ] Keep hardware scripts as operator tools (not CI tests).
- [ ] Expand automated tests for visualizer OSC parsing and renderer-safe state updates.
- [ ] Add a short `CHANGELOG.md` for the cleanup cycle.
- [ ] Add optional CI command documentation (`./venv/bin/python -m pytest -q tests`).

## Backlog
- [ ] Preset save/load for mapping and f1 settings.
- [ ] Additional LFO shapes and modulation routing.
- [ ] MIDI recording/export workflow.
- [ ] More robust multi-controller mapping profiles.

## Verification Commands
- `./venv/bin/python -m pytest -q tests`
- `./venv/bin/python -m harmonic_beacon.main --help`
- `./venv/bin/python -m harmonic_visualizer.main --help`
