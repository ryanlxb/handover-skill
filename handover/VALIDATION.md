# v1.1-draft Validation Report

- Date (UTC): 2026-11-02T03:38:54+00:00
- Target: `handover`
- Scope: structural/static checks only; no installation, no skill execution.

## Files

| file | lines | bytes | fences |
|---|---:|---:|---|
| CHECKLIST.md | 93 | 7725 | OK |
| E2E_TEST_RESULTS.md | 110 | 5308 | OK |
| FIXTURE_TEST_RESULTS.md | 28 | 1774 | OK |
| README.md | 230 | 16039 | OK |
| SKILL.md | 167 | 22894 | OK |
| SOURCES.md | 12 | 863 | OK |
| references/task-template.md | 68 | 3181 | OK |

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
- Archive/restore, project isolation, 1.0.0 migration, concurrency: not executed.

Static checks do not replace end-to-end acceptance.
