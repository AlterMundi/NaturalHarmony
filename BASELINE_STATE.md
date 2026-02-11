# Baseline State - Comprehensive Cleanup
## Date: 2026-02-11
## Branch: refactor/comprehensive-cleanup

## Git Status
Clean working directory - starting from commit:
```
8f069a1 Update README with troubleshooting and new dependencies
```

## Known Issues Identified

### Critical Runtime Issues
1. **MockOscSender.py (Lines 432-433)**: Missing broadcast method implementations
   - `broadcast_voice_on()` - incomplete (line 432 just has `pass`)
   - `broadcast_voice_off()` - missing entirely
   - `broadcast_voice_freq()` - missing entirely
   - `broadcast_key_on()` - missing entirely
   - `broadcast_key_off()` - missing entirely
   - `broadcast_cc()` - missing entirely
   - Impact: Will throw AttributeError if beacon runs with `--mock --broadcast`

### Documentation Issues
2. **README.md**: Severely outdated
   - Describes obsolete "dual-voice" architecture
   - Wrong harmonic mapping table
   - Missing: Pad Mode, Stacking Mode, Split Mode, visualizer, modulation controller

3. **SPEC.md**: Completely outdated
   - Still describes v1.1 dual-voice system
   - Wrong dependency (pyliblo vs python-osc)
   - Missing modern features

4. **docs/VISUALIZER_PLAN.md**: May be outdated (need to check)

### Test Suite Issues
5. **tests/test_key_mapper.py**: References removed APIs
   - `create_default_mapper()` doesn't exist
   - `tolerance_cents` parameter removed
   - `get_harmonic()` method removed

6. **tests/test_octave_borrower.py**: Tests non-existent module
   - `harmonic_beacon/octave_borrower.py` doesn't exist

7. **tests/test_harmonics.py**: Wrong function signatures
   - `playable_frequency()` signature changed

### Repository Hygiene Issues
8. **No LICENSE file**: README claims MIT license but file is missing

9. **.gitignore conflict**: Lists `TASKS.md` but file is tracked in git

10. **Stale comments in code**:
    - `key_mapper.py:146` - disabled local matching logic needs documentation

## Current Defaults (Confirmed as Intentional)
- `DEFAULT_F1 = 65.0` Hz
- Pad Mode enabled by default: `PAD_MODE_ENABLED_BY_DEFAULT = True`
- Stacking Mode disabled by default (toggle via CC22)
- Split Mode disabled by default (toggle via CC104)

## Architecture Reality Check
Current system uses:
- **Single voice per layer** with optional Stacking Mode (not always dual-voice)
- **python-osc** (not pyliblo)
- **KeyMapper** with chromatic prototypes and transposition
- **Pad Mode** with 8×8 grid and Split Mode
- **Modulation controller** support for on-the-fly retuning
- **LFO chorus** for harmonic sweeping

## Next Steps
Proceed with Phase 2: Define source of truth and make architectural decisions
