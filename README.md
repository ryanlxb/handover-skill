# handover-skill

A Claude Code skill for carrying task state across sessions: manually **save** a verified handover, then **load** it in a fresh session or a parallel task.

> Status: **v1.2.0**. Adds deterministic task-body sealing (`seal` + `body_sha256`/`goal_sha256`), `task-lint`, `goal-guard`, `entry-lint`, project-context and unverified-claim sections, and a `declared` root-scope default. Static validation and 93/93 fixture cases pass; a headless save → fresh load → goal change → conflict-refusal chain passed in a temporary project. Real business projects, actual 1.0.0 artifacts, concurrency, interactive permission modes, and other archive/restore failure modes remain untested.

## Why

Claude Code sessions are isolated. Starting a new window, switching tasks, or clearing a long session usually means re-describing the goal, decisions, failed attempts, and next steps.

This skill writes a project-local handover that a fresh session can verify:

- what the task is and what is done;
- decisions and rejected approaches;
- failed attempts and retry conditions;
- files, symbols, and verification evidence;
- what changed in the worktree since the handover was written;
- the exact command to resume the task.

It is not a chat log, a code backup, or an automatic execution queue.

## Install

Copy the `handover/` folder into one of these locations:

```text
~/.claude/skills/handover/                 # all projects
<project>/.claude/skills/handover/         # one project
```

The final path must contain `.../skills/handover/SKILL.md`.

For a trial, prefer a temporary project so you do not overwrite an existing skill. If a global and a project-level `handover` both exist, verify which copy Claude Code resolves; a stale global copy can shadow the project copy. Replace or remove the old copy before testing a new version.

## Usage

```text
/handover save <task-id>
/handover load <task-id>
/handover brief
/handover list
/handover archive <task-id>
/handover restore <archive-id>
/handover load --archived <archive-id>
```

Typical loop:

```text
save → confirm files and fingerprint → /clear → load → continue work → save
```

- `save`: write `.handover/<task-id>.md`, its fingerprint sidecar, and update `handover.md`.
- `load`: read-only verification; it does **not** change status or `updated_at`.
- `brief`: load project background for a new task; do not inherit an old task queue.
- `list`: active tasks plus an exceptions section for unknown/corrupt records.
- `archive` / `restore`: move a task and its sidecar as one record group; no permanent delete in v1.1.

## Design invariants

- Manual save and load; no automatic save, delete, `/clear`, or commit.
- Project-local storage; no cross-project scanning and no global last-active pointer.
- Target projects should ignore `.handover/` and `handover.md`; task files contain local absolute paths, and the skill does not auto-modify `.gitignore`.
- Task identity is `task-id`, not the window.
- `status` / `freshness` / `consistency` are separate:
  - `status`: in-progress / pending / blocked / paused / completed / cancelled;
  - `freshness`: fresh / stale / unknown (a reminder, not an expiry);
  - `consistency`: matched / changed / unknown, backed by content hashes plus relevant git state.
- A `snapshot_id` binds the task markdown and its fingerprint sidecar to the same save.
- `matched` only covers the declared scope, not the whole project.
- `load` does not auto-activate a task or run project commands.

## Repository layout

```text
handover/                  # the installable skill
├── SKILL.md
├── README.md
├── references/task-template.md
├── CHECKLIST.md
├── SOURCES.md
├── scripts/handover.py    # optional list / fingerprint / check / status-guard / ignore-check / stats / analysis
├── VALIDATION.md
├── FIXTURE_TEST_RESULTS.md
├── E2E_TEST_RESULTS.md
└── SHA256SUMS.txt

tests/                     # validation and fixture tests
├── validate_handover.py
├── run_fixture_tests.py
└── README.md

REVIEW.md                  # review guide
```

## Validation

Run the static validator and the script-level fixture tests:

```text
python3 -I tests/validate_handover.py handover
python3 -I tests/run_fixture_tests.py
```

Current results:

| Layer | Result |
|---|---|
| Static/structural (`VALIDATION.md`) | PASS, no errors |
| Script fixtures (`FIXTURE_TEST_RESULTS.md`) | 93/93 PASS |
| v1.2 headless E2E (`E2E_TEST_RESULTS.md`) | PASS: save with `seal`/`task-lint`/`goal-guard`; fresh load with body/goal matched; goal change via explicit authorization; conflict instruction refused; `check` body tamper exit 3; root-scope noise remains matched |
| v1.2 exact `/handover` install | PASS: global v1.1.2 backed up and replaced with v1.2.0; exact `/handover` load and save passed in the temporary project |
| v1.2 short `/compact` A/B | PASS (one short run): both branches retained task facts; handover separated historical test evidence from current verification |
| v1.2 rules-heavy load | PASS: 25 rules, 5 Critical; goal/progress/next preserved; sources attributed |
| v1.2 entry-lint | PASS: 3 tasks / 3 linked; summary/long-line warnings surfaced |
| v1.1.2 headless E2E (historical) | PASS: save → fresh load (read-only) → modify → load (`changed`) → save (`matched`); completed guard, legacy migration branch, archive/restore, list, brief, `--out` and `analysis` probes |
| v1.1.2 focused acceptance (historical) | PASS: Python 3.9 static + 82/82 fixtures; non-git (`overall: partial`, `check: unknown`); helper-missing; archive/restore target conflicts; missing-sidecar archive; archive entry-update failure; brief/load budgets |
| Real business project, real 1.0.0 artifact, concurrency/real permission modes, full checklist | Not executed |

`VALIDATION.md`, `FIXTURE_TEST_RESULTS.md`, and the v1.2 section of `E2E_TEST_RESULTS.md` are the current v1.2.0 records. `E2E_TEST_RESULTS.md` also preserves the v1.1.2 and v1.1.0-rc.1 records as history. Controlled fixture acceptance is not a real-project trial.

`SHA256SUMS.txt` verifies file digests only; it does not prove logic, installation, permissions, or safety.

## Known limitations

- Archive/restore are instruction-based, not scripted; the v1.1.2 headless E2E exercised the happy path, but real file-move failure behavior is still being validated.
- `SKILL.md` routes to `references/`, and `references/save.md` points to `references/task-template.md`. The v1.1.2 headless E2E exercised the reference-routed save/load/change chain; template reading still deserves a separate check after any installation change.
- The fingerprint covers declared files plus relevant git state; it does not prove the whole project is consistent. Content hashes cover only explicitly listed files; directory scope only filters git status entries. `body_sha256`/`goal_sha256` detect post-seal edits, but they do not prove the narrative matches the code or that the task was not edited before sealing.
- v1.2 quality checks are helper-enforced when the save protocol runs them: `seal`, `task-lint`, and `goal-guard` are deterministic commands, but the skill is still prompt-based, so a model that skips a command is not blocked by a harness hook.
- v1.1.2 fixes remain covered by fixtures and historical E2E: arbitrary `--out` overwrite refusal, no system/tool content in `analysis`, schema/project_root validation in `status-guard`, an explicit legacy-migration branch, Git error classification in `ignore-check`, strict transcript selection, restricted frontmatter parsing, bool-schema and duplicate-ID handling in `list`, config symlink boundaries, reserved task IDs, and coverage reporting.
- The skill is a prompt-based skill, not a background service or a deterministic state machine.
- Deliberately not in v1.2.0: a concurrency write lock (single-user manual workflow; safe writes plus conflict reporting only) and scripted archive/restore moves (the instruction-based record-group rules remain; scripting file moves was judged too risky for this patch).

## License

MIT. See `LICENSE`.
