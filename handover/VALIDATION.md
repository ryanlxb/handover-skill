# v1.2.0 Validation Report

- Date (UTC): 2026-11-16T09:17:52+00:00
- Target: `handover`
- Scope: structural/static checks only; no installation, no skill execution.

## Files

| file | lines | bytes | fences |
|---|---:|---:|---|
| CHECKLIST.md | 185 | 18878 | OK |
| E2E_TEST_RESULTS.md | 375 | 30234 | OK |
| FIXTURE_TEST_RESULTS.md | 108 | 9760 | OK |
| README.md | 360 | 31727 | OK |
| SKILL.md | 115 | 11970 | OK |
| SOURCES.md | 18 | 1901 | OK |
| references/analysis.md | 75 | 3614 | OK |
| references/archive-restore.md | 41 | 4102 | OK |
| references/brief-load.md | 140 | 9708 | OK |
| references/data-model.md | 101 | 11955 | OK |
| references/entry-template.md | 30 | 1111 | OK |
| references/fingerprint.md | 40 | 7605 | OK |
| references/save.md | 118 | 11981 | OK |
| references/task-template.md | 106 | 6128 | OK |
| references/token-hygiene.md | 21 | 1313 | OK |

## Checks

- Required files: PASS
- Frontmatter keys: PASS
- Code fences: PASS
- Python syntax: PASS
- Local links: PASS
- Truncation markers: PASS
- Size budgets: PASS

## Errors

- (none)

## Warnings

- references/task-template.md: example date present; do not copy into a real task

## Not Covered by This Validator

- This validator does not install or execute the skill.
- Skill invocation and the minimal save/load/change chain: see `E2E_TEST_RESULTS.md`.
- Script fixture semantics: see `FIXTURE_TEST_RESULTS.md`.
- Current dynamic coverage, including controlled fixture acceptance: see `E2E_TEST_RESULTS.md`.

Static checks do not replace end-to-end acceptance.
