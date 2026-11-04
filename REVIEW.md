# Handover Skill v1.1.2 — Review Package

- Date: 2026-11-03
- Status: v1.1.2 security/consistency patch; controlled trial only, not a stable release
- Installable folder: `handover/`
- Review-only file: this `REVIEW.md`

## v1.1.2 changes

- `fingerprint --out` refuses arbitrary business-file overwrites: custom output must be a sidecar name directly under `.handover/` or `.handover/archive/`, and an existing target must belong to the same project and task.
- `analysis --json` no longer emits any system-prompt or tool-description text (the `head` field is removed).
- `status-guard` validates `schema` and `project_root` in addition to `task_id` and `status`; `--legacy-migration` adds a separate exit-3 branch for recognisable frontmatter-less v1.0 records.
- `ignore-check` treats only a definite “not a git repository” response as `not-git`; timeouts, missing Git, and permission errors are `unknown`, exit 2.
- `analysis --session <id>` is strict: a missing explicit session is an error and never falls back to another transcript; auto-discovered transcripts that resolve outside the project transcript directory are ignored.
- Frontmatter parsing is a restricted flat-YAML subset: inline comments and quoting work; duplicate keys, indentation, nesting, sequences, anchors/tags, and unclosed quotes are parse errors. `list` rejects boolean `schema` and moves every copy of a duplicate task ID to EXCEPTIONS.
- config symlinks resolving outside the project are not read; reserved task IDs are rejected by the helper.
- `fingerprint`/`check` report content-hash and git-status coverage separately.

## What changed in v1.1.1 (historical)

- `check` no longer returns `matched` when the task frontmatter is missing or disagrees on `schema`, `task_id`, `project_root`, `fingerprint_file`, or `fingerprint_sha256`; those cases are `unknown`.
- `fingerprint` refuses an empty declared scope, so a 0-file sidecar cannot produce a vacuous `matched`.
- Root-level declared files scope direct root entries only; subdirectories still scope their subtrees. `--scope-dir .` means root-directory entries.
- `fingerprint` refuses a symlinked sidecar output path or a symlinked `.handover`, preventing a write through a link from overwriting a business file.
- `list` stops when `.handover` resolves outside the project and reports individual task/archive files whose paths resolve outside the project without reading them.
- `.handover/config.yaml` works without `---` frontmatter delimiters; invalid `stale_after_days` warns and falls back to 14.
- `ignore-check` probes `.handover/` with a trailing slash, so a first save before the directory exists no longer reports a false `not-ignored` warning.
- `matched` output reports `out_of_scope_changes` and states that it covers the declared scope only.
- A declared file that grows beyond the size limit and changes size is classified `changed`, not `unknown`.
- Duplicate task IDs are visible in `list` exceptions.
- Added `status-guard`: no-ID `save` only reuses active tasks; completed/cancelled/archived are not targets. New tasks default to `in-progress`; `completed` requires explicit user confirmation plus evidence; status conflicts become `blocked`. Reopening a completed task requires an explicit user request and `--reopen-authorised`.
- Fixture suite extended from 29 to 55 cases; static report and checksums regenerated.

## Suggested review order

1. `handover/README.md` — usage, boundaries, lifecycle.
2. `handover/SKILL.md` — the model-facing router and safety rules.
3. `handover/references/save.md`, `fingerprint.md`, `brief-load.md` — mode details.
4. `handover/references/task-template.md` — task document schema.
5. `handover/scripts/handover.py` — `list`, `fingerprint`, `check`, `status-guard`, `ignore-check`, `stats`, `analysis`.
6. `handover/VALIDATION.md` — structural/static checks.
7. `handover/FIXTURE_TEST_RESULTS.md` — 82 script-level cases.
8. `handover/E2E_TEST_RESULTS.md` — v1.1.2 headless E2E plus the historical v1.1.0-rc.1 record.
9. `handover/CHECKLIST.md` — 122 acceptance scenarios, not fully executed.

## Test status

| Layer | Result |
|---|---|
| Structural/static (`VALIDATION.md`) | PASS; no errors |
| Script fixture (`FIXTURE_TEST_RESULTS.md`) | 82/82 PASS |
| v1.1.2 headless E2E (`E2E_TEST_RESULTS.md`) | PASS: save → fresh load (read-only) → modify → load (`changed`) → save (`matched`); completed guard; legacy migration branch; archive/restore; list; brief; `--out` and `analysis` probes |
| v1.1.2 exact `/handover` install | PASS: global v1.1.1 backed up and replaced with v1.1.2; the same chain passed in a new project with no project-level skill |
| v1.1.2 focused acceptance | PASS: Python 3.9 static + 82/82 fixtures; non-git save/load (`overall: partial`, `check: unknown`); helper-missing degradation; restore/archive target conflicts; missing-sidecar archive; archive entry-update failure; brief/load read budgets |
| v1.1.1 headless save/load smoke | PASS: save/load/list exit 0; load read-only ~3k tokens; `changed` only for untracked harness files created after save; kept as historical evidence |
| v1.1.1 status-selection smoke | PASS: continuing a completed task created new `in-progress` `project-init-wrapup`; existing completed tasks unchanged; kept as historical evidence |
| Real Claude Code E2E (rc.1 minimal chain) | PASS after a scope fix; not rerun for v1.1.1 |
| Controlled fixture acceptance (rc.1) | PASS for no-ID load, multi-turn, A/B isolation, archive/restore, 1.0-style migration; not rerun for v1.1.1 |
| Real business project, real 1.0.0 artifact, concurrency/real permission modes, full 122-item checklist | Not executed |

