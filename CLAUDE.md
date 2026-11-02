# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A Claude Code skill package for cross-session task handover, plus a stdlib-only helper and test suite. There is no build step, package manager, or application server.

- `handover/` is the installable skill. Install it by copying the folder to `~/.claude/skills/handover/` or `<project>/.claude/skills/handover/`.
- `handover/SKILL.md` is the model-facing protocol; `handover/README.md` is the human-facing usage and boundary document.
- `handover/references/task-template.md` defines the task document schema.
- `handover/scripts/handover.py` is an optional helper with `list`, `fingerprint`, and `check`.
- `tests/` validates the package and helper; it does not execute the skill.
- `handover/VALIDATION.md`, `FIXTURE_TEST_RESULTS.md`, and `E2E_TEST_RESULTS.md` are committed validation reports.
- `handover/SHA256SUMS.txt` covers the skill package files.
- `.github/workflows/ci.yml` runs the static validator and fixture tests on push and PR.

## Commands

Requirements: Python 3.9+ and `git`.

### Validate and test

```text
python3 -I tests/validate_handover.py handover
python3 -I tests/run_fixture_tests.py
```

`validate_handover.py` checks required files, frontmatter keys, code-fence balance, local Markdown links, truncation markers, and Python syntax. It prints a Markdown report and exits non-zero on errors.

`run_fixture_tests.py` runs 19 cases against `handover/scripts/handover.py` in temporary git and non-git projects. It prints a Markdown report and exits non-zero on failures. There is no single-case flag; run the full suite, or temporarily narrow the `tests` list in `tests/run_fixture_tests.py` when debugging one case.

### Helper CLI

```text
python3 -I handover/scripts/handover.py --help
python3 -I handover/scripts/handover.py list --root <project> --all
python3 -I handover/scripts/handover.py fingerprint --root <project> --task <id> --paths <paths-file>
python3 -I handover/scripts/handover.py check --root <project> --task <id> --task-file <task.md>
python3 -I handover/scripts/handover.py ignore-check --root <project>
```

`check` exit codes: `0` = matched, `1` = changed, `2` = unknown or error.

`ignore-check` exit codes: `0` = ok or not a Git work tree, `1` = warning, `2` = unknown or error.

### Regenerate committed reports and checksums

```text
python3 -I tests/validate_handover.py handover > handover/VALIDATION.md
python3 -I tests/run_fixture_tests.py > handover/FIXTURE_TEST_RESULTS.md
```

After regenerating the reports or changing any listed skill file:

```text
(cd handover && shasum -a 256 CHECKLIST.md E2E_TEST_RESULTS.md FIXTURE_TEST_RESULTS.md README.md SKILL.md SOURCES.md references/task-template.md scripts/handover.py VALIDATION.md > SHA256SUMS.txt && shasum -a 256 -c SHA256SUMS.txt)
```

`E2E_TEST_RESULTS.md` is manual; update it only after a real Claude Code run, and sanitize local paths/model names before committing.

### Manual E2E (optional, real model call)

Install `handover/` into a temporary project's `.claude/skills/handover/`, then run from that project:

```text
claude -p "/handover save demo" --permission-mode dontAsk \
  --allowedTools "Read Write Edit Glob Grep Bash" \
  --max-turns 30 --no-session-persistence
```

This is a real model call and can take minutes. It is separate from `tests/`; fixture tests do not execute the skill.

## Architecture

### Skill flow

The skill is a manual protocol, not an automatic service:

```text
save → confirm task markdown + fingerprint → /clear → load → continue work → save
```

- `save` writes `.handover/<task-id>.md`, its fingerprint sidecar, and updates `handover.md`.
- `load` is read-only: it verifies the selected task and does not change `status` or `updated_at`.
- `brief` loads project background for a new task without inheriting an old task queue.
- `archive` / `restore` move a task and its sidecar as one record group; v1.1 does not permanently delete.
- `load` does not auto-activate a restored task; the next explicit `save` records `in-progress`.

### Data model

