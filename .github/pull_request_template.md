## Description
<!-- What does this PR do? Be specific. -->

Closes #<!-- issue number, if applicable -->
Related: <!-- REQ-F-NNN or US-XX if applicable — see docs/requirements/ and docs/user-stories/ -->

## Changes
<!-- Bullet list of what changed -->
-

## Checklist

### Tests
- [ ] Tests added or updated for all new/changed behaviour
- [ ] `cd kiri && python -m pytest tests/unit/ -q` passes locally

### Architecture
- [ ] Branch name follows convention: `feat/`, `fix/`, `sec/`, or `docs/`
- [ ] If a design decision changed: ADR created or updated in `docs/adr/`
- [ ] If requirements changed: `docs/requirements/` updated

### Critical invariants (CLAUDE.md — do not skip)
- [ ] Fail-open behaviour preserved: L1/L3 errors result in PASS, not BLOCK (ADR-004)
- [ ] L2 symbol matching remains always active
- [ ] `kiri serve` still binds to `127.0.0.1` only — not `0.0.0.0` (REQ-S-005)
- [ ] Indexer stores float vectors only, never source text (REQ-NF-005)

## Notes for reviewer
<!-- Anything the reviewer should pay special attention to. Leave blank if none. -->