The v1.1.2 headless E2E reran the save → load → change → load → save chain and the bounded cases above in temporary git projects. The main matrix used a project-local copy renamed to `handover-v112`; after the matrix, the global v1.1.1 copy was backed up and replaced with v1.1.2, and the exact `/handover` chain was re-run in a new project with no project-level skill and passed. The focused acceptance batch also covered Python 3.9, non-git projects, helper-missing degradation, restore/archive target conflicts, missing-sidecar archive, archive entry-update failure, and brief/load budgets; `fingerprint` now reports `overall: partial` when git is unavailable. `E2E_TEST_RESULTS.md` now contains the v1.1.2 record plus the historical rc.1 record. Real business projects, actual 1.0.0 artifacts, concurrency, interactive permission modes, other archive/restore failure modes (for example a cross-device move), and the full 122-item checklist remain untested.

### Status-selection manual E2E (global v1.1.0)

| Case | Setup | Observed save result |
|---|---|---|
| A | 1 completed + ongoing, half-done task | new `in-progress` task |
| B | 1 completed + code done, untested | new `in-progress` task |
| C | 2 completed + new ongoing task | new `in-progress` task |
| D | 1 completed + completion claim without evidence | new `blocked` task |
| E | 2 completed + session says “continue old-task-2” | reused `old-task-2`, reopened `completed` → `in-progress` |
| F | patched v1.1.1; same setup as E | new `project-init-wrapup` `in-progress`; `old-task-1/2` unchanged `completed`; `status-guard` used |

E exposed the completed-task reuse path: `save` with no ID can select an existing completed task and either reopen it or leave it completed. v1.1.1 adds `status-guard` and the no-ID selection rules. F confirms the patched behavior: “continue old-task-2” created a new in-progress task and did not mutate the completed records.

A separate local headless smoke against the globally installed v1.1.0 skill also exited 0 for save, load, check, and list; the load read about 2.4k tokens and stayed read-only. The global copy shadowed the project-level copy, so that smoke does not validate v1.1.1.

## Known caveats

- Archive/restore are instruction-based, not scripted; the record-group rules are written, but real file-move failure behavior remains open.
- `check` proves consistency within the declared scope only: content hashes for explicitly listed files plus git status for declared directories. It does not prove directory-wide content consistency, the narrative matches the code, or that the task body is unchanged; it does not hash the task body.
- The fingerprint excludes `.handover/`, `handover.md`, `.claude/`, and `.git/` by design.
- Concurrency is unsupported; do not run multiple writers on the same task.
- `SHA256SUMS.txt` verifies file digests only, not logic, installation, permissions, or safety.
- The v1.1.0 headless brief E2E used a configured custom gateway; results are behavioral evidence for that environment, not a guarantee across models or permission modes.
- If both a global and a project-level `handover` are installed, verify which copy resolves. A stale global copy can shadow the project copy; replace or remove it before testing a new version.

## Install for review

Prefer a temporary project:

```text
<temp-project>/.claude/skills/handover/
```

Copy `handover/` there, start a new Claude Code session in `<temp-project>`, then run:

```text
/handover save demo
/handover load demo
```

Do not overwrite an existing skill until you have reviewed this package.

## Validation commands

```text
python3 -I tests/validate_handover.py handover
python3 -I tests/run_fixture_tests.py
```

CI runs both on every push and pull request.

## Repository map

```text
README.md                  # project overview and install
REVIEW.md                  # this review guide
RELEASE_NOTES.md           # v1.1.2 patch notes and historical releases
LICENSE                    # MIT
.github/workflows/ci.yml   # static + fixture checks + checksums + secret scan
handover/                  # installable skill
├── SKILL.md
├── README.md
├── references/
├── CHECKLIST.md
├── SOURCES.md
├── scripts/handover.py
├── VALIDATION.md
├── FIXTURE_TEST_RESULTS.md
├── E2E_TEST_RESULTS.md
└── SHA256SUMS.txt
tests/
├── README.md
├── validate_handover.py
└── run_fixture_tests.py
```
