#!/usr/bin/env python3
"""Structural/static validator for a Handover skill directory.

Usage:
  python3 -I validate_handover.py /path/to/handover-v1.1

This does not install or execute the skill. It checks required files,
frontmatter keys, code-fence balance, local Markdown links, and a few
truncation markers. It prints a Markdown report to stdout and exits
non-zero when an error is found.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REQUIRED = [
    "SKILL.md",
    "README.md",
    "references/task-template.md",
    "references/brief-load.md",
    "references/save.md",
    "references/archive-restore.md",
    "references/data-model.md",
    "references/fingerprint.md",
    "references/analysis.md",
    "CHECKLIST.md",
    "SOURCES.md",
    "scripts/handover.py",
]

# Keep the model-facing router small; mode details live in references/.
SIZE_BUDGETS = {
    "SKILL.md": 12000,
    "references/brief-load.md": 10000,
    "references/save.md": 12000,
    "references/archive-restore.md": 8000,
    "references/data-model.md": 12000,
    "references/fingerprint.md": 8000,
    "references/analysis.md": 10000,
    "references/task-template.md": 8000,
}

REFERENCE_LINKS = [
    "references/brief-load.md",
    "references/save.md",
    "references/archive-restore.md",
    "references/data-model.md",
    "references/fingerprint.md",
    "references/analysis.md",
]

SKILL_KEYS = ["name", "description", "argument-hint", "disable-model-invocation"]
TEMPLATE_KEYS = [
    "schema",
    "snapshot_id",
    "task_id",
    "title",
    "status",
    "updated_at",
    "migrated_at",
    "archived_at",
    "restored_at",
    "project_root",
    "branch",
    "head",
    "worktree",
    "fingerprint_file",
    "fingerprint_sha256",
    "fingerprint_scope",
    "fingerprint_checked_at",
]

TRUNCATION_PATTERNS = [
    (re.compile(r"(?<![A-Za-z])hived(?![A-Za-z])"), "truncated 'archived' fragment"),
    (re.compile(r"\bTODO\b"), "TODO marker"),
]

LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def parse_frontmatter(text: str) -> Optional[Dict[str, str]]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None
    data: Dict[str, str] = {}
    for raw in lines[1:end]:
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data


def check_fences(text: str) -> Tuple[bool, int]:
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            count += 1
    return count % 2 == 0, count


def check_links(path: Path, text: str) -> List[str]:
    errors: List[str] = []
    for target in LINK_RE.findall(text):
        target = target.strip()
        if not target:
            continue
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        if "<" in target or ">" in target or target.startswith("..."):
            continue
        if target.startswith(".handover/"):
            # Documentation examples, not real files in the skill package.
            continue
        if target.startswith("VALIDATION.md"):
            continue
        candidate = (path.parent / target).resolve()
        if not candidate.exists():
            errors.append("%s: broken local link -> %s" % (path.name, target))
    return errors


def check_frontmatter(path: Path, text: str, keys: List[str], label: str) -> List[str]:
    errors: List[str] = []
    data = parse_frontmatter(text)
    if data is None:
        return ["%s: missing or unclosed frontmatter" % label]
    for key in keys:
        if key not in data:
            errors.append("%s: missing frontmatter key '%s'" % (label, key))
    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python3 -I validate_handover.py <skill-dir>", file=sys.stderr)
        return 2
    target_arg = sys.argv[1]
    root = Path(target_arg).resolve()
    errors: List[str] = []
    warnings: List[str] = []
    files_report: List[Tuple[str, int, int, str]] = []

    if not root.is_dir():
        print("error: not a directory: %s" % root, file=sys.stderr)
        return 2

    for rel in REQUIRED:
        path = root / rel
        if not path.is_file():
            errors.append("missing required file: %s" % rel)

    python_syntax_ok = True
    for py_path in sorted(root.glob("scripts/*.py")):
        try:
            compile(py_path.read_text(encoding="utf-8"), str(py_path), "exec")
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            python_syntax_ok = False
            errors.append("%s: Python syntax error: %s" % (py_path.name, exc))

    # VALIDATION.md is this report's output, not a source file. Exclude it to
    # avoid a self-referential size/fence entry.
    md_files = sorted(p for p in root.rglob("*.md") if p.name != "VALIDATION.md")
    for path in md_files:
        rel = str(path.relative_to(root))
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append("%s: cannot read: %s" % (rel, exc))
            continue
        lines = len(text.splitlines())
        size = len(text.encode("utf-8"))
        if rel in SIZE_BUDGETS and size > SIZE_BUDGETS[rel]:
            errors.append(
                "%s: exceeds size budget (%d > %d bytes)" % (rel, size, SIZE_BUDGETS[rel])
            )
        ok_fences, fence_count = check_fences(text)
        if not ok_fences:
            errors.append("%s: unbalanced code fences (%d fence lines)" % (rel, fence_count))
        for pattern, label in TRUNCATION_PATTERNS:
            if pattern.search(text):
                errors.append("%s: %s" % (rel, label))
        errors.extend(check_links(path, text))
        if rel == "SKILL.md":
            errors.extend(check_frontmatter(path, text, SKILL_KEYS, rel))
            data = parse_frontmatter(text) or {}
            hint = data.get("argument-hint", "")
            for mode in ("save", "load", "brief", "list", "archive", "restore", "analysis"):
                if mode not in hint:
                    errors.append("SKILL.md: argument-hint missing mode '%s'" % mode)
            if data.get("disable-model-invocation") != "true":
                errors.append("SKILL.md: disable-model-invocation should be true")
            for ref in REFERENCE_LINKS:
                if ref not in text:
                    warnings.append("SKILL.md: does not reference %s" % ref)
        if rel == "references/task-template.md":
            errors.extend(check_frontmatter(path, text, TEMPLATE_KEYS, rel))
            if "2026-11-02T10:30:00+08:00" in text:
                warnings.append("%s: example date present; do not copy into a real task" % rel)
        if rel == "README.md":
            if "测试声明" not in text:
                warnings.append("README.md: missing explicit test declaration section")
            if "VALIDATION.md" not in text:
                warnings.append("README.md: does not reference VALIDATION.md")
            if "E2E_TEST_RESULTS.md" not in text:
                warnings.append("README.md: does not reference E2E_TEST_RESULTS.md")
        files_report.append((rel, lines, size, "OK" if ok_fences else "FENCE-ERROR"))

    print("# v1.1.2 Validation Report")
    print("")
    print("- Date (UTC): %s" % datetime.now(timezone.utc).isoformat(timespec="seconds"))
    print("- Target: `%s`" % target_arg)
    print("- Scope: structural/static checks only; no installation, no skill execution.")
    print("")
    print("## Files")
    print("")
    print("| file | lines | bytes | fences |")
    print("|---|---:|---:|---|")
    for rel, lines, size, fence_result in files_report:
        print("| %s | %d | %d | %s |" % (rel, lines, size, fence_result))
    print("")
    print("## Checks")
    print("")
    print("- Required files: %s" % ("PASS" if not any("missing required file" in e for e in errors) else "FAIL"))
    print("- Frontmatter keys: %s" % ("FAIL" if any("frontmatter key" in e or "frontmatter" in e for e in errors) else "PASS"))
    print("- Code fences: %s" % ("FAIL" if any("code fences" in e for e in errors) else "PASS"))
    print("- Python syntax: %s" % ("PASS" if python_syntax_ok else "FAIL"))
    print("- Local links: %s" % ("FAIL" if any("broken local link" in e for e in errors) else "PASS"))
    print("- Truncation markers: %s" % ("FAIL" if any("truncated" in e or "TODO" in e for e in errors) else "PASS"))
    print("- Size budgets: %s" % ("FAIL" if any("size budget" in e for e in errors) else "PASS"))
    print("")
    if errors:
        print("## Errors")
        print("")
        for err in errors:
            print("- %s" % err)
        print("")
    else:
        print("## Errors")
        print("")
        print("- (none)")
        print("")
    if warnings:
        print("## Warnings")
        print("")
        for warning in warnings:
            print("- %s" % warning)
        print("")
    print("## Not Covered by This Validator")
    print("")
    print("- This validator does not install or execute the skill.")
    print("- Skill invocation and the minimal save/load/change chain: see `E2E_TEST_RESULTS.md`.")
    print("- Script fixture semantics: see `FIXTURE_TEST_RESULTS.md`.")
    print("- Current dynamic coverage, including controlled fixture acceptance: see `E2E_TEST_RESULTS.md`.")
    print("")
    print("Static checks do not replace end-to-end acceptance.")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
