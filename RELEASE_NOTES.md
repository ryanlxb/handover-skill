# handover v1.1.0

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

The full package manifest is `handover/SHA256SUMS.txt`.
