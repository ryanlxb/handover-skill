# Handover Skill v1.1.0-rc.1 — Review Package

- Date: 2026-11-02
- Status: release candidate; controlled trial only, not a stable release
- Installable folder: `handover/`
- Review-only file: this `REVIEW.md`

## What changed from 1.0.0

- Task files now use YAML frontmatter with `schema` and `snapshot_id`.
- Added `status` / `freshness` / `consistency` as separate concepts; `stale` is a reminder, not a status or delete trigger.
- Added a fingerprint sidecar (`.handover/<task-id>.fingerprint.json`) with:
  - content SHA-256 for declared files;
  - relevant git branch/HEAD/status entries;
  - `snapshot_id` binding task markdown and sidecar to the same save.
- `check` precedence: definite change -> changed (even if incomplete); no definite change + incomplete -> unknown; complete + no change -> matched.
- Added reversible `archive` / `restore` rules; task markdown and sidecar move as one record group; no permanent delete in v1.1.
- Added unknown/corrupt record visibility in `list` (EXCEPTIONS section).
- Added 1.0.0 migration rules: `migrated_at` separate from `updated_at`; no batch rewrite; unknown stays unknown.
- Added optional stdlib-only helper: `handover/scripts/handover.py` with `list`, `fingerprint`, `check`.
- Clarified context boundaries and static-check limitations.
- Excluded `.handover/`, `handover.md`, `.claude/`, and `.git/` from the fingerprint scope.

## Suggested review order

1. `handover/README.md` — usage, boundaries, lifecycle.
2. `handover/SKILL.md` — the actual instructions the model follows.
3. `handover/references/task-template.md` — the task document schema.
4. `handover/scripts/handover.py` — optional fingerprint/list/check/ignore-check helper.
5. `handover/VALIDATION.md` — structural/static checks.
6. `handover/FIXTURE_TEST_RESULTS.md` — 19 script-level cases.
7. `handover/E2E_TEST_RESULTS.md` — real Claude Code save/load/change chain.
8. `handover/CHECKLIST.md` — remaining acceptance scenarios.

## Test status

Status snapshot as of 2026-11-02. The canonical, scoped coverage matrix is in `handover/E2E_TEST_RESULTS.md`; this table is a summary, not a second source of truth.

| Layer | Result |
|---|---|
| Structural/static (`VALIDATION.md`) | PASS; no errors |
| Script fixture (`FIXTURE_TEST_RESULTS.md`) | 19/19 PASS |
| Real Claude Code E2E (minimal chain) | PASS after a scope fix |
| Controlled fixture acceptance | PASS for no-ID load, multi-turn, A/B isolation, archive/restore, 1.0-style migration |
| Real business project, real 1.0.0 artifact, concurrency/real permission modes, full 70-item checklist | Not executed |

Controlled fixture acceptance used temporary projects and fixtures, not real business data or a real 1.0.0 artifact.

## Known caveats

- Archive/restore are instruction-based, not scripted; the record-group rules are written, but the real file-move failure behavior is still open.
- The template path is still an inline `references/task-template.md` reference. The E2E generated the full template structure from a non-skill working directory, but the exact tool call was not captured because session persistence was disabled. Treat as “likely works, verify once in a new session”.
- The E2E used a custom model gateway that printed `unrecognized_model`; the skill still executed.
- `SHA256SUMS.txt` only verifies file digests, not logic, installation, permissions, or safety.
- The first E2E record still has the old 3-file fingerprint scope; it is a test artifact, not part of this package.

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
LICENSE                    # MIT
.github/workflows/ci.yml   # static + fixture checks
handover/                  # installable skill
├── SKILL.md
├── README.md
├── references/task-template.md
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
