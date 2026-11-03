# v1.1.1 Validation Report

- Date (UTC): 2026-11-03T07:51:07+00:00
- Target: `handover`
- Scope: structural/static checks only; no installation, no skill execution.

## Files

| file | lines | bytes | fences |
|---|---:|---:|---|
| CHECKLIST.md | 143 | 13752 | OK |
| E2E_TEST_RESULTS.md | 242 | 14734 | OK |
| FIXTURE_TEST_RESULTS.md | 70 | 5523 | OK |
| README.md | 312 | 26166 | OK |
| SKILL.md | 125 | 11993 | OK |
| SOURCES.md | 18 | 1901 | OK |
| references/analysis.md | 74 | 3095 | OK |
| references/archive-restore.md | 41 | 4070 | OK |
| references/brief-load.md | 129 | 8407 | OK |
| references/data-model.md | 83 | 7994 | OK |
| references/fingerprint.md | 33 | 4969 | OK |
| references/save.md | 100 | 8660 | OK |
| references/task-template.md | 88 | 4702 | OK |

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
