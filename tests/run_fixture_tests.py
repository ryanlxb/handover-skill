#!/usr/bin/env python3
"""Fixture-level tests for handover-v1.1/scripts/handover.py.

These tests do not install or execute the skill. They exercise the optional
helper's fingerprint/check semantics in temporary git and non-git projects.
Output is a Markdown report; exit 0 only when every case passes.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "handover" / "scripts" / "handover.py"

TASK_TEMPLATE = """---
schema: 1
snapshot_id: null
task_id: login
title: Login task
status: in-progress
updated_at: 2026-11-01T10:00:00+08:00
migrated_at: null
archived_at: null
restored_at: null
project_root: {root}
branch: main
head: 0000000
worktree: {root}
fingerprint_file: .handover/login.fingerprint.json
fingerprint_sha256: null
fingerprint_scope: relevant-files+git
fingerprint_checked_at: null
---

# Login task

## 快速接手摘要
- 目标：fixture
"""

CASES: List[Dict[str, object]] = []
TEMP_PATHS: List[Path] = []


def run(args: List[str], cwd: Optional[Path] = None) -> Tuple[int, str, str]:
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    proc = subprocess.run(
        [sys.executable, "-I", str(SCRIPT)] + args,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr


def git(root: Path, *args: str) -> Tuple[int, str, str]:
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    proc = subprocess.run(
        ["git", "-C", str(root)] + list(args),
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr


def make_root(with_git: bool = True) -> Path:
    root = Path(tempfile.mkdtemp(prefix="handover-fixture-"))
    TEMP_PATHS.append(root)
    (root / "src").mkdir()
    (root / ".handover").mkdir()
    (root / "src" / "login.ts").write_text("export const login = 1;\n", encoding="utf-8")
    (root / "src" / "other.ts").write_text("export const other = 1;\n", encoding="utf-8")
    (root / ".handover" / "config.yaml").write_text("stale_after_days: 14\n", encoding="utf-8")
    (root / ".handover" / "login.md").write_text(TASK_TEMPLATE.format(root=root), encoding="utf-8")
    if with_git:
        git(root, "init", "-q")
        git(root, "config", "user.email", "fixture@example.com")
        git(root, "config", "user.name", "Fixture")
        git(root, "add", ".")
        git(root, "commit", "-qm", "init")
    return root


def paths_file(root: Path, rels: List[str]) -> Path:
    path = root.parent / (root.name + "-paths.txt")
    path.write_text("\n".join(rels) + "\n", encoding="utf-8")
    TEMP_PATHS.append(path)
    return path


def fingerprint(root: Path, rels: List[str]) -> Tuple[str, str, str]:
    pfile = paths_file(root, rels)
    code, out, err = run(["fingerprint", "--root", str(root), "--task", "login", "--paths", str(pfile)])
    if code != 0:
        raise RuntimeError("fingerprint failed: %s %s" % (out, err))
    snapshot = re.search(r"^snapshot_id: (.+)$", out, re.M)
    sidecar_sha = re.search(r"^sidecar_sha256: (.+)$", out, re.M)
    if not snapshot or not sidecar_sha:
        raise RuntimeError("fingerprint output missing fields: %s" % out)
    return snapshot.group(1).strip(), sidecar_sha.group(1).strip(), out


def bind_task(root: Path, snapshot_id: str, sidecar_sha: str) -> None:
    task = root / ".handover" / "login.md"
    text = task.read_text(encoding="utf-8")
    text = text.replace("snapshot_id: null", "snapshot_id: %s" % snapshot_id)
    text = text.replace("fingerprint_sha256: null", "fingerprint_sha256: %s" % sidecar_sha)
    text = text.replace("fingerprint_checked_at: null", "fingerprint_checked_at: 2026-11-02T10:00:00+08:00")
    task.write_text(text, encoding="utf-8")


def check(root: Path, sidecar_sha: str, task_file: Optional[Path] = None) -> Tuple[int, str, str]:
    args = ["check", "--root", str(root), "--task", "login", "--expected-sha256", sidecar_sha]
    if task_file:
        args += ["--task-file", str(task_file)]
    return run(args)


def record(name: str, expected: str, code: int, out: str, err: str, passed: bool) -> None:
    first = ""
    for line in out.splitlines():
        if line.startswith(("consistency:", "error:")):
            first = line.strip()
            break
    CASES.append(
        {
            "name": name,
            "expected": expected,
            "actual": first or ("exit %d" % code),
            "passed": passed,
            "out": out.strip(),
            "err": err.strip(),
        }
    )


def case_matched() -> None:
    root = make_root()
    snap, sha, _ = fingerprint(root, ["src/login.ts"])
    bind_task(root, snap, sha)
    code, out, err = check(root, sha)
    record("完整基线，无变化", "matched, exit 0", code, out, err, code == 0 and "consistency: matched" in out)


def case_snapshot_mismatch() -> None:
    root = make_root()
    snap, sha, _ = fingerprint(root, ["src/login.ts"])
    bind_task(root, "mismatch-" + snap, sha)
    code, out, err = check(root, sha)
    record("任务与 sidecar 的 snapshot_id 不一致", "unknown, exit 2", code, out, err,
           code == 2 and "snapshot_id mismatch" in out)


def case_content_changed() -> None:
    root = make_root()
    snap, sha, _ = fingerprint(root, ["src/login.ts"])
    bind_task(root, snap, sha)
    (root / "src" / "login.ts").write_text("export const login = 2;\n", encoding="utf-8")
    code, out, err = check(root, sha)
    record("声明文件内容变化", "changed, content_changed", code, out, err,
           code == 1 and "consistency: changed" in out and "content_changed" in out)


def case_new_file_in_scope() -> None:
    root = make_root()
    snap, sha, _ = fingerprint(root, ["src/login.ts"])
    bind_task(root, snap, sha)
    (root / "src" / "new.ts").write_text("export const added = 1;\n", encoding="utf-8")
    code, out, err = check(root, sha)
    record("声明目录内新增文件", "changed, git_changed", code, out, err,
           code == 1 and "consistency: changed" in out and "git_changed" in out)


def case_deleted_file() -> None:
    root = make_root()
    snap, sha, _ = fingerprint(root, ["src/login.ts"])
    bind_task(root, snap, sha)
    (root / "src" / "login.ts").unlink()
    code, out, err = check(root, sha)
    record("声明文件被删除", "changed, missing", code, out, err,
           code == 1 and "consistency: changed" in out and "missing" in out)


def case_renamed_file() -> None:
    root = make_root()
    snap, sha, _ = fingerprint(root, ["src/login.ts"])
    bind_task(root, snap, sha)
    git(root, "mv", "src/login.ts", "src/renamed.ts")
    code, out, err = check(root, sha)
    record("声明文件被重命名", "changed", code, out, err,
           code == 1 and "consistency: changed" in out)


def case_staged_state() -> None:
    root = make_root()
    (root / "src" / "login.ts").write_text("export const login = 3;\n", encoding="utf-8")
    snap, sha, _ = fingerprint(root, ["src/login.ts"])
    bind_task(root, snap, sha)
    code0, out0, err0 = check(root, sha)
    if code0 != 0:
        record("暂存状态变化（前置 matched）", "matched", code0, out0, err0, False)
        return
    git(root, "add", "src/login.ts")
    code, out, err = check(root, sha)
    record("文件内容不变，暂存状态变化", "changed, git_changed, no content_changed", code, out, err,
           code == 1 and "git_changed" in out and "content_changed" not in out)


def case_head_changed() -> None:
    root = make_root()
    snap, sha, _ = fingerprint(root, ["src/login.ts"])
    bind_task(root, snap, sha)
    git(root, "commit", "--allow-empty", "-qm", "empty")
    code, out, err = check(root, sha)
    record("HEAD 变化，声明文件内容相同", "changed, git_changed", code, out, err,
           code == 1 and "git_changed" in out and "content_changed" not in out)


def case_partial_with_change() -> None:
    root = make_root()
    snap, sha, out = fingerprint(root, ["src/login.ts", "src/missing.ts"])
    bind_task(root, snap, sha)
    (root / "src" / "login.ts").write_text("export const login = 4;\n", encoding="utf-8")
    code, out2, err = check(root, sha)
    record("部分基线不可检查 + 已知内容变化", "changed, incomplete: true", code, out2, err,
           code == 1 and "consistency: changed" in out2 and "incomplete: true" in out2)


def case_partial_without_change() -> None:
    root = make_root()
    snap, sha, _ = fingerprint(root, ["src/missing.ts"])
    bind_task(root, snap, sha)
    code, out, err = check(root, sha)
    record("部分基线不可检查 + 无明确变化", "unknown, exit 2", code, out, err,
           code == 2 and "consistency: unknown" in out)


def case_no_git() -> None:
    root = make_root(with_git=False)
    snap, sha, _ = fingerprint(root, ["src/login.ts"])
    bind_task(root, snap, sha)
    code, out, err = check(root, sha)
    record("非 git 项目，无 git 基线", "unknown, exit 2", code, out, err,
           code == 2 and "consistency: unknown" in out)


def case_sidecar_sha_mismatch() -> None:
    root = make_root()
    snap, sha, _ = fingerprint(root, ["src/login.ts"])
    bind_task(root, snap, "deadbeef")
    code, out, err = check(root, sha)
    record("任务 fingerprint_sha256 与 sidecar 不一致", "unknown, exit 2", code, out, err,
           code == 2 and "unknown" in out)


def case_excluded_skill_docs() -> None:
    root = make_root()
    skill_doc = root / ".claude" / "skills" / "handover" / "SKILL.md"
    skill_doc.parent.mkdir(parents=True)
    skill_doc.write_text("# skill\n", encoding="utf-8")
    snap, sha, out = fingerprint(
        root,
        ["src/login.ts", ".claude/skills/handover/SKILL.md", ".git/config"],
    )
    sidecar = json.loads((root / ".handover" / "login.fingerprint.json").read_text(encoding="utf-8"))
    files = set(sidecar.get("files", {}))
    ok = (
        files == {"src/login.ts"}
        and ".claude/skills/handover/SKILL.md" in sidecar.get("skipped_excluded", [])
        and ".git/config" in sidecar.get("skipped_excluded", [])
    )
    record("排除 .claude/ 与 .git/", "skipped_excluded; sidecar only src/login.ts", 0, out, "",
           ok)


def case_list_title() -> None:
    root = make_root()
    code, out, err = run(["list", "--root", str(root)])
    ok = code == 0 and "| login | Login task | in-progress |" in out
    record("list 读取 frontmatter title", "title column contains Login task", code, out, err, ok)


def case_list_title_fallback() -> None:
    root = make_root()
    task = root / ".handover" / "login.md"
    text = task.read_text(encoding="utf-8")
    text = text.replace("task_id: login", "task_id: no-title")
    text = text.replace("title: Login task\n", "")
    text = text.replace("status: in-progress", "status: pending")
    (root / ".handover" / "no-title.md").write_text(text, encoding="utf-8")
    code, out, err = run(["list", "--root", str(root)])
    ok = code == 0 and "| no-title | no-title | pending |" in out
    record("title 缺失时回退 task-id", "title falls back to no-title", code, out, err, ok)


def case_ignore_check_ok() -> None:
    root = make_root()
    git(root, "rm", "-r", "--cached", "-q", ".handover")
    (root / ".gitignore").write_text(".handover/\nhandover.md\n", encoding="utf-8")
    code, out, err = run(["ignore-check", "--root", str(root)])
    ok = (
        code == 0
        and "result: ok" in out
        and ".handover/: ignored, not-tracked" in out
        and "handover.md: ignored, not-tracked" in out
    )
    record("ignore-check: 已忽略且未跟踪", "ok, exit 0", code, out, err, ok)


def case_ignore_check_warning() -> None:
    root = make_root()
    git(root, "rm", "-r", "--cached", "-q", ".handover")
    code, out, err = run(["ignore-check", "--root", str(root)])
    ok = (
        code == 1
        and "result: warning" in out
        and ".handover/: not-ignored, not-tracked" in out
        and "handover.md: not-ignored, not-tracked" in out
    )
    record("ignore-check: 未忽略", "warning, exit 1", code, out, err, ok)


def case_ignore_check_tracked() -> None:
    root = make_root()
    (root / ".gitignore").write_text(".handover/\nhandover.md\n", encoding="utf-8")
    git(root, "add", "-f", ".handover/login.md")
    git(root, "commit", "-qm", "track task data")
    code, out, err = run(["ignore-check", "--root", str(root)])
    ok = (
        code == 1
        and "result: warning" in out
        and ".handover/: ignored, tracked" in out
        and "handover.md: ignored, not-tracked" in out
    )
    record("ignore-check: 已跟踪的任务数据", "warning, exit 1", code, out, err, ok)


def case_ignore_check_not_git() -> None:
    root = make_root(with_git=False)
    code, out, err = run(["ignore-check", "--root", str(root)])
    ok = code == 0 and "result: not-git" in out
    record("ignore-check: 非 Git 项目", "not-git, exit 0", code, out, err, ok)


def _run_tests() -> int:
    tests = [
        case_matched,
        case_snapshot_mismatch,
        case_content_changed,
        case_new_file_in_scope,
        case_deleted_file,
        case_renamed_file,
        case_staged_state,
        case_head_changed,
        case_partial_with_change,
        case_partial_without_change,
        case_no_git,
        case_sidecar_sha_mismatch,
        case_excluded_skill_docs,
        case_list_title,
        case_list_title_fallback,
        case_ignore_check_ok,
        case_ignore_check_warning,
        case_ignore_check_tracked,
        case_ignore_check_not_git,
    ]
    for test in tests:
        try:
            test()
        except Exception as exc:  # noqa: BLE001 - test harness boundary
            CASES.append(
                {
                    "name": test.__name__,
                    "expected": "test completes",
                    "actual": "exception: %s" % exc,
                    "passed": False,
                    "out": "",
                    "err": str(exc),
                }
            )

    passed = sum(1 for case in CASES if case["passed"])
    print("# v1.1.0-rc.1 Fixture Test Results")
    print("")
    print("- Date (UTC): %s" % datetime.now(timezone.utc).isoformat(timespec="seconds"))
    try:
        script_display = SCRIPT.relative_to(REPO_ROOT)
    except ValueError:
        script_display = SCRIPT
    print("- Script: `%s`" % script_display)
    print("- Scope: fixture-level script tests only; no Claude Code skill execution.")
    print("- Cases: %d, passed: %d, failed: %d" % (len(CASES), passed, len(CASES) - passed))
    print("")
    print("| # | case | expected | actual | result |")
    print("|---:|---|---|---|---|")
    for i, case in enumerate(CASES, 1):
        print("| %d | %s | %s | %s | %s |" % (
            i, case["name"], case["expected"], case["actual"],
            "PASS" if case["passed"] else "FAIL",
        ))
    print("")
    failures = [case for case in CASES if not case["passed"]]
    if failures:
        print("## Failures")
        print("")
        for case in failures:
            print("### %s" % case["name"])
            print("")
            print("```text")
            print(case["out"] or "(no stdout)")
            if case["err"]:
                print("--- stderr ---")
                print(case["err"])
            print("```")
            print("")
    print("## Not covered by these fixture tests")
    print("")
    print("- Claude Code skill installation, `/handover` invocation, `/clear`, and reload.")
    print("- Archive/restore file moves and entry-link updates.")
    print("- Concurrent writers and real permission behavior.")
    return 0 if not failures else 1


def cleanup_temp_paths() -> None:
    for path in reversed(TEMP_PATHS):
        try:
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
        except OSError:
            pass


def main() -> int:
    try:
        return _run_tests()
    finally:
        cleanup_temp_paths()


if __name__ == "__main__":
    sys.exit(main())
