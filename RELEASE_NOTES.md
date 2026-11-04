# handover v1.1.2

- Date: 2026-11-03
- Status: **v1.1.2** — security/consistency patch over `v1.1.1`; controlled trial only, not a stable release.
- Install: copy `handover/` to `~/.claude/skills/handover/`; back up any existing skill first.
- Package integrity: `handover/SHA256SUMS.txt` covers the 15 skill package files.

## What changed since v1.1.1

- `fingerprint --out` can no longer overwrite arbitrary business files. The default output is `.handover/<task-id>.fingerprint.json`; a custom `--out` must be directly under `.handover/` or `.handover/archive/`, use a `<task-id>[-<timestamp>].fingerprint.json` name, and may only replace an existing sidecar for the same project and task.
- `analysis --json` no longer emits the first 80 characters of each system block. Text and JSON output contain only sizes, categories, tool names, and server names.
- `status-guard` now validates `schema` and `project_root` in addition to `task_id` and `status`. `--legacy-migration` adds a separate exit-3 branch for recognisable frontmatter-less v1.0 records; corrupt, unclosed, non-Markdown, or unsupported-schema files remain exit 2.
- `ignore-check` reports `not-git` only when Git explicitly says “not a git repository”. Timeouts, a missing git executable, permission failures, and other Git errors return `unknown`, exit 2.
- `analysis --session <id>` is strict: a missing explicit session is an error and never falls back to another transcript. Session IDs are validated, and auto-discovered transcripts that resolve outside the project transcript directory are ignored.
- Frontmatter parsing is now a restricted flat-YAML subset: inline comments and quoted values work; duplicate keys, indentation, nested mappings, sequences, anchors/tags, block scalars, and unclosed quotes are parse errors instead of being silently ignored.
- `list` rejects boolean `schema` and moves every copy of a duplicate task ID to EXCEPTIONS; file ordering no longer decides which copy stays active.
- `.handover/config.yaml` symlinks that resolve outside the project are not read; the default `stale_after_days` is used with a warning.
- Reserved task IDs (`save`/`load`/`brief`/`list`/`archive`/`restore`/`analysis`) are rejected by `fingerprint`, `check`, `status-guard`, and `stats`.
- `fingerprint` and `check` report `content_hashed_files`, `git_status_dirs`, and `coverage_note` separately. Documentation now states that directory scope filters git status entries and does not hash every file in those directories; `check` also does not hash the task body.

## Validation

- Static validator: PASS.
- Fixture suite: 82/82 PASS (27 new cases covering the v1.1.2 fixes and the two documented scope boundaries).
- `SHA256SUMS.txt`: 15/15 OK.
- Headless v1.1.2 E2E: PASS in temporary git projects. The main matrix used a project-local copy renamed to `handover-v112` to avoid a global v1.1.1 shadow; after the matrix, the global v1.1.1 copy was backed up and replaced with v1.1.2, and the exact `/handover` chain was re-checked in a new project with no project-level skill. Covered: new save → fresh load (read-only) → modify → load (`changed`) → save (new baseline, `matched`); completed-task guard; legacy migration branch; archive/restore record-group move with baseline preserved; `list --all`; `brief`; `--out` refusal; `analysis` content probe. Details in `handover/E2E_TEST_RESULTS.md`.
- Not covered: real business project, actual 1.0.0 artifact, concurrency, interactive permission modes, archive/restore failure injection, and the full 122-item checklist.

## Scope and limitations

- `check` still covers only declared content hashes plus git status for declared directories. A same-directory file not listed in `files`, whose content changes without changing its git status, can remain `matched`.
- `check` does not hash the task body; editing only the body while keeping frontmatter and the sidecar unchanged can remain `matched`.
- The v1.1.2 E2E is one Claude Code version/model/gateway; it is not a cross-model or cross-permission-mode guarantee. The exact `/handover` chain was re-checked after replacing the global v1.1.1 copy with v1.1.2; the previous global copy was backed up outside the skill directory.
- Real business-project trial, real 1.0.0 artifact migration, concurrency, archive/restore failure paths, and normal interactive permission modes remain unvalidated.
- No full code audit or security guarantee. Checksums verify content consistency; static checks verify only their listed rules; fixtures and E2E evidence have separate bounded scopes.

