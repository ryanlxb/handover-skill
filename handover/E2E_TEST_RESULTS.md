# v1.1 Claude Code E2E Test Results

- Date: 2026-11-02
- Claude Code: 2.1.300
- Model gateway: custom gateway (name withheld); the harness printed `unrecognized_model` at startup and execution continued.
- Invocation: `claude -p "<slash command>" --permission-mode dontAsk --allowedTools "Read Write Edit Glob Grep Bash" --max-turns 30 --no-session-persistence`
- Scope: minimal real save/load/change chain in temporary git projects. Fixture-level script tests are in `FIXTURE_TEST_RESULTS.md`; static checks are in `VALIDATION.md`.

## Projects

| Project | Purpose |
|---|---|
| `e2e-project-20261102` | First save → load → modify → load; exposed the `.claude/` scope bug |
| `e2e-project-20261102b` | Save after the `.claude/`/`.git/` exclusion fix; verifies scope |

## Case 1 — Real save (first project)

**Command**

```text
claude -p "/handover save demo" --permission-mode dontAsk \
  --allowedTools "Read Write Edit Glob Grep Bash" \
  --max-turns 30 --no-session-persistence
```

**Expected**: create `handover.md`, `.handover/demo.md`, `.handover/demo.fingerprint.json`; do not modify business code; `check` returns matched.

**Actual**

- Files created: `handover.md`, `.handover/demo.md`, `.handover/demo.fingerprint.json`.
- Business code unchanged; `git status` showed only `?? .handover/` and `?? handover.md`.
- `check`: `consistency: matched`, `scope: 3 file(s), 0 git entries`.
- The 3 files were `src/login.ts`, `.claude/skills/handover/SKILL.md`, and `.claude/skills/handover/CHECKLIST.md`.

**Result**: PASS for save mechanics, **FAIL for scope selection**. The model included Skill installation documents in the fingerprint. The script now excludes `.claude/` and `.git/`.

## Case 2 — Real load (first project, before code change)

**Command**

```text
claude -p "/handover load demo" --permission-mode dontAsk \
  --allowedTools "Read Write Edit Glob Grep Bash" \
  --max-turns 30 --no-session-persistence
```

**Expected**: read-only; verify fingerprint; report matched; do not change status or `updated_at`.

**Actual**

- `consistency: matched` (`scope: 3 file(s), 0 git entries`).
- `load` explicitly reported read-only; status and `updated_at` unchanged.
- No business code or service changes.

**Result**: PASS.

## Case 3 — Modify code, then load (first project)

**Command**: modify `src/login.ts` (`"ok"` → `"changed"`), then repeat the load command above.

**Expected**: `consistency: changed`; identify content and git changes; `incomplete: false`; do not auto-execute a fix.

**Actual**

- `consistency: changed`.
- `content_changed: src/login.ts` with old/new SHA-256.
- `git_changed: status changed`.
- `incomplete: false`.
- No auto-revert, no auto-continue, no status/`updated_at` change.

**Result**: PASS.

## Case 4 — Save after scope fix (second project)

**Command**: same save command in `e2e-project-20261102b`.

**Expected**: sidecar contains only business-related files; no `.claude/skills/handover/` documents; `check` matched; `handover.md` uses a task list, not a global current-task pointer.

**Actual**

- `check`: `consistency: matched`, `scope: 1 file(s), 0 git entries`.
- Sidecar `files` contains only `src/login.ts`; `scope_dirs` contains only `src/`.
- `skipped_excluded` is empty because the model did not list `.claude/` paths this time.
- `handover.md` uses `## 当前记录区` with the task list, not a single “当前任务” pointer.
- Task status is `pending` because no business goal was provided; the skill did not invent one.

**Result**: PASS for the scope fix.

## Bug Found and Fixed

| Finding | Fix |
|---|---|
| First save included `.claude/skills/handover/SKILL.md` and `CHECKLIST.md` in the fingerprint and scope dirs | `scripts/handover.py` now excludes `.claude/` and `.git/` in addition to `.handover/` and `handover.md` |
| First save's `handover.md` used a single “当前任务” section | `SKILL.md` now requires a task list; no unique “current task” or global last-active pointer |
| Script examples used a relative `scripts/handover.py` path | Skill content now uses `${CLAUDE_SKILL_DIR}/scripts/handover.py`; fallback to `.claude/skills/handover/scripts/handover.py` |
| First E2E record still has the old 3-file scope | It is a test artifact, not a released record; the second project verifies the fix |

## Not Executed

- `archive` / `restore` (including task + sidecar group moves and entry-link failure).
- Project isolation with the same task-id in projects A and B.
- Real 1.0.0 file migration.
- Concurrent writers and real permission behavior.
- Exact template-read tool call: the headless runs used `--no-session-persistence`, so no transcript was retained. The generated document matched the template structure, but this is evidence, not a captured tool call.

## Caveats

- The model gateway printed `[claude-code:unrecognized_model]` at startup. The skill still executed; this is a harness/model-identification warning, not a skill failure.
- `--permission-mode dontAsk` with explicit `allowedTools` was used to make the headless run non-interactive. Real permission behavior in your normal sessions may differ.
- These are real Claude Code runs, but they are not a substitute for the full acceptance sequence in `CHECKLIST.md`; archive/restore and project isolation remain open.
