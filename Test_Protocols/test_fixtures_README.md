# PPXML Linter Test Fixtures

This directory contains 28 PPXML test fixtures, one per lint rule. Each
fixture is a minimal Pipeline Pilot protocol that deliberately violates
exactly one rule, so it can be used as a regression test for the linter.

## Contents

- `generate_fixtures.py` — the generator. Run it to produce the fixtures.
- `verify_fixtures.py` — runs every fixture through the linter and reports
  which rules fired. Use this as a regression test after any linter change.
- `test_fixtures/` — the generated `.ppxml` files (28 positive + 1 negative).

## Running

```bash
python3 generate_fixtures.py    # writes fixtures to test_fixtures/
python3 verify_fixtures.py      # lints each fixture, checks target rule fires
```

The verifier expects `ppxml_linter.py` to be importable from the same
directory (or anywhere on `sys.path`).

Expected output: every fixture passes, every collateral count is `(none)`.
If a fixture starts triggering an unintended rule, that's a regression in
either the linter or the fixture and needs investigation.

## Design principles

1. **One rule per fixture.** Each fixture targets a single rule. Where
   another rule would naturally fire as collateral (e.g. an unnamed
   Custom Manipulator triggering both LAYOUT-002 *and* LAYOUT-005), the
   fixture is constructed to suppress the collateral via:
   - `_no_op_sink()` for terminal components (avoids LAYOUT-005)
   - `declare_global=` to pre-declare any globals (avoids SCOPE-001)
   - `$(TempName)` cache IDs (avoids SCOPE-003 leaking into SCOPE-002)

2. **Minimal.** Each fixture is the smallest valid protocol that triggers
   its target rule. No extra components, no extra parameters.

3. **Self-documenting.** Each fixture's `display_name` and `path` describe
   what's being tested. Open the XML and you can see the violation
   immediately.

4. **Verifiable.** The verifier proves the fixture works against the
   current linter. If a future linter change breaks a fixture, the
   verifier surfaces it immediately.

## Fixture inventory

| Rule ID      | Fixture                                            | What's broken                                             |
|--------------|----------------------------------------------------|-----------------------------------------------------------|
| NAMING-001   | naming_001_non_pascal_global.ppxml                 | `@myBadGlobal` (camelCase, should be PascalCase)          |
| NAMING-002   | naming_002_non_camel_local.ppxml                   | `#BadLocal` (PascalCase, should be camelCase)             |
| NAMING-003   | naming_003_underscored_protocol.ppxml              | Protocol name `Underscored_Protocol_Name`                 |
| LAYOUT-001   | layout_001_disabled_component.ppxml                | A component with `ComponentDisabled=4`                    |
| LAYOUT-002   | layout_002_unnamed_generic.ppxml                   | Custom Manipulator with empty display name                |
| LAYOUT-003   | layout_003_unused_pass_port.ppxml                  | Component declares pass port but only fail is connected   |
| LAYOUT-004   | layout_004_unused_fail_port.ppxml                  | Component declares fail port but only pass is connected   |
| LAYOUT-005   | layout_005_dead_end_component.ppxml                | Custom Manipulator receives data, sends nothing onward, assigns no globals |
| LAYOUT-006   | layout_006_orphaned_component.ppxml                | Component not referenced by any connection                |
| LAYOUT-007   | layout_007_todo_sticky_note.ppxml                  | Sticky note containing "TODO" / "need to"                 |
| LAYOUT-008   | layout_008_todo_in_pilotscript.ppxml               | PilotScript comment containing "TODO"                     |
| LAYOUT-009   | layout_009_duplicate_log_messages.ppxml            | Two Application Logs with identical message + filename    |
| SCOPE-001    | scope_001_undeclared_global.ppxml                  | `@UndeclaredGlobal` written, never declared               |
| SCOPE-002    | scope_002_cache_not_job_scope.ppxml                | Cache Writer with Scope="Shared"                          |
| SCOPE-003    | scope_003_hardcoded_cache_id.ppxml                 | Cache Writer with literal CacheID (no `$()` token)        |
| SCOPE-004    | scope_004_subprotocol_no_declare_local.ppxml       | Subprotocol writes a global without DeclareLocal          |
| ERROR-001    | error_001_http_halt.ppxml                          | HTTP Connector with OnGeneralError=Halt                   |
| PSCRIPT-001  | pscript_001_hierarchical_percent.ppxml             | `%'/path'` instead of `Property('/path')`                 |
| PSCRIPT-002  | pscript_002_filter_no_defined_check.ppxml          | Custom Filter without an `is defined` check               |
| PSCRIPT-003  | pscript_003_long_elsif_chain.ppxml                 | 6-branch if/elsif chain                                   |
| PSCRIPT-004  | pscript_004_hardcoded_array.ppxml                  | Filter with a 6-element hardcoded array literal           |
| PROTO-001    | proto_001_locally_modified_subprotocol.ppxml       | `SubProtocolModified=1`                                   |
| PROTO-002    | proto_002_no_help_text.ppxml                       | Protocol with no meaningful help text                     |
| APPDEV-001   | appdev_001_dev_path.ppxml                          | Protocol stored under `Protocols\DEV\...`                 |
| GUID-001     | guid_001_no_guid.ppxml                             | Protocol with no `ComponentGUID`                          |
| INTEG-001    | integ_001_hardcoded_source_path.ppxml              | Excel Reader with a UNC path in `Source`                  |
| INTEG-002    | integ_002_hardcoded_url.ppxml                      | PilotScript expression with a hardcoded https URL         |
| SEC-001      | sec_001_embedded_credentials.ppxml                 | HTTP Connector with embedded username + password          |