## Key hashes

| File | SHA-256 |
|---|---|
| `handover/SKILL.md` | `46f80c24288d54977bd1dd2a4ad5b4c98a1b909d7fc73299aa59c133e252c96e` |
| `handover/scripts/handover.py` | `dff71bddeb79ca28cb3696092de94996808fd935ca94b3e4b7b4f62b0b0e663d` |
| `handover/README.md` | `2dae4a15f17f55ba8ce418db9e68e9d5f28677de2d08d293d9c46e6c6e707700` |
| `handover/CHECKLIST.md` | `e295f4f8fa561fb4e473bbb80bc81af64d08f15bc8f7690f3dbeb1e4033021f5` |

The full package manifest is `handover/SHA256SUMS.txt`.

---

# handover v1.1.1 (historical release)

- Date: 2026-11-03
- Status: **v1.1.1** — patch release over `v1.1.0`.
- Install: copy `handover/` to `~/.claude/skills/handover/`; back up any existing skill first.
- Package integrity: `handover/SHA256SUMS.txt` covers the 15 skill package files. No ZIP is committed; build a source archive from the review commit if needed.

## What changed since v1.1.0

- `check` no longer returns `matched` when task `schema`, `task_id`, `project_root`, `fingerprint_file`, or `fingerprint_sha256` is missing or disagrees with the sidecar/current project.
- `fingerprint` refuses an empty declared scope; a 0-file sidecar can no longer produce a vacuous `matched`.
- Root-level declared files scope direct root entries only; subdirectories still scope their subtrees. `--scope-dir .` means root-directory entries. Existing v1.1.0 sidecars without root scope are checked with it added conservatively; re-save to record the baseline explicitly.
- `fingerprint` refuses a symlinked sidecar output path or a symlinked `.handover`, preventing a write through a link from overwriting a business file.
- `list` stops when `.handover` resolves outside the project and does not read individual task/archive files that resolve outside the project.
- `.handover/config.yaml` works without `---` frontmatter delimiters; invalid `stale_after_days` warns and falls back to 14.
- `ignore-check` probes `.handover/` with a trailing slash, so a first save before the directory exists no longer reports a false `not-ignored` warning.
- `matched` output reports `out_of_scope_changes` and states that it covers the declared scope only.
- A declared file that grows beyond the size limit and changes size is classified `changed`, not `unknown`.
- Duplicate task IDs are visible in `list` exceptions.
- Added `status-guard`: no-ID `save` only reuses active tasks; completed/cancelled/archived are not targets. New tasks default to `in-progress`; `completed` requires explicit user confirmation plus evidence; status conflicts become `blocked`. Reopening a completed task requires an explicit user request and `--reopen-authorised`.
- Fixture suite extended from 29 to 55 cases; static report and checksums regenerated.

## Validation

- Static validator: PASS.
- Fixture suite: 55/55 PASS.
- `SHA256SUMS.txt`: 15/15 OK.
- Headless v1.1.1 save/load smoke: PASS (save/load/list exit 0; load read-only, ~3k tokens; `check` reported changed only for untracked harness files created after save). The smoke reproduced the first-save `ignore-check` false positive; fixed and covered by fixtures. The full change → load → save chain was not rerun.
- Status-selection E2E (v1.1.1 patched): PASS. With two completed tasks and a session saying “continue old-task-2”, `save` created a new in-progress `project-init-wrapup` and left both completed tasks unchanged; `status-guard` was used for the new target.

## Scope and limitations

- Real business-project trial: not executed.
- Actual 1.0.0 artifact migration: not executed.
- Concurrency and normal interactive permission modes: not validated; do not run multiple writers on the same task.
- Full 110-item `handover/CHECKLIST.md`: not executed end-to-end.
- `.claude/` is excluded from the fingerprint scope; configuration changes under `.claude/` are outside consistency checks.
- No full code audit or security guarantee. Checksums verify content consistency; static checks verify only their listed rules; fixtures and E2E evidence have separate bounded scopes.
- Headless runs used `--permission-mode dontAsk` and the configured custom gateway; results are behavioral evidence for this environment, not a guarantee across models or permission modes.
- Archive/restore remain instruction-based; real file-move failure behavior is not scripted or fully validated.

