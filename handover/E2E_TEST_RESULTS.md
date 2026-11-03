# Claude Code E2E Test Results

- Current record: v1.1.2 (2026-11-03)
- Historical record: v1.1.0-rc.1 (2026-11-02), preserved below.

## v1.1.2 headless E2E

- Date: 2026-11-03
- Version: v1.1.2
- Claude Code: 2.1.300
- Model gateway: custom gateway (name withheld); the harness printed `unrecognized_model` at startup and execution continued.
- Isolation: installed as a project-local copy renamed to `handover-v112`, so the globally installed v1.1.1 `handover` skill could not shadow it. The skill content, references, and scripts under test are v1.1.2; only the frontmatter `name` and invocation name were changed.
- Invocation: `claude -p "<slash command>" --permission-mode dontAsk --allowedTools "Read Write Edit Glob Grep Bash" --max-turns <n> --no-session-persistence`
- Scope: real Claude Code skill invocation in one temporary git project. This is not a real business project and not a multi-model or multi-permission-mode matrix.

### Results

| Case | Expected | Observed | Result |
|---|---|---|---|
| `save` (new task) | Create task, sidecar, and entry; no business-code change; `check` matched | Created `.handover/demo.md`, `.handover/demo.fingerprint.json`, `handover.md`; 3 content-hashed files; `snapshot_id` recorded; `check` matched; `ignore-check` ok | PASS |
| Fresh-session `load` | Read-only; `matched`; no status/`updated_at` change | Task and sidecar SHA-256 unchanged; `matched`; ~1.6k tokens read | PASS |
| Modify declared file, then `load` | `changed` with `content_changed` | `changed`; ` M src/login.ts`; `incomplete: false` | PASS |
| Re-`save` | Reuse active task; new baseline; `matched` | `active-reuse-allowed`; new `snapshot_id`; `updated_at` updated; `check` matched | PASS |
| `save` on completed task | Stop without overwriting; ask to reopen or create a new task | `status-guard` exit 1; skill wrote nothing; task stayed `completed`; reopen/new-task options reported | PASS |
| Legacy migration | Plain guard exit 2; `--legacy-migration` exit 3; migrate then re-guard | Both exits observed; frontmatter added; re-guard exit 2 because migrated `status: unknown`; save stopped without inventing a status | PASS for the branch; task remains unactivated |
| `archive` | Move task + sidecar as one group; preserve baseline; update entry | Both files moved; `fingerprint_sha256` and `updated_at` unchanged; entry updated; `check` matched | PASS |
| `restore` | Return group; status `paused`; preserve baseline and timestamps | Group restored; `status: paused`; `archived_at` preserved; `restored_at` set; `fingerprint_sha256` unchanged; `check` matched | PASS |
| `list --all` | Active + exceptions; ignore non-task backups | `demo` shown paused; `legacy` shown as unknown exception; `.handover/demo.md.bak` not treated as a task | PASS |
| `brief` (after read-budget clarification) | Project background + summary state; no full task body | Read `demo` frontmatter + summary (L1-30) and `legacy` frontmatter (L1-15); ~1.2k tokens; skipped demo body L31+ | PASS |
| `fingerprint --out` business file | Exit 2; file unchanged | Exit 2 with path restriction; business file unchanged | PASS |
| `fingerprint --out` task Markdown | Exit 2; task unchanged | Exit 2 with filename restriction; task unchanged | PASS |
| `analysis --json` content probe | No system/tool text; no `head` field | Synthetic transcript markers absent; no `head` field | PASS |

### Detailed observations