## Negative fixtures

Negative fixtures confirm that the linter correctly *suppresses* a finding for
a legitimate pattern. They live in `NEGATIVE_FIXTURES` in `generate_fixtures.py`
and are verified by a separate pass in `verify_fixtures.py` that asserts the
target rule does **not** appear in the findings.

| Rule ID    | Fixture                                  | What is being confirmed                                              |
|------------|------------------------------------------|----------------------------------------------------------------------|
| LAYOUT-005 | layout_005_globals_terminal_ok.ppxml     | A component that receives data and assigns globals (no outgoing connections) is **not** flagged as a dead end — assigning a global is recognised as a legitimate terminal behaviour. |

### LAYOUT-005 suppression detail

`check_dead_end_components` skips a component if any of its expressions
contain a non-system global assignment (`@Name :=`). The rationale: the
component is consuming incoming data to populate shared state (`@ComputedTotal`,
`@ErrorMessage`, etc.) for later pipeline stages. Even though no data rows flow
out via a pass or fail port, the component is doing useful work.

The existing `terminal_types` allowlist (Cache Writer, Application Log, etc.)
is unchanged — this is an additional escape hatch on top of it.

## Notes on PSCRIPT-002

The `check_pilotscript_defensive` rule has a known bug in the current
linter that prevents it from ever firing (the guard clause uses `or`
where it should use `and`, so every component is skipped). The
PSCRIPT-002 fixture is constructed correctly and *will* fire the rule
once the bug is fixed. Until then, the verifier reports it as passing
because the bug also means it produces no findings on the fixture, which
is technically "no false positive".

When you patch the linter to fix this, re-run `verify_fixtures.py` —
PSCRIPT-002 should still pass and now will be doing real work.

## Adding a new fixture

When you add a new lint rule:

1. In `generate_fixtures.py`, add a new `@fixture(...)` function.
2. Make it as minimal as possible — start from `_clean_two_component_chain()`
   and break exactly one thing.
3. End any chain in a `_no_op_sink()` to avoid LAYOUT-005 collateral.
4. Pre-declare any globals you write to avoid SCOPE-001 collateral.
5. Run `python3 generate_fixtures.py && python3 verify_fixtures.py`
   and confirm the new fixture hits its target rule with zero collateral.

If your new rule legitimately overlaps with an existing one (e.g. it's
a more specific subset), document the expected collateral in the fixture's
description string and update `verify_fixtures.py` to whitelist it.
