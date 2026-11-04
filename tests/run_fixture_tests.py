#!/usr/bin/env python3
"""Fixture-level tests for handover-v1.1/scripts/handover.py.

These tests do not install or execute the skill. They exercise the optional
helper's fingerprint/check semantics in temporary git and non-git projects.
Output is a Markdown report; exit 0 only when every case passes.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
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


def run(
    args: List[str],
    cwd: Optional[Path] = None,
    env_extra: Optional[Dict[str, str]] = None,
) -> Tuple[int, str, str]:
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    if env_extra:
        env.update(env_extra)
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


def fingerprint(
    root: Path, rels: List[str], extra: Optional[List[str]] = None
) -> Tuple[str, str, str]:
    pfile = paths_file(root, rels)
    args = ["fingerprint", "--root", str(root), "--task", "login", "--paths", str(pfile)]
    if extra:
        args.extend(extra)
    code, out, err = run(args)
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


def set_task_text(root: Path, old: str, new: str) -> None:
    task = root / ".handover" / "login.md"
    text = task.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError("task text not found: %s" % old)
    task.write_text(text.replace(old, new), encoding="utf-8")


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
    snap, sha, fp_out = fingerprint(root, ["src/login.ts"])
    sidecar = json.loads(
        (root / ".handover" / "login.fingerprint.json").read_text(encoding="utf-8")
    )
    overall_ok = (
        sidecar.get("overall") == "partial"
        and sidecar.get("git", {}).get("available") is False
    )
    bind_task(root, snap, sha)
    code, out, err = check(root, sha)
    ok = code == 2 and "consistency: unknown" in out and overall_ok
    record(
        "非 git 项目：overall=partial、check unknown",
        "partial; unknown exit 2",
        code,
        out + "\n---\n" + fp_out,
        err,
        ok,
    )


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


def case_ignore_check_missing_dir() -> None:
    root = make_root()
    git(root, "rm", "-r", "--cached", "-q", ".handover")
    shutil.rmtree(root / ".handover")
    (root / ".gitignore").write_text(".handover/\nhandover.md\n", encoding="utf-8")
    code, out, err = run(["ignore-check", "--root", str(root)])
    ok = (
        code == 0
        and "result: ok" in out
        and ".handover/: ignored, not-tracked" in out
    )
    record("ignore-check: .handover 尚未创建时仍识别目录规则", "ok, exit 0", code, out, err, ok)


def case_ignore_check_not_git() -> None:
    root = make_root(with_git=False)
    code, out, err = run(["ignore-check", "--root", str(root)])
    ok = code == 0 and "result: not-git" in out
    record("ignore-check: 非 Git 项目", "not-git, exit 0", code, out, err, ok)


def status_guard(root: Path, task: str = "login", extra: Optional[List[str]] = None) -> Tuple[int, str, str]:
    args = ["status-guard", "--root", str(root), "--task", task]
    if extra:
        args.extend(extra)
    return run(args)


def case_status_guard_absent() -> None:
    root = make_root()
    code, out, err = status_guard(root, "new-task")
    ok = code == 0 and "status: absent" in out and "new-task-allowed" in out
    record("status-guard：任务不存在允许新建", "new-task-allowed, exit 0", code, out, err, ok)


def case_status_guard_active() -> None:
    root = make_root()
    code, out, err = status_guard(root)
    ok = code == 0 and "status: in-progress" in out and "active-reuse-allowed" in out
    record("status-guard：active 任务允许复用", "active-reuse-allowed, exit 0", code, out, err, ok)


def case_status_guard_completed() -> None:
    root = make_root()
    set_task_text(root, "status: in-progress", "status: completed")
    code, out, err = status_guard(root)
    ok = code == 1 and "blocked-completed-task" in out
    record("status-guard：completed 任务阻止 save", "blocked, exit 1", code, out, err, ok)


def case_status_guard_cancelled() -> None:
    root = make_root()
    set_task_text(root, "status: in-progress", "status: cancelled")
    code, out, err = status_guard(root)
    ok = code == 1 and "blocked-completed-task" in out
    record("status-guard：cancelled 任务阻止 save", "blocked, exit 1", code, out, err, ok)


def case_status_guard_reopen() -> None:
    root = make_root()
    set_task_text(root, "status: in-progress", "status: completed")
    code, out, err = status_guard(root, extra=["--reopen-authorised"])
    ok = code == 0 and "reopen-authorised" in out
    record("status-guard：显式授权后可重开", "reopen-authorised, exit 0", code, out, err, ok)


def case_status_guard_unknown() -> None:
    root = make_root()
    set_task_text(root, "status: in-progress", "status: unknown")
    code, out, err = status_guard(root)
    ok = code == 2 and "result: unknown" in out
    record("status-guard：unknown 状态拒绝", "unknown, exit 2", code, out, err, ok)


def case_status_guard_outside() -> None:
    root = make_root()
    outside = root.parent / (root.name + "-outside.md")
    outside.write_text("# outside\n", encoding="utf-8")
    TEMP_PATHS.append(outside)
    code, out, err = status_guard(root, extra=["--task-file", str(outside)])
    ok = code == 2 and "outside project root" in out
    record("status-guard：任务文件在项目外", "unknown, exit 2", code, out, err, ok)


def case_stats_text() -> None:
    root = make_root()
    code, out, err = run(["stats", "--root", str(root), "--task", "login"])
    ok = (
        code == 0
        and "approx_tokens:" in out
        and "frontmatter:" in out
        and "decorative_lines:" in out
        and "快速接手摘要" in out
        and "sections (tokens, percent, lines):" in out
    )
    record("stats 文本输出：frontmatter + section 分布", "exit 0, contains sections", code, out, err, ok)


def case_stats_json() -> None:
    root = make_root()
    code, out, err = run(["stats", "--root", str(root), "--task", "login", "--json"])
    ok = False
    detail = out
    if code == 0:
        try:
            data = json.loads(out)
            sections = data.get("sections") or []
            fm = data.get("frontmatter") or {}
            total_pct = float(fm.get("percent", 0)) + sum(
                float(section.get("percent", 0)) for section in sections
            )
            ok = (
                data.get("task_id") == "login"
                and int(data.get("approx_tokens", 0)) > 0
                and data.get("decorative_lines") == 0
                and isinstance(sections, list)
                and bool(sections)
                and abs(total_pct - 100.0) <= 0.5
            )
        except (ValueError, TypeError) as exc:
            detail = "json parse error: %s\n%s" % (exc, out)
    record("stats --json：合法 JSON，percent 合计约 100", "exit 0, JSON valid", code, detail, err, ok)


def case_stats_missing() -> None:
    root = make_root()
    code, out, err = run(["stats", "--root", str(root), "--task", "missing"])
    ok = code == 2 and "not found" in err
    record("stats：任务文件缺失", "exit 2, error", code, out, err, ok)


def case_stats_outside() -> None:
    root = make_root()
    outside = root.parent / (root.name + "-outside.md")
    outside.write_text("# outside\n", encoding="utf-8")
    TEMP_PATHS.append(outside)
    code, out, err = run(
        ["stats", "--root", str(root), "--task", "login", "--task-file", str(outside)]
    )
    ok = code == 2 and "outside project root" in err
    record("stats：task-file 在项目外", "exit 2, error", code, out, err, ok)


def case_stats_invalid_task() -> None:
    root = make_root()
    code, out, err = run(["stats", "--root", str(root), "--task", "../bad"])
    ok = code == 2 and "invalid task-id" in err
    record("stats：非法 task-id", "exit 2, error", code, out, err, ok)


def write_transcript(
    root: Path, shapes: List[Dict[str, object]], blobs: List[Dict[str, object]]
) -> Path:
    path = root / "session.jsonl"
    lines: List[str] = []
    for index, shape in enumerate(shapes):
        lines.append(
            json.dumps(
                {
                    "type": "api-request-shape",
                    "timestamp": "2026-11-03T00:00:0%dZ" % index,
                    "shape": shape,
                },
                ensure_ascii=False,
            )
        )
    lines.append(
        json.dumps(
            {
                "type": "api-request",
                "timestamp": "2026-11-03T00:00:09Z",
                "params": {"model": "demo-model"},
            },
            ensure_ascii=False,
        )
    )
    for index, message in enumerate(blobs):
        lines.append(
            json.dumps(
                {"type": "api-request-blob", "hash": "h%d" % index, "message": message},
                ensure_ascii=False,
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def analysis_fixture() -> Tuple[Path, Path]:
    root = make_root()
    shape_with = {
        "system": [{"type": "text", "text": "system prompt"}],
        "tools": [
            {"name": "mcp__demo__big", "description": "x" * 3000, "input_schema": {"type": "object"}},
            {"name": "Bash", "description": "y" * 100, "input_schema": {"type": "object"}},
        ],
    }
    shape_without = {
        "system": [{"type": "text", "text": "system prompt"}],
        "tools": [{"name": "Bash", "description": "y" * 100, "input_schema": {"type": "object"}}],
    }
    blobs = [
        {"role": "user", "content": "hello"},
        {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {"cmd": "ls"}}],
        },
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "x" * 2000}],
        },
    ]
    return root, write_transcript(root, [shape_with, shape_without], blobs)


def case_analysis_text() -> None:
    root, transcript = analysis_fixture()
    code, out, err = run(["analysis", "--root", str(root), "--transcript", str(transcript)])
    ok = (
        code == 0
        and "request prefix" in out
        and "shape changes" in out
        and "demo" in out
        and "system_prompt" in out
        and "recommendations:" in out
    )
    record("analysis 文本输出：tool schema + shape delta", "exit 0, contains groups", code, out, err, ok)


def case_analysis_json() -> None:
    root, transcript = analysis_fixture()
    code, out, err = run(
        ["analysis", "--root", str(root), "--transcript", str(transcript), "--json"]
    )
    ok = False
    detail = out
    if code == 0:
        try:
            data = json.loads(out)
            groups = {
                group.get("server"): group
                for group in data.get("request_prefix", {}).get("tools", {}).get("groups", [])
            }
            changes = data.get("shape_changes") or []
            ok = (
                "builtin" in groups
                and any(change.get("server") == "demo" and change.get("delta", 0) < 0 for change in changes)
                and isinstance(data.get("recommendations"), list)
                and "transcript_blobs" in data
            )
        except (ValueError, TypeError) as exc:
            detail = "json parse error: %s\n%s" % (exc, out)
    record("analysis --json：分组和 shape delta", "exit 0, JSON valid", code, detail, err, ok)


def case_analysis_missing_transcript() -> None:
    root = make_root()
    code, out, err = run(
        ["analysis", "--root", str(root), "--transcript", str(root / "missing.jsonl")]
    )
    ok = code == 2 and "transcript not found" in err
    record("analysis：显式 transcript 缺失", "exit 2, error", code, out, err, ok)


def case_analysis_no_transcript() -> None:
    root = make_root()
    code, out, err = run(["analysis", "--root", str(root)])
    ok = code == 0 and "transcript: (not found)" in out
    record("analysis：无 transcript 时仍给出配置报告", "exit 0, not found note", code, out, err, ok)


def case_stats_no_frontmatter() -> None:
    root = make_root()
    plain = root / ".handover" / "plain.md"
    plain.write_text("# Plain\n\n## A\nalpha\n\n---\n\n## B\nbeta\n", encoding="utf-8")
    code, out, err = run(["stats", "--root", str(root), "--task", "plain", "--json"])
    ok = False
    if code == 0:
        try:
            data = json.loads(out)
            sections = data.get("sections") or []
            names = {section.get("section") for section in sections}
            ok = (
                int(data.get("frontmatter", {}).get("approx_tokens", -1)) == 0
                and data.get("decorative_lines") == 1
                and {"A", "B"}.issubset(names)
            )
        except (ValueError, TypeError):
            ok = False
    record("stats：无 frontmatter 的文档", "exit 0, frontmatter=0, decorative=1", code, out, err, ok)


def case_config_plain_yaml() -> None:
    root = make_root()
    recent = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(timespec="seconds")
    set_task_text(root, "updated_at: 2026-11-01T10:00:00+08:00", "updated_at: %s" % recent)
    (root / ".handover" / "config.yaml").write_text("stale_after_days: 1\n", encoding="utf-8")
    code, out, err = run(["list", "--root", str(root)])
    ok_plain = code == 0 and "| login | Login task | in-progress | stale |" in out
    (root / ".handover" / "config.yaml").write_text(
        "---\nstale_after_days: 1\n", encoding="utf-8"
    )
    code2, out2, err2 = run(["list", "--root", str(root)])
    ok_marker = code2 == 0 and "| login | Login task | in-progress | stale |" in out2
    record(
        "config.yaml 无分隔符/无闭合分隔符仍生效",
        "stale, exit 0",
        code2,
        out + "\n---\n" + out2,
        err + "\n---\n" + err2,
        ok_plain and ok_marker,
    )


def case_config_invalid_warning() -> None:
    root = make_root()
    recent = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(timespec="seconds")
    set_task_text(root, "updated_at: 2026-11-01T10:00:00+08:00", "updated_at: %s" % recent)
    (root / ".handover" / "config.yaml").write_text("stale_after_days: 0\n", encoding="utf-8")
    code, out, err = run(["list", "--root", str(root)])
    ok = code == 0 and "invalid stale_after_days" in err and "| fresh |" in out
    record("无效 config 告警并使用默认 14", "warning + fresh", code, out, err, ok)


def case_check_missing_fingerprint_file() -> None:
    root = make_root()
    snap, sha, _ = fingerprint(root, ["src/login.ts"])
    bind_task(root, snap, sha)
    set_task_text(
        root,
        "fingerprint_file: .handover/login.fingerprint.json",
        "fingerprint_file: null",
    )
    code, out, err = check(root, sha)
    ok = code == 2 and "fingerprint_file missing" in out
    record("任务缺少 fingerprint_file 绑定", "unknown, exit 2", code, out, err, ok)


def case_check_missing_fingerprint_sha() -> None:
    root = make_root()
    snap, sha, _ = fingerprint(root, ["src/login.ts"])
    bind_task(root, snap, sha)
    set_task_text(root, "fingerprint_sha256: %s" % sha, "fingerprint_sha256: null")
    code, out, err = check(root, sha)
    ok = code == 2 and "fingerprint_sha256 missing" in out
    record("任务缺少 fingerprint_sha256 绑定", "unknown, exit 2", code, out, err, ok)


def case_check_task_id_mismatch() -> None:
    root = make_root()
    snap, sha, _ = fingerprint(root, ["src/login.ts"])
    bind_task(root, snap, sha)
    set_task_text(root, "task_id: login", "task_id: other")
    code, out, err = check(root, sha)
    ok = code == 2 and "task_id mismatch" in out
    record("任务 frontmatter task_id 不一致", "unknown, exit 2", code, out, err, ok)


def case_check_unsupported_schema() -> None:
    root = make_root()
    snap, sha, _ = fingerprint(root, ["src/login.ts"])
    bind_task(root, snap, sha)
    set_task_text(root, "schema: 1", "schema: 2")
    code, out, err = check(root, sha)
    ok = code == 2 and "schema" in out
    record("任务 schema 不受支持", "unknown, exit 2", code, out, err, ok)


def case_check_schema_bool() -> None:
    root = make_root()
    snap, sha, _ = fingerprint(root, ["src/login.ts"])
    bind_task(root, snap, sha)
    set_task_text(root, "schema: 1", "schema: true")
    code, out, err = check(root, sha)
    ok = code == 2 and "schema" in out
    record("任务 schema 为布尔值", "unknown, exit 2", code, out, err, ok)


def case_check_project_root_mismatch() -> None:
    root = make_root()
    snap, sha, _ = fingerprint(root, ["src/login.ts"])
    bind_task(root, snap, sha)
    set_task_text(root, "project_root: %s" % root, "project_root: %s-other" % root)
    code, out, err = check(root, sha)
    ok = code == 2 and "project_root mismatch" in out
    record("任务 project_root 不一致", "unknown, exit 2", code, out, err, ok)


def case_fingerprint_empty_scope() -> None:
    root = make_root()
    pfile = paths_file(root, [])
    code, out, err = run(
        ["fingerprint", "--root", str(root), "--task", "login", "--paths", str(pfile)]
    )
    ok = code == 2 and "no files" in err.lower()
    record("fingerprint 拒绝空声明范围", "exit 2, error", code, out, err, ok)


def case_root_scope_new_file() -> None:
    root = make_root()
    (root / "README.md").write_text("hello\n", encoding="utf-8")
    git(root, "add", "README.md")
    git(root, "commit", "-qm", "readme")
    snap, sha, _ = fingerprint(root, ["README.md"])
    bind_task(root, snap, sha)
    (root / "docs").mkdir()
    (root / "docs" / "note.md").write_text("note\n", encoding="utf-8")
    code_sub, out_sub, err_sub = check(root, sha)
    ok_sub = code_sub == 0 and "consistency: matched" in out_sub
    (root / "NEW.md").write_text("new\n", encoding="utf-8")
    code_new, out_new, err_new = check(root, sha)
    ok_new = code_new == 1 and "consistency: changed" in out_new and "git_changed" in out_new
    record(
        "根目录声明只覆盖直属文件：子目录新增不触发，根目录新增触发",
        "subdir matched; root changed",
        code_new,
        out_sub + "\n---\n" + out_new,
        err_sub + "\n---\n" + err_new,
        ok_sub and ok_new,
    )


def case_check_empty_sidecar() -> None:
    root = make_root()
    snap, sha, _ = fingerprint(root, ["src/login.ts"])
    bind_task(root, snap, sha)
    sidecar = root / ".handover" / "login.fingerprint.json"
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data["files"] = {}
    sidecar.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    empty_sha = hashlib.sha256(sidecar.read_bytes()).hexdigest()
    set_task_text(root, "fingerprint_sha256: %s" % sha, "fingerprint_sha256: %s" % empty_sha)
    code, out, err = check(root, empty_sha)
    ok = code == 2 and "no files" in out
    record("sidecar 文件集为空", "unknown, exit 2", code, out, err, ok)


def case_check_legacy_root_scope() -> None:
    root = make_root()
    (root / "README.md").write_text("hello\n", encoding="utf-8")
    git(root, "add", "README.md")
    git(root, "commit", "-qm", "readme")
    snap, sha, _ = fingerprint(root, ["README.md"])
    bind_task(root, snap, sha)
    sidecar = root / ".handover" / "login.fingerprint.json"
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data["git"]["scope_dirs"] = [
        directory for directory in data["git"].get("scope_dirs", []) if directory != "."
    ]
    sidecar.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    legacy_sha = hashlib.sha256(sidecar.read_bytes()).hexdigest()
    set_task_text(root, "fingerprint_sha256: %s" % sha, "fingerprint_sha256: %s" % legacy_sha)
    (root / "NEW.md").write_text("new\n", encoding="utf-8")
    code, out, err = check(root, legacy_sha)
    ok = code == 1 and "consistency: changed" in out and "git_changed" in out
    record(
        "旧 sidecar 缺根目录 scope 时仍能检测根目录新增",
        "changed, git_changed",
        code,
        out,
        err,
        ok,
    )


def case_list_handover_symlink_outside() -> None:
    a = make_root()
    b = make_root()
    set_task_text(b, "title: Login task", "title: Secret task")
    shutil.rmtree(a / ".handover")
    (a / ".handover").symlink_to(b / ".handover", target_is_directory=True)
    code, out, err = run(["list", "--root", str(a)])
    ok = code == 2 and "outside project root" in err and "Secret task" not in out
    record("list：.handover 指向项目外", "exit 2, not read", code, out, err, ok)


def case_list_task_symlink_outside() -> None:
    a = make_root()
    b = make_root()
    set_task_text(b, "title: Login task", "title: Secret task")
    (a / ".handover" / "leak.md").symlink_to(b / ".handover" / "login.md")
    code, out, err = run(["list", "--root", str(a)])
    ok = (
        code == 0
        and "path resolves outside project root" in out
        and "Secret task" not in out
    )
    record("list：单个任务文件指向项目外", "exception, not read", code, out, err, ok)


def case_fingerprint_output_symlink() -> None:
    root = make_root()
    original = (root / "src" / "login.ts").read_text(encoding="utf-8")
    (root / ".handover" / "login.fingerprint.json").symlink_to(root / "src" / "login.ts")
    pfile = paths_file(root, ["src/login.ts"])
    code, out, err = run(
        ["fingerprint", "--root", str(root), "--task", "login", "--paths", str(pfile)]
    )
    ok = (
        code == 2
        and "symlink" in err.lower()
        and (root / "src" / "login.ts").read_text(encoding="utf-8") == original
    )
    record("fingerprint 拒绝写入符号链接 sidecar", "exit 2, file unchanged", code, out, err, ok)


def case_check_out_of_scope_note() -> None:
    root = make_root()
    snap, sha, _ = fingerprint(root, ["src/login.ts"])
    bind_task(root, snap, sha)
    (root / "docs").mkdir()
    (root / "docs" / "note.md").write_text("note\n", encoding="utf-8")
    code, out, err = check(root, sha)
    ok = (
        code == 0
        and "consistency: matched" in out
        and "out_of_scope_changes: 1" in out
    )
    record("matched 输出范围外变化计数", "matched + out_of_scope_changes", code, out, err, ok)


def case_check_size_change_over_limit() -> None:
    root = make_root()
    big = root / "src" / "big.ts"
    big.write_text("x" * 20, encoding="utf-8")
    snap, sha, _ = fingerprint(root, ["src/big.ts"], extra=["--max-bytes", "25"])
    bind_task(root, snap, sha)
    big.write_text("x" * 30, encoding="utf-8")
    code, out, err = check(root, sha)
    ok = code == 1 and "changed" in out and "size changed" in out
    record("文件超过上限但大小已变：判 changed 而非 unknown", "changed, size changed", code, out, err, ok)


def case_list_duplicate_task_id() -> None:
    root = make_root()
    shutil.copy(root / ".handover" / "login.md", root / ".handover" / "copy.md")
    code, out, err = run(["list", "--root", str(root)])
    ok = code == 0 and "duplicate task_id" in out
    record("list：重复 task_id 可见", "duplicate task_id", code, out, err, ok)


def case_list_duplicate_all_exceptions() -> None:
    root = make_root()
    shutil.copy(root / ".handover" / "login.md", root / ".handover" / "copy.md")
    code, out, err = run(["list", "--root", str(root)])
    active = out.split("## EXCEPTIONS")[0]
    ok = (
        code == 0
        and "| login |" not in active
        and "duplicate task_id (2 files)" in out
    )
    record(
        "list：重复 ID 的所有记录都进入 EXCEPTIONS",
        "no duplicate in ACTIVE",
        code,
        out,
        err,
        ok,
    )


def case_list_schema_bool_exception() -> None:
    root = make_root()
    set_task_text(root, "schema: 1", "schema: true")
    code, out, err = run(["list", "--root", str(root)])
    active = out.split("## EXCEPTIONS")[0]
    ok = code == 0 and "| login |" not in active and "unsupported schema=True" in out
    record("list：schema 为布尔值不进入 ACTIVE", "exception, not active", code, out, err, ok)


def case_fingerprint_out_business_file_refused() -> None:
    root = make_root()
    business = root / "src" / "business.py"
    original = "print('keep me')\n"
    business.write_text(original, encoding="utf-8")
    pfile = paths_file(root, ["src/login.ts"])
    code, out, err = run(
        [
            "fingerprint",
            "--root",
            str(root),
            "--task",
            "login",
            "--paths",
            str(pfile),
            "--out",
            str(business),
        ]
    )
    ok = (
        code == 2
        and "--out must be" in err
        and business.read_text(encoding="utf-8") == original
    )
    record(
        "fingerprint --out 不能覆盖业务文件",
        "exit 2, business file unchanged",
        code,
        out,
        err,
        ok,
    )


def case_fingerprint_out_task_markdown_refused() -> None:
    root = make_root()
    task = root / ".handover" / "login.md"
    original = task.read_text(encoding="utf-8")
    pfile = paths_file(root, ["src/login.ts"])
    code, out, err = run(
        [
            "fingerprint",
            "--root",
            str(root),
            "--task",
            "login",
            "--paths",
            str(pfile),
            "--out",
            str(task),
        ]
    )
    ok = (
        code == 2
        and "must end with" in err
        and task.read_text(encoding="utf-8") == original
    )
    record(
        "fingerprint --out 不能覆盖任务 Markdown",
        "exit 2, task unchanged",
        code,
        out,
        err,
        ok,
    )


def case_fingerprint_out_valid_archive_sidecar() -> None:
    root = make_root()
    pfile = paths_file(root, ["src/login.ts"])
    archive = root / ".handover" / "archive" / "login-20261103t000000z.fingerprint.json"
    code, out, err = run(
        [
            "fingerprint",
            "--root",
            str(root),
            "--task",
            "login",
            "--paths",
            str(pfile),
            "--out",
            str(archive),
        ]
    )
    ok = code == 0 and archive.is_file()
    if ok:
        try:
            data = json.loads(archive.read_text(encoding="utf-8"))
            ok = data.get("task_id") == "login" and data.get("schema") == 1
        except ValueError:
            ok = False
    record(
        "fingerprint --out 允许 .handover/archive 下的归档 sidecar",
        "exit 0, sidecar written",
        code,
        out,
        err,
        ok,
    )


def case_fingerprint_out_existing_invalid_refused() -> None:
    root = make_root()
    target = root / ".handover" / "login.fingerprint.json"
    original = (
        json.dumps(
            {
                "schema": 1,
                "task_id": "other",
                "root": str(root),
                "snapshot_id": "x",
                "files": {"a": {}},
            }
        )
        + "\n"
    )
    target.write_text(original, encoding="utf-8")
    pfile = paths_file(root, ["src/login.ts"])
    code, out, err = run(
        ["fingerprint", "--root", str(root), "--task", "login", "--paths", str(pfile)]
    )
    ok = (
        code == 2
        and "refusing to overwrite" in err
        and target.read_text(encoding="utf-8") == original
    )
    record(
        "fingerprint 拒绝覆盖其他任务的 sidecar",
        "exit 2, existing sidecar unchanged",
        code,
        out,
        err,
        ok,
    )


def case_fingerprint_out_outside_root_refused() -> None:
    root = make_root()
    outside = root.parent / (root.name + "-outside.fingerprint.json")
    TEMP_PATHS.append(outside)
    pfile = paths_file(root, ["src/login.ts"])
    code, out, err = run(
        [
            "fingerprint",
            "--root",
            str(root),
            "--task",
            "login",
            "--paths",
            str(pfile),
            "--out",
            str(outside),
        ]
    )
    ok = code == 2 and "--out must be" in err and not outside.exists()
    record("fingerprint --out 不能写到项目外", "exit 2, no file", code, out, err, ok)


def case_fingerprint_out_archive_symlink_outside() -> None:
    root = make_root()
    outside = root.parent / (root.name + "-outside-archive")
    outside.mkdir()
    TEMP_PATHS.append(outside)
    archive = root / ".handover" / "archive"
    archive.symlink_to(outside, target_is_directory=True)
    pfile = paths_file(root, ["src/login.ts"])
    target = archive / "login-20261103t000000z.fingerprint.json"
    code, out, err = run(
        [
            "fingerprint",
            "--root",
            str(root),
            "--task",
            "login",
            "--paths",
            str(pfile),
            "--out",
            str(target),
        ]
    )
    ok = (
        code == 2
        and "--out must be" in err
        and not (outside / target.name).exists()
    )
    record(
        "fingerprint --out 不能通过 archive 符号链接写到项目外",
        "exit 2, no file",
        code,
        out,
        err,
        ok,
    )


def case_fingerprint_reserved_task() -> None:
    root = make_root()
    pfile = paths_file(root, ["src/login.ts"])
    code, out, err = run(
        ["fingerprint", "--root", str(root), "--task", "analysis", "--paths", str(pfile)]
    )
    ok = code == 2 and "reserved task-id" in err
    record("fingerprint 拒绝保留字 task-id", "exit 2, reserved", code, out, err, ok)


def case_analysis_json_no_content_leak() -> None:
    root = make_root()
    marker = "SECRET_SYSTEM_PROMPT_MARKER"
    tool_marker = "SECRET_TOOL_DESCRIPTION_MARKER"
    shape = {
        "system": [{"type": "text", "text": marker + " " + "x" * 200}],
        "tools": [
            {
                "name": "Bash",
                "description": tool_marker,
                "input_schema": {"type": "object"},
            }
        ],
    }
    transcript = write_transcript(root, [shape], [])
    code, out, err = run(
        ["analysis", "--root", str(root), "--transcript", str(transcript), "--json"]
    )
    code2, out2, err2 = run(
        ["analysis", "--root", str(root), "--transcript", str(transcript)]
    )
    ok = (
        code == 0
        and code2 == 0
        and marker not in out
        and marker not in out2
        and tool_marker not in out
        and tool_marker not in out2
        and '"head"' not in out
    )
    record(
        "analysis 不输出 system/tool 正文片段",
        "no markers, no head field",
        code,
        out + "\n---\n" + out2,
        err + "\n---\n" + err2,
        ok,
    )


def case_analysis_explicit_session_strict() -> None:
    root = make_root()
    home = Path(tempfile.mkdtemp(prefix="handover-home-"))
    TEMP_PATHS.append(home)
    encoded = re.sub(r"[^A-Za-z0-9]", "-", str(root.resolve()))
    project_dir = home / ".claude" / "projects" / encoded
    project_dir.mkdir(parents=True)
    (project_dir / "other.jsonl").write_text("{}\n", encoding="utf-8")
    env_extra = {"HOME": str(home), "CLAUDE_CODE_SESSION_ID": ""}
    code_missing, out_missing, err_missing = run(
        ["analysis", "--root", str(root), "--session", "missing-session"],
        env_extra=env_extra,
    )
    ok_missing = code_missing == 2 and "session transcript not found" in err_missing
    code_auto, out_auto, err_auto = run(
        ["analysis", "--root", str(root)], env_extra=env_extra
    )
    ok_auto = (
        code_auto == 0
        and "auto-selected latest transcript: other.jsonl" in out_auto
    )
    code_bad, out_bad, err_bad = run(
        ["analysis", "--root", str(root), "--session", "../escape"],
        env_extra=env_extra,
    )
    ok_bad = code_bad == 2 and "invalid session id" in err_bad
    record(
        "analysis：显式 session 缺失不回退；未指定时才自动选择",
        "missing exit 2; auto note; invalid exit 2",
        code_missing,
        "\n---\n".join([out_missing, out_auto, out_bad]),
        "\n---\n".join([err_missing, err_auto, err_bad]),
        ok_missing and ok_auto and ok_bad,
    )


def case_analysis_transcript_symlink_outside() -> None:
    root = make_root()
    home = Path(tempfile.mkdtemp(prefix="handover-home-"))
    TEMP_PATHS.append(home)
    encoded = re.sub(r"[^A-Za-z0-9]", "-", str(root.resolve()))
    project_dir = home / ".claude" / "projects" / encoded
    project_dir.mkdir(parents=True)
    outside = home / "outside.jsonl"
    marker = "OUTSIDE_TRANSCRIPT_MARKER"
    outside.write_text(
        json.dumps(
            {
                "type": "api-request-shape",
                "timestamp": "2026-11-03T00:00:01Z",
                "shape": {"system": [{"type": "text", "text": marker}]},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (project_dir / "leak.jsonl").symlink_to(outside)
    env_extra = {"HOME": str(home), "CLAUDE_CODE_SESSION_ID": ""}
    code, out, err = run(["analysis", "--root", str(root)], env_extra=env_extra)
    ok = code == 0 and marker not in out and "transcript: (not found)" in out
    record(
        "analysis 不读取项目 transcript 目录外的符号链接",
        "not found, no content",
        code,
        out,
        err,
        ok,
    )


def case_ignore_check_git_error() -> None:
    root = make_root(with_git=False)
    fake_bin = root.parent / (root.name + "-fakebin")
    fake_bin.mkdir()
    TEMP_PATHS.append(fake_bin)
    fake_git = fake_bin / "git"
    fake_git.write_text(
        "#!/bin/sh\necho 'fatal: unable to access repository' >&2\nexit 128\n",
        encoding="utf-8",
    )
    fake_git.chmod(0o755)
    env_extra = {"PATH": str(fake_bin) + os.pathsep + os.environ.get("PATH", "")}
    code, out, err = run(["ignore-check", "--root", str(root)], env_extra=env_extra)
    ok = code == 2 and "result: unknown" in out
    record(
        "ignore-check：git 执行失败不被当作非 Git",
        "unknown, exit 2",
        code,
        out,
        err,
        ok,
    )


def case_status_guard_schema_invalid() -> None:
    root = make_root()
    set_task_text(root, "schema: 1", "schema: 999")
    code, out, err = status_guard(root)
    ok_bad = code == 2 and "schema" in out
    set_task_text(root, "schema: 999", "schema: true")
    code2, out2, err2 = status_guard(root)
    ok_bool = code2 == 2 and "schema" in out2
    record(
        "status-guard 拒绝不支持/布尔 schema",
        "unknown, exit 2",
        code,
        out + "\n---\n" + out2,
        err + "\n---\n" + err2,
        ok_bad and ok_bool,
    )


def case_status_guard_project_root_mismatch() -> None:
    root = make_root()
    set_task_text(root, "project_root: %s" % root, "project_root: %s-other" % root)
    code, out, err = status_guard(root)
    ok = code == 2 and "project_root mismatch" in out
    record("status-guard 拒绝其他项目的记录", "unknown, exit 2", code, out, err, ok)


def case_status_guard_legacy_migration_branch() -> None:
    root = make_root()
    task = root / ".handover" / "login.md"
    task.write_text("# Legacy login\n\n## 当前进度\n- old\n", encoding="utf-8")
    code_plain, out_plain, err_plain = status_guard(root)
    ok_plain = code_plain == 2 and "missing_frontmatter" in out_plain
    code_legacy, out_legacy, err_legacy = status_guard(root, extra=["--legacy-migration"])
    ok_legacy = code_legacy == 3 and "legacy-migration-required" in out_legacy
    task.write_text("not a markdown heading\n", encoding="utf-8")
    code_corrupt, out_corrupt, err_corrupt = status_guard(
        root, extra=["--legacy-migration"]
    )
    ok_corrupt = code_corrupt == 2 and "not a recognisable legacy task" in out_corrupt
    task.write_text("---\ntask_id: login\n", encoding="utf-8")
    code_unclosed, out_unclosed, err_unclosed = status_guard(
        root, extra=["--legacy-migration"]
    )
    ok_unclosed = code_unclosed == 2 and "unclosed_frontmatter" in out_unclosed
    record(
        "status-guard 旧格式迁移分支：仅可识别旧记录 exit 3",
        "plain exit 2; legacy exit 3; corrupt/unclosed exit 2",
        code_legacy,
        "\n---\n".join([out_plain, out_legacy, out_corrupt, out_unclosed]),
        "\n---\n".join([err_plain, err_legacy, err_corrupt, err_unclosed]),
        ok_plain and ok_legacy and ok_corrupt and ok_unclosed,
    )


def case_parse_inline_comments_and_quotes() -> None:
    root = make_root()
    set_task_text(root, "schema: 1", "schema: 1 # current schema")
    set_task_text(root, "title: Login task", 'title: "Login # task"')
    set_task_text(root, "status: in-progress", "status: in-progress # active")
    code, out, err = run(["list", "--root", str(root)])
    ok = code == 0 and "| login | Login # task | in-progress |" in out
    code2, out2, err2 = status_guard(root)
    ok = ok and code2 == 0 and "active-reuse-allowed" in out2
    record(
        "受限 YAML：行内注释与引号内 # 正确处理",
        "list/status-guard succeed",
        code,
        out + "\n---\n" + out2,
        err + "\n---\n" + err2,
        ok,
    )


def case_parse_apostrophe_in_plain_scalar() -> None:
    root = make_root()
    set_task_text(root, "title: Login task", "title: It's fine")
    code, out, err = run(["list", "--root", str(root)])
    ok = code == 0 and "| login | It's fine | in-progress |" in out
    code2, out2, err2 = status_guard(root)
    ok = ok and code2 == 0 and "active-reuse-allowed" in out2
    record(
        "受限 YAML：普通标量中的撇号不被当作引号",
        "list/status-guard succeed",
        code,
        out + "\n---\n" + out2,
        err + "\n---\n" + err2,
        ok,
    )


def case_parse_single_quoted_apostrophe() -> None:
    root = make_root()
    set_task_text(root, "title: Login task", "title: 'It''s fine'")
    code, out, err = run(["list", "--root", str(root)])
    ok = code == 0 and "| login | It's fine | in-progress |" in out
    code2, out2, err2 = status_guard(root)
    ok = ok and code2 == 0 and "active-reuse-allowed" in out2
    record(
        "受限 YAML：单引号标量中的 '' 转义",
        "list/status-guard succeed",
        code,
        out + "\n---\n" + out2,
        err + "\n---\n" + err2,
        ok,
    )


def case_parse_duplicate_key_rejected() -> None:
    root = make_root()
    task = root / ".handover" / "login.md"
    text = task.read_text(encoding="utf-8")
    text = text.replace(
        "status: in-progress\n", "status: in-progress\nstatus: pending\n", 1
    )
    task.write_text(text, encoding="utf-8")
    code, out, err = run(["list", "--root", str(root)])
    ok_list = code == 0 and "duplicate_key" in out
    code2, out2, err2 = status_guard(root)
    ok_guard = code2 == 2 and "duplicate_key" in out2
    record(
        "受限 YAML：重复键被拒绝而非后者覆盖",
        "exception + exit 2",
        code,
        out + "\n---\n" + out2,
        err + "\n---\n" + err2,
        ok_list and ok_guard,
    )


def case_parse_unsupported_syntax_rejected() -> None:
    root = make_root()
    set_task_text(root, "title: Login task", "title: [Login, task]")
    code, out, err = status_guard(root)
    ok_bracket = code == 2 and "unsupported_syntax" in out
    set_task_text(root, "title: [Login, task]", "title: Fix: login")
    code2, out2, err2 = status_guard(root)
    ok_nested = code2 == 2 and "unsupported_syntax" in out2
    set_task_text(root, "title: Fix: login", "  title: indented")
    code3, out3, err3 = status_guard(root)
    ok_indent = code3 == 2 and "indented_line" in out3
    set_task_text(root, "  title: indented", "title: 'It's fine'")
    code4, out4, err4 = status_guard(root)
    ok_trailing = code4 == 2 and "invalid_quoted_value" in out4
    record(
        "受限 YAML：序列/嵌套映射/缩进/引号尾随内容被拒绝",
        "exit 2 with parse error",
        code,
        out + "\n---\n" + out2 + "\n---\n" + out3 + "\n---\n" + out4,
        err + "\n---\n" + err2 + "\n---\n" + err3 + "\n---\n" + err4,
        ok_bracket and ok_nested and ok_indent and ok_trailing,
    )


def case_config_symlink_outside() -> None:
    root = make_root()
    outside = root.parent / (root.name + "-config.yaml")
    outside.write_text("stale_after_days: 1\n", encoding="utf-8")
    TEMP_PATHS.append(outside)
    config = root / ".handover" / "config.yaml"
    config.unlink()
    config.symlink_to(outside)
    recent = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(timespec="seconds")
    set_task_text(root, "updated_at: 2026-11-01T10:00:00+08:00", "updated_at: %s" % recent)
    code, out, err = run(["list", "--root", str(root)])
    ok = (
        code == 0
        and "outside project root" in err
        and "| login | Login task | in-progress | fresh |" in out
    )
    record(
        "config 符号链接指向项目外时不读取",
        "warning + default freshness",
        code,
        out,
        err,
        ok,
    )


def case_fingerprint_scope_report() -> None:
    root = make_root()
    _, _, out = fingerprint(root, ["src/login.ts"])
    ok = (
        "content_hashed_files: 1" in out
        and "git_status_dirs: src/" in out
        and "coverage_note:" in out
    )
    record("fingerprint 报告内容哈希与 git 状态范围", "coverage lines", 0, out, "", ok)


def case_check_matched_scope_report() -> None:
    root = make_root()
    snap, sha, _ = fingerprint(root, ["src/login.ts"])
    bind_task(root, snap, sha)
    code, out, err = check(root, sha)
    ok = (
        code == 0
        and "content_hashed_files: 1" in out
        and "git_status_dirs: src/" in out
        and "coverage_note:" in out
    )
    record("check matched 报告覆盖范围", "coverage lines", code, out, err, ok)


def case_directory_sibling_status_unchanged() -> None:
    root = make_root()
    other = root / "src" / "other.ts"
    other.write_text("export const other = 2;\n", encoding="utf-8")
    snap, sha, _ = fingerprint(root, ["src/login.ts"])
    bind_task(root, snap, sha)
    other.write_text("export const other = 3;\n", encoding="utf-8")
    code, out, err = check(root, sha)
    ok = code == 0 and "consistency: matched" in out
    record(
        "目录内未声明文件：同状态内容变化不被内容哈希发现（记录边界）",
        "matched (documented limitation)",
        code,
        out,
        err,
        ok,
    )


def case_task_body_edit_not_detected() -> None:
    root = make_root()
    snap, sha, _ = fingerprint(root, ["src/login.ts"])
    bind_task(root, snap, sha)
    set_task_text(root, "- 目标：fixture", "- 目标：changed after save")
    code, out, err = check(root, sha)
    ok = code == 0 and "consistency: matched" in out
    record(
        "只改任务正文不更新 frontmatter：check 仍 matched（记录边界）",
        "matched (documented limitation)",
        code,
        out,
        err,
        ok,
    )


def case_check_sidecar_schema_bool() -> None:
    root = make_root()
    snap, sha, _ = fingerprint(root, ["src/login.ts"])
    bind_task(root, snap, sha)
    sidecar = root / ".handover" / "login.fingerprint.json"
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data["schema"] = True
    sidecar.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    new_sha = hashlib.sha256(sidecar.read_bytes()).hexdigest()
    set_task_text(root, "fingerprint_sha256: %s" % sha, "fingerprint_sha256: %s" % new_sha)
    code, out, err = check(root, new_sha)
    ok = code == 2 and "schema" in out
    record("check 拒绝布尔 sidecar schema", "unknown, exit 2", code, out, err, ok)


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
        case_ignore_check_missing_dir,
        case_ignore_check_not_git,
        case_status_guard_absent,
        case_status_guard_active,
        case_status_guard_completed,
        case_status_guard_cancelled,
        case_status_guard_reopen,
        case_status_guard_unknown,
        case_status_guard_outside,
        case_stats_text,
        case_stats_json,
        case_stats_missing,
        case_stats_outside,
        case_stats_invalid_task,
        case_stats_no_frontmatter,
        case_config_plain_yaml,
        case_config_invalid_warning,
        case_check_missing_fingerprint_file,
        case_check_missing_fingerprint_sha,
        case_check_task_id_mismatch,
        case_check_unsupported_schema,
        case_check_schema_bool,
        case_check_project_root_mismatch,
        case_fingerprint_empty_scope,
        case_root_scope_new_file,
        case_check_empty_sidecar,
        case_check_legacy_root_scope,
        case_list_handover_symlink_outside,
        case_list_task_symlink_outside,
        case_fingerprint_output_symlink,
        case_check_out_of_scope_note,
        case_check_size_change_over_limit,
        case_list_duplicate_task_id,
        case_list_duplicate_all_exceptions,
        case_list_schema_bool_exception,
        case_fingerprint_out_business_file_refused,
        case_fingerprint_out_task_markdown_refused,
        case_fingerprint_out_valid_archive_sidecar,
        case_fingerprint_out_existing_invalid_refused,
        case_fingerprint_out_outside_root_refused,
        case_fingerprint_out_archive_symlink_outside,
        case_fingerprint_reserved_task,
        case_analysis_transcript_symlink_outside,
        case_ignore_check_git_error,
        case_status_guard_schema_invalid,
        case_status_guard_project_root_mismatch,
        case_status_guard_legacy_migration_branch,
        case_parse_inline_comments_and_quotes,
        case_parse_apostrophe_in_plain_scalar,
        case_parse_single_quoted_apostrophe,
        case_parse_duplicate_key_rejected,
        case_parse_unsupported_syntax_rejected,
        case_config_symlink_outside,
        case_fingerprint_scope_report,
        case_check_matched_scope_report,
        case_directory_sibling_status_unchanged,
        case_task_body_edit_not_detected,
        case_check_sidecar_schema_bool,
        case_analysis_json_no_content_leak,
        case_analysis_explicit_session_strict,
        case_analysis_text,
        case_analysis_json,
        case_analysis_missing_transcript,
        case_analysis_no_transcript,
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
    print("# v1.1.2 Fixture Test Results")
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