- The first `save` created a new `in-progress` task without touching `src/login.ts`, `README.md`, or `.gitignore`; `check` reported `matched` over 3 content-hashed files and git dirs `.` and `src/`.
- A fresh headless `load` did not modify the task file or sidecar; byte-level SHA-256 checks before/after passed.
- After changing `src/login.ts`, `load` reported `changed` (not `unknown`) and named the modified path.
- The second `save` reused the active task, regenerated the sidecar with a new `snapshot_id`, and `check` matched the new baseline.
- On a manually completed task, the skill stopped at `status-guard` exit 1 and did not write; it offered explicit reopen or a new task.
- The legacy record was migrated from a frontmatter-less Markdown file. The skill then re-ran `status-guard`, received exit 2 for `status: unknown`, and correctly stopped instead of fabricating `in-progress`.
- Archive/restore preserved `fingerprint_sha256` and `updated_at`; the sidecar moved with the task and `fingerprint_file` was rewritten to the new location.
- The first `brief` run read 60 lines of the task file, above the ≤40-line summary budget in `brief-load.md`. The reference was tightened to stop at the next `##` heading and to read only frontmatter for unrecognised records; a re-run read `demo.md:1-30` and `legacy.md:1-15` (~1.2k tokens) and skipped the task body.
- `analysis` was probed with a synthetic transcript containing system and tool markers; the JSON output contained neither marker and no `head` field.

### Limitations

- One Claude Code version, one model/gateway, one temporary git project. Results are behavioral evidence for this environment, not a cross-model guarantee.
- The E2E used a renamed project-local copy; the exact `/handover` name was not exercised while a global v1.1.1 copy was installed. For a release install, replace or remove the global copy and repeat the minimal chain.
- `analysis` leak testing used a synthetic transcript; live transcripts were not inspected for content.
- Not covered: real business project, actual 1.0.0 artifact, concurrency, interactive permission modes, archive/restore failure injection, and the full `CHECKLIST.md`.
- The migrated legacy task remains `status: unknown` by design; completing it requires a user-confirmed status before the next save.

---

# Historical: v1.1.0-rc.1 Claude Code E2E Test Results

- Date: 2026-11-02
- Version: v1.1.0-rc.1
- Claude Code: 2.1.300
- Model gateway: custom gateway (name withheld); the harness printed `unrecognized_model` at startup and execution continued.
- Invocation: `claude -p "<slash command>" --permission-mode dontAsk --allowedTools "Read Write Edit Glob Grep Bash" --max-turns 30 --no-session-persistence`
- Scope: minimal real save/load/change chain in temporary git projects. Fixture-level script tests are in `FIXTURE_TEST_RESULTS.md`; static checks are in `VALIDATION.md`.
- Historical note: this section covers `v1.1.0-rc.1`. Current v1.1.2 results are above; current fixture results are in `FIXTURE_TEST_RESULTS.md` (82 cases).

## Coverage summary

This table is the canonical, scoped status summary for this report. Other documents should link here instead of restating a different status.

| Layer | Scope | Result |
|---|---|---|
| Static / structural | `VALIDATION.md` | PASS; no errors |
| Script fixtures | `FIXTURE_TEST_RESULTS.md` (19 cases) | 19/19 PASS |
| Real Claude Code E2E | Minimal save → load → modify → load chain in temporary git projects | PASS after the `.claude/` scope fix |
| Controlled fixture acceptance | Installed copy; temporary projects/fixtures: no-ID load matrix, multi-turn handover, A/B isolation, archive/restore, 1.0-style migration | PASS (see below) |
| Real business project | Actual user project and data | Not executed |
| Real 1.0.0 artifact migration | An actual 1.0.0 task file, not a 1.0-style fixture | Not executed |
| Concurrency / real permission modes | Multiple writers, normal interactive permissions | Not executed |
| Full `CHECKLIST.md` | All 70 items | Not executed |

Controlled fixture acceptance is not a real-project trial. The 1.0-style migration below used a task file without YAML frontmatter; it is not evidence that an actual 1.0.0 file was migrated.

## v1.1.0-rc.1 scope and limitations

- Release candidate for controlled trial; not a stable release.
- Verified on the installed copy with controlled temporary fixtures; not a real business project.
- The 1.0-style migration fixture is not an actual 1.0.0 artifact.
- Concurrency and normal interactive permission modes are not validated; do not run multiple writers on the same task.
- `.claude/` is excluded from the fingerprint scope in this version; configuration changes under `.claude/` are outside consistency checks.
- No full code audit or security guarantee. Static checks, checksums, fixtures, and E2E evidence have separate, bounded scopes.

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