## Key hashes

| File | SHA-256 |
|---|---|
| `handover/SKILL.md` | `5449ca299c29fa7dae022629bcb3a1deebf8d8b22cd46c96ea5329e1f365549b` |
| `handover/scripts/handover.py` | `274d961388c823ca5b73479e97a9b85c6e15bafd554a6617d0e484b5cb8e97d7` |
| `handover/README.md` | `2496de847d1b19075e5b1944bda5049933974a8c9fa48bb1d10d99871a80e923` |
| `handover/CHECKLIST.md` | `37e2d63390ca7acb7b7c57707b18013a8489b9c7db78890e0f5dbd496f95aceb` |

The full package manifest is `handover/SHA256SUMS.txt`.

---

# handover v1.1.0 (historical release)

- Date: 2026-11-03
- Status: **v1.1.0** — supersedes `v1.1.0-rc.1`.
- Install: copy `handover/` to `~/.claude/skills/handover/`; back up any existing skill first.
- Package integrity: `handover/SHA256SUMS.txt` covers the 15 skill package files. No ZIP is built for this release; install from the repository or a source archive.

## What changed since v1.1.0-rc.1

- `SKILL.md` is now a lightweight router; mode details live in `references/` and load only when needed.
- `brief`/`load` use summary-first read budgets while preserving a mandatory quality checklist.
- `load --deep` is an explicit full-fidelity mode: full task body + full “接手必读”, 30k-token cap, check-first, and read reporting. It is never the default.
- `save` runs `check` on the existing record before writing and reconciles changed/unknown/stale instead of trusting the old narrative.
- `brief` reads project background plus a summary-level project state (task-list titles/status, recent commits, git status) without reading task bodies.
- Token hygiene: compact Markdown, no decorative whitespace or separators, cross-file dedup, and `path#symbol` references.
- New helpers: `stats` (task-document token distribution) and `analysis` (system prompt, MCP tool schemas, transcript blobs, and config sizes).
- Validator and fixture tests extended; reports and checksums regenerated.

## Validation

- Static validator: PASS.
- Fixture suite: 29/29 PASS.
- `SHA256SUMS.txt`: 15/15 OK.
- Headless `/handover brief` E2E in a temporary project: read 3 files / ~0.7k tokens; skipped the task body; quality checklist covered.
- Context analysis: `rea` MCP tool schemas were ~257.5k tokens before disabling and 0 after; the request prefix after disabling was ~2.6% of a 1M window.
- The committed `handover/E2E_TEST_RESULTS.md` remains the rc.1 record; the full save/load/change E2E was not rerun for v1.1.0.

## Scope and limitations

- Real business-project trial: not executed.
- Actual 1.0.0 artifact migration: not executed.
- Concurrency and normal interactive permission modes: not validated; do not run multiple writers on the same task.
- Full 95-item `handover/CHECKLIST.md`: not executed end-to-end.
- `.claude/` is excluded from the fingerprint scope; configuration changes under `.claude/` are outside consistency checks.
- No full code audit or security guarantee. Checksums verify content consistency; static checks verify only their listed rules; fixtures and E2E evidence have separate bounded scopes.
- Headless runs used `--permission-mode dontAsk` and the configured custom gateway; results are behavioral evidence for this environment, not a guarantee across models or permission modes.

## Key hashes

| File | SHA-256 |
|---|---|
| `handover/SKILL.md` | `d5b9afcf2bb4228f2df50367441412ca0f3a906e3b472c49a484543e61f9df57` |
| `handover/scripts/handover.py` | `1990a4b8ea74b386d41628b4a81cf51301b79f4fecd0e77794eeeb65bd4077b8` |
| `handover/README.md` | `8bcf068e3c21210a17af676e774f5590f57dbd499311740c38cd911d846286e2` |
| `handover/CHECKLIST.md` | `d6c4fb3294f13ebc8b95f533072ba123c85042fa899d54d81b7464a05e444b03` |

The full package manifest is `handover/SHA256SUMS.txt` (as tagged for v1.1.0).
