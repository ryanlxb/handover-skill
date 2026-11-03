# v1.1.0-rc.1 Validation Report

- Date (UTC): 2026-11-03T02:32:00+00:00
- Target: `handover`
- Scope: structural/static checks only; no installation, no skill execution.

## Files

| file | lines | bytes | fences |
|---|---:|---:|---|
| CHECKLIST.md | 118 | 10879 | OK |
| E2E_TEST_RESULTS.md | 241 | 14445 | OK |
| FIXTURE_TEST_RESULTS.md | 40 | 2724 | OK |
| README.md | 291 | 22560 | OK |
| SKILL.md | 122 | 11621 | OK |
| SOURCES.md | 18 | 1901 | OK |
| references/analysis.md | 74 | 3095 | OK |
| references/archive-restore.md | 30 | 3321 | OK |
| references/brief-load.md | 114 | 6830 | OK |
| references/data-model.md | 70 | 6202 | OK |
| references/fingerprint.md | 28 | 3349 | OK |
| references/save.md | 79 | 6338 | OK |
| references/task-template.md | 86 | 4459 | OK |

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
