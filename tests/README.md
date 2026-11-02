# Tests

These tests validate the skill package and the optional fingerprint helper. They do not install or execute the Claude Code skill.

Requirements: Python 3.9+ and `git`.

## Static validation

```text
python3 -I tests/validate_handover.py handover
```

Checks required files, frontmatter keys, code-fence balance, local Markdown links, truncation markers, and Python syntax. This is a structural check, not an end-to-end test.

## Fixture tests

```text
python3 -I tests/run_fixture_tests.py
```

Runs 19 fixture cases against `handover/scripts/handover.py` in temporary git and non-git projects:

- matched baseline;
- snapshot binding mismatch;
- content change;
- new/deleted/renamed files;
- staged-state change;
- HEAD change;
- partial baseline with and without a definite change;
- non-git project;
- fingerprint SHA-256 mismatch;
- `.claude/` and `.git/` exclusion;
- `list` title from frontmatter and fallback to task-id.
- `ignore-check` ok when `.handover/` and `handover.md` are ignored and untracked;
- `ignore-check` warning when ignore rules are missing;
- `ignore-check` warning when task data is tracked even if ignore rules exist;
- `ignore-check` not-git when the project is not a Git work tree.

The script prints a Markdown report. It exits non-zero if any case fails.

These fixture tests do not cover:

- Claude Code skill installation or `/handover` invocation;
- archive/restore file moves and entry-link updates;
- concurrent writers;
- real permission modes.
