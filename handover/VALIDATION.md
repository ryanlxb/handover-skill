# v1.1.2 Validation Report

- Date (UTC): 2026-11-03T10:27:46+00:00
- Target: `handover`
- Scope: structural/static checks only; no installation, no skill execution.

## Files

| file | lines | bytes | fences |
|---|---:|---:|---|
| CHECKLIST.md | 158 | 15803 | OK |
| E2E_TEST_RESULTS.md | 296 | 19974 | OK |
| FIXTURE_TEST_RESULTS.md | 97 | 8395 | OK |
| README.md | 325 | 27874 | OK |
| SKILL.md | 124 | 11998 | OK |
| SOURCES.md | 18 | 1901 | OK |
| references/analysis.md | 75 | 3614 | OK |
| references/archive-restore.md | 41 | 4070 | OK |
| references/brief-load.md | 129 | 8407 | OK |
| references/data-model.md | 89 | 10135 | OK |
| references/fingerprint.md | 36 | 6330 | OK |
| references/save.md | 105 | 9957 | OK |
| references/task-template.md | 90 | 5132 | OK |

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