## Earlier minimal-chain coverage

The four cases above cover only save/load/change. Later sections add controlled fixture acceptance for archive/restore, A/B isolation, and 1.0-style migration. For the current overall scope, including what remains untested, use the coverage summary at the top and the remaining open items at the end. Do not read this earlier section as the current overall status.

## Caveats

- The model gateway printed `[claude-code:unrecognized_model]` at startup. The skill still executed; this is a harness/model-identification warning, not a skill failure.
- `--permission-mode dontAsk` with explicit `allowedTools` was used to make the headless run non-interactive. Real permission behavior in your normal sessions may differ.
- These are real Claude Code runs, but they are not a substitute for the full acceptance sequence in `CHECKLIST.md`; the candidate acceptance section below covers archive/restore, A/B isolation, and 1.0-style migration, while concurrency and real permission modes remain open.

## v1.1.0-rc.1 candidate acceptance — installed copy (controlled fixtures)

- Date: 2026-11-02
- Claude Code: 2.1.300
- Model gateway: custom gateway (name withheld); the harness printed `unrecognized_model` at startup and execution continued.
- Invocation: `claude -p "<slash command>" --permission-mode dontAsk --allowedTools "Read Write Edit Glob Grep Bash" --max-turns 30 --no-session-persistence`.
- Scope: controlled temporary Git projects; no real business data. Headless runs used `--no-session-persistence`, so exact tool-call transcripts were not retained.

### Installation record

| Item | Value |
|---|---|
| Installed path | `~/.claude/skills/handover/` |
| Old-version backup | `~/.claude/handover-backups/handover-<UTC timestamp>/` |
| Source | Repository working tree at `c309b8a` plus the candidate changes; not a committed tag |
| Package checksums | `SHA256SUMS.txt` all OK in the installed copy |
| `SKILL.md` SHA-256 | `6ce596c8fd3109cf925cd8113f370df47b50b0ac0dd80a678075dbd0e73f092f` |
| `scripts/handover.py` SHA-256 | `e798c1c81b79aea3cae019dbc6a511ff1d9ee013a070516e71ef780d923700a2` |
| Script path | `~/.claude/skills/handover/scripts/handover.py` (resolved from `${CLAUDE_SKILL_DIR}`; exact invocation not retained in the headless transcript) |
| Repo/install alignment | Installed `SKILL.md` and `handover.py` hashes match the repository working tree |

### No-ID load matrix

| Case | Fixture | Expected | Actual | Result |
|---|---|---|---|---|
| Unique fresh `in-progress` | One task `alpha`, `in-progress`, fresh | Auto-select, verify, no auto-development | Selected `alpha`; reported goal/constraints; read-only; no development | PASS |
| Unique fresh `paused` | One task `beta`, `paused`, fresh | List candidate, no auto-select | Listed `beta` as paused; did not select | PASS |
| Unique stale `in-progress` | One task `gamma`, `in-progress`, 30 days old | List candidate, no auto-select | Marked `gamma` stale; did not select | PASS |
| Multiple `in-progress` | `delta` (2h old) and `epsilon` (1h old) | List both, no recency-based selection | Listed both; did not select by updated_at | PASS |

### Multi-turn handover integrity

- Scenario: one process received requirements, a correction, decisions, and todos; it ran `save demo`. A separate process (equivalent to `/clear`) ran `load demo`.
- Restored: original request, authoritative correction, SQLite decision, deferred OAuth/SSO, two todos, and six open questions explicitly marked as not approved.
- Status remained `pending`; `load` was read-only; `check` returned `consistency: matched` (1 file, 0 git entries).
- Result: PASS; the load did not auto-start implementation.

### A/B project isolation

- Projects A and B each contained a task with the same task-id `demo` but different titles.
- `load demo` in each project reported its own title and project root; neither read the other project's task.
- Result: PASS.

### Archive / restore

