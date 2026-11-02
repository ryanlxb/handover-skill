# handover v1.1.0-rc.1 — release candidate

- Date: 2026-11-02
- Status: **release candidate for controlled trial**; not a stable release.
- Install: copy `handover/` to `~/.claude/skills/handover/`; back up any existing skill first.
- Package integrity: `handover/SHA256SUMS.txt` covers the skill package; `MANIFEST.sha256` covers every file in this archive. The ZIP's own SHA-256 is in the external `.sha256` file next to the archive.

## Key hashes

| File | SHA-256 |
|---|---|
| `handover/SKILL.md` | `32fb7a4a198fb0e3140b7ba2c41e550adcc66f908b7aa24f1329fd75fe4a994d` |
| `handover/scripts/handover.py` | `be63a78545aa208bc5892603842a7c6d8431151e4c94fe8c9c5962e8ff807e1a` |
| `handover/README.md` | `9a137e4502b6becdcdd21face8091b7c996545a2687acd026b952b70ecef9736` |
| `handover/CHECKLIST.md` | `90a078d6a039da1e1303cb509fffebaf5e824b2d467166acbd316893d973e7e4` |

## Acceptance summary

- Static validator: PASS, no errors.
- Fixture suite: 19/19 PASS, including four `ignore-check` cases.
- Minimal save/load on the installed RC: PASS (`check` matched; fresh-process load restored the goal and remained read-only).
- No-ID selection smoke on the installed RC: PASS (unique fresh `in-progress` auto-selected; read-only).
- Controlled fixture acceptance: no-ID load matrix, multi-turn handover, A/B isolation, archive/restore, and 1.0-style migration passed; see `handover/E2E_TEST_RESULTS.md`.
- The 1.0-style migration used a file without YAML frontmatter; it is not an actual 1.0.0 artifact.

## Scope and limitations

- Real business-project trial: not executed.
- Actual 1.0.0 artifact migration: not executed.
- Concurrency and normal interactive permission modes: not validated; do not run multiple writers on the same task.
- Full 70-item `CHECKLIST.md`: not executed.
- `.claude/` is excluded from the fingerprint scope in this version; configuration changes under `.claude/` are outside consistency checks. This is a current limitation, not a claim that all project configuration is irrelevant.
- No full code audit or security guarantee. Checksums verify content consistency; static checks verify only their listed rules; fixtures and E2E evidence have separate bounded scopes.
- Headless runs used `--permission-mode dontAsk` and the configured custom gateway, which printed `unrecognized_model`; results are behavioral evidence for this environment, not a guarantee across models or permission modes.

## Corrections included

- Save-time `check` wording is narrowed: it verifies that the current scene matches the just-generated baseline and that the task/sidecar binding is intact; it does not prove the narrative semantically matches the code or that code was unchanged while the body was composed.
- Git ignore safety: `ignore-check` checks whether `.handover/` and `handover.md` are ignored and untracked. `save`/`archive`/`restore` remind the user; the skill does not modify `.gitignore` or run `git rm`.
- Archive/restore no longer allows “user chooses and bears verification” as a substitute for migrating old files first.
- Migration reports use “body content preserved”; “byte-identical” is only claimed after an actual byte comparison.
