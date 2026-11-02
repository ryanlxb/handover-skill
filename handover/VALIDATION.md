# v1.1.0-rc.1 Validation Report

- Date (UTC): 2026-11-02T09:13:45+00:00
- Target: `handover`
- Scope: structural/static checks only; no installation, no skill execution.

## Files

| file | lines | bytes | fences |
|---|---:|---:|---|
| CHECKLIST.md | 97 | 8678 | OK |
| E2E_TEST_RESULTS.md | 241 | 14445 | OK |
| FIXTURE_TEST_RESULTS.md | 34 | 2223 | OK |
| README.md | 237 | 18418 | OK |
| SKILL.md | 178 | 26067 | OK |
| SOURCES.md | 12 | 863 | OK |
| references/task-template.md | 69 | 3203 | OK |

## Checks

- Required files: PASS
- Frontmatter keys: PASS
- Code fences: PASS
- Python syntax: PASS
- Local links: PASS
- Truncation markers: PASS

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