- Fixture: completed task `done-task` with a bound fingerprint sidecar.
- Archive moved Markdown and sidecar as one record group, set `archived_at`, kept `updated_at` unchanged, updated `fingerprint_file`, and updated the entry.
- Restore moved both files back, set status to `paused`, recorded `restored_at`, preserved `archived_at` and `updated_at`, kept `fingerprint_sha256` unchanged, and updated the entry.
- `check` returned `consistency: matched` before and after; no baseline was regenerated.
- Result: PASS.

### 1.0-style migration (fixture)

- Fixture: a task file without YAML frontmatter; this is not an actual 1.0.0 artifact.
- `save legacy` added `schema: 1`, `title`, `status: unknown`, `updated_at: null`, and `migrated_at`; it did not default the status to `in-progress` and did not use the migration time as `updated_at`.
- Body content was preserved, but one extra leading blank line was added after the frontmatter (271 bytes vs 270 bytes). The run claimed "byte-identical, 230 bytes"; that claim was inaccurate.
- `list` placed the record in `EXCEPTIONS` with `status unknown`; explicit `load legacy` reported the unknown status and did not auto-activate it; `check` returned `consistency: matched`.
- Result: PASS with a minor formatting/reporting finding. No record content was lost.

### Remaining open items

- Real business-project trial (actual project and data).
- Real 1.0.0 artifact migration (the migration above used a 1.0-style fixture).
- Concurrency and real interactive permission modes.
- Full 70-item `CHECKLIST.md` execution.
- Exact tool-call transcript capture for template reads and helper invocations.

## v1.1.0-rc.1 release binding

- Release: `v1.1.0-rc.1` — release candidate, controlled trial only.
- Installed path: `~/.claude/skills/handover/`
- Previous-copy backup: `~/.claude/handover-backups/handover-20261102T090750Z/`
- Package checksums: `shasum -a 256 -c SHA256SUMS.txt` all OK in the installed copy.

### Protocol delta since the earlier E2E run

The earlier E2E install record used `SKILL.md` `6ce596c8…f092f`; this RC uses `32fb7a4a…994d`. The delta is:

- Added the Git ignore/tracked check: `ignore-check` helper plus `save`/`archive`/`restore` reminders.
- Narrowed the save-time `check` claim: it compares the current scene with the just-generated baseline; it does not prove the narrative semantically matches the code or that code was unchanged while the body was composed.
- Added the RC version labels and the scope/limitations section.
- The `load` selection logic and archive/restore record-group rules are unchanged; the final package was smoke-tested again below.

### Final package key hashes

| File | SHA-256 |
|---|---|
| `SKILL.md` | `32fb7a4a198fb0e3140b7ba2c41e550adcc66f908b7aa24f1329fd75fe4a994d` |
| `scripts/handover.py` | `be63a78545aa208bc5892603842a7c6d8431151e4c94fe8c9c5962e8ff807e1a` |
| `README.md` | `9a137e4502b6becdcdd21face8091b7c996545a2687acd026b952b70ecef9736` |
| `CHECKLIST.md` | `90a078d6a039da1e1303cb509fffebaf5e824b2d467166acbd316893d973e7e4` |

### Final smoke tests (installed RC)

- **Minimal save/load**: `save rc-smoke` created the task, sidecar, and entry; `check` returned `consistency: matched` (1 file, 0 git entries). A fresh-process `load rc-smoke` reported `matched`, restored the goal, and remained read-only.
- **Ignore check**: the fixture had no `.gitignore`; `ignore-check` correctly returned `warning` (`not-ignored, not-tracked`) and did not modify `.gitignore`.
- **No-ID selection**: the unique fresh `in-progress` fixture (`alpha`) was auto-selected; the load was read-only.
- **Fixture suite**: 19/19 PASS, including four `ignore-check` cases.
- **Static validator**: PASS, no errors.

### RC caveats

- These are controlled temporary fixtures, not a real business-project trial.
- The 1.0-style migration fixture is not an actual 1.0.0 artifact.
- Concurrency and normal interactive permission modes are not validated; do not run multiple writers on the same task.
- The 70-item `CHECKLIST.md` is not fully executed.
- Headless runs used `--permission-mode dontAsk` and the configured custom gateway, which printed `unrecognized_model`; results are behavioral evidence for this environment, not a guarantee across models/permissions.
