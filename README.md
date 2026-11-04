# handover-skill

A Claude Code skill for carrying task state across sessions: manually **save** a verified handover, then **load** it in a fresh session or a parallel task.

> Status: **v1.1.2**. Static validation, 82/82 fixture cases, and a headless save → fresh load → modify → load → save E2E pass. The main matrix used a project-local copy renamed to `handover-v112`; after replacing the global v1.1.1 copy with v1.1.2, the exact `/handover` chain was re-checked and passed. Real business projects, actual 1.0.0 artifacts, concurrency, interactive permission modes, archive/restore failure injection, and the full 122-item checklist remain untested.

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
| Script fixtures (`FIXTURE_TEST_RESULTS.md`) | 82/82 PASS |
| v1.1.2 headless E2E (`E2E_TEST_RESULTS.md`) | PASS: save → fresh load (read-only) → modify → load (`changed`) → save (`matched`); completed guard, legacy migration branch, archive/restore, list, brief, `--out` and `analysis` probes |
| v1.1.2 exact `/handover` install | PASS: global v1.1.1 backed up and replaced with v1.1.2; the same chain passed in a new project with no project-level skill |
| v1.1.1 headless save/load smoke | PASS; historical evidence |
| v1.1.1 status-selection smoke | PASS; historical evidence |
| Real Claude Code E2E (rc.1 minimal save/load/change) | PASS after a scope fix; historical evidence |
| Controlled fixture acceptance (rc.1: no-ID load, multi-turn, A/B isolation, archive/restore, 1.0-style migration) | PASS in temporary projects/fixtures; not rerun for v1.1.1 or v1.1.2 |
| Real business project, real 1.0.0 artifact, concurrency/real permission modes, full 122-item checklist | Not executed |

`VALIDATION.md`, `FIXTURE_TEST_RESULTS.md`, and the v1.1.2 section of `E2E_TEST_RESULTS.md` are the current v1.1.2 records. `E2E_TEST_RESULTS.md` also preserves the v1.1.0-rc.1 record as history. Controlled fixture acceptance is not a real-project trial.

`SHA256SUMS.txt` verifies file digests only; it does not prove logic, installation, permissions, or safety.

## Known limitations

- Archive/restore are instruction-based, not scripted; the v1.1.2 headless E2E exercised the happy path, but real file-move failure behavior is still being validated.
- `SKILL.md` routes to `references/`, and `references/save.md` points to `references/task-template.md`. The v1.1.2 headless E2E exercised the reference-routed save/load/change chain; template reading still deserves a separate check after any installation change.
- The fingerprint covers declared files plus relevant git state; it does not prove the whole project is consistent. Content hashes cover only explicitly listed files; directory scope only filters git status entries. `matched` also does not hash the task body. `matched` output reports out-of-scope change counts, but that is transparency, not full-project verification.
- v1.1.2 fixes are covered by fixtures and a headless E2E: arbitrary `--out` overwrite refusal, no system/tool content in `analysis`, schema/project_root validation in `status-guard`, an explicit legacy-migration branch, Git error classification in `ignore-check`, strict transcript selection, restricted frontmatter parsing, bool-schema and duplicate-ID handling in `list`, config symlink boundaries, reserved task IDs, and coverage reporting. The main matrix used a renamed project-local copy; the exact `/handover` name was re-checked after replacing the global copy with v1.1.2. It is still one environment; real business projects, concurrency, and interactive permissions remain untested.
- The skill is a prompt-based skill, not a background service or a deterministic state machine.

## License

MIT. See `LICENSE`.