```text
handover.md                                  # project entry + task list (no global last-active)
.handover/<task-id>.md                       # task markdown with YAML frontmatter
.handover/<task-id>.fingerprint.json         # optional fingerprint sidecar
.handover/archive/<task-id>-<utc>.md         # archived task
.handover/archive/<task-id>-<utc>.fingerprint.json
.handover/config.yaml                        # optional: stale_after_days
```

Task files use YAML frontmatter with `schema`, `snapshot_id`, `task_id`, `status`, `updated_at`, `migrated_at`, `archived_at`, `restored_at`, `project_root`, `branch`, `head`, `worktree`, `fingerprint_file`, `fingerprint_sha256`, `fingerprint_scope`, and `fingerprint_checked_at`.

### Three separate state axes

- `status`: `in-progress` / `pending` / `blocked` / `paused` / `completed` / `cancelled`; `unknown` is diagnostic only.
- `freshness`: `fresh` / `stale` / `unknown`, computed from `updated_at` and `stale_after_days`. `stale` is a reminder, not an expiry or deletion trigger.
- `consistency`: `matched` / `changed` / `unknown`, computed at `load` time from the fingerprint and relevant git state.

`matched` means “consistent within the declared scope”, not “the whole project is consistent”.

### Fingerprint and snapshot binding

The sidecar records:

- content SHA-256 for declared files;
- relevant git branch, HEAD, and status entries (including new, deleted, renamed, and staged/unstaged changes);
- a `snapshot_id` shared with the task frontmatter.

The fingerprint scope is declared files + `接手必读` paths + explicit paths + their directories. It excludes `.handover/`, `handover.md`, `.claude/`, and `.git/`.

`check` first verifies that the task frontmatter and sidecar agree on `snapshot_id`, `fingerprint_file`, and `fingerprint_sha256`; a mismatch returns `unknown`. It then applies this precedence:

1. any definite content or git change → `changed`, with `incomplete: true` if some checks were unavailable;
2. no definite change but incomplete checks → `unknown`;
3. complete checks with no change → `matched`.

`save` must run `check` after writing the task file and sidecar to detect code changes that happened during snapshot generation.

### Archive / restore

Archive and restore treat the task markdown and its sidecar as one record group. They must:

- verify matching `snapshot_id` before moving both files;
- update `fingerprint_file` to the new location;
- preserve `fingerprint_sha256` and not regenerate the baseline;
- report actual locations and incomplete state if only one file moved;
- not delete the task file when entry-link updates fail.

### Test layers

- Static validator: structure, frontmatter, links, fences, Python syntax.
- Fixture tests: helper semantics in temporary projects.
- Claude Code E2E: real skill invocation, documented separately in `handover/E2E_TEST_RESULTS.md`.

These layers are not interchangeable; static checks do not prove runtime behavior.

## Editing rules and gotchas

- Update `handover/SKILL.md`, `handover/README.md`, `references/task-template.md`, `scripts/handover.py`, and tests together when changing behavior; they describe the same protocol.
- Do not regenerate a fingerprint during `archive` or `restore`; preserve the original baseline and mark consistency `unknown` if it is missing.
- Keep `load` read-only. Do not add automatic activation, commit, `/clear`, or service startup.
- Keep the helper stdlib-only and Python 3.9+ compatible.
- `stale` is not a status; `unknown` is not a user-selectable status.
- The fingerprint excludes `.claude/` and `.git/`; do not add them back to the declared scope.
- The template's example date (`2026-11-02T10:30:00+08:00`) is a format example; never copy it into a real task.
- Before committing, sanitize public reports: remove `/Users/...` paths, local test project paths, and model gateway names.
- `.gitignore` excludes `_extracted/`, `_checks/`, `_packaging/`, `*.zip`, `.claude/settings.local.json`, and `__pycache__`; do not commit these local artifacts.
- Regenerating `VALIDATION.md` or `FIXTURE_TEST_RESULTS.md` changes the checked-in reports; regenerate `SHA256SUMS.txt` afterward.
- The repository is public; check `git status` and `grep` the staged files for local paths or secrets before pushing.
