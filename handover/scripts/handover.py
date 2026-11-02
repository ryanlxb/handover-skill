#!/usr/bin/env python3
"""Minimal stdlib-only helpers for the Handover skill.

Commands
--------
list --root ROOT [--all]
    Read task frontmatter only. Default: active states + exceptions.
    --all also shows completed/cancelled and archive area.

fingerprint --root ROOT --task TASK --paths PATHS [--out OUT]
            [--snapshot-id ID] [--scope-dir DIR ...] [--max-bytes N]
    Hash the listed files and the relevant git state, then write
    .handover/<task>.fingerprint.json. Prints the snapshot id and sidecar
    SHA-256 for the task frontmatter.

check --root ROOT --task TASK [--task-file FILE] [--sidecar SIDECAR]
      [--expected-sha256 HASH] [--expected-snapshot-id ID]
    Re-hash the sidecar's files and git state. Verifies the task frontmatter
    and sidecar belong to the same snapshot. Reports matched / changed /
    unknown, with the precedence:
      definite change -> changed (even if incomplete)
      no definite change + incomplete -> unknown
      complete + no change -> matched

This script never modifies task files or business files. It only writes the
fingerprint sidecar requested by `fingerprint`. Requires Python 3.9+.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCHEMA = 1
DEFAULT_STALE_DAYS = 14
DEFAULT_MAX_BYTES = 8 * 1024 * 1024
TASK_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
SNAPSHOT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

ACTIVE = {"in-progress", "pending", "blocked", "paused"}
ENDED = {"completed", "cancelled"}
KNOWN_STATUS = ACTIVE | ENDED | {"unknown"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return now_utc().isoformat(timespec="seconds")


def parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    return dt


def freshness(updated_at: Optional[str], stale_days: int) -> str:
    dt = parse_iso(updated_at)
    if dt is None:
        return "unknown"
    age = (now_utc() - dt).total_seconds() / 86400.0
    if age < 0:
        return "unknown"
    return "stale" if age >= stale_days else "fresh"


def parse_simple_yaml(text: str) -> Optional[Dict[str, Any]]:
    """Parse a flat YAML frontmatter block. Returns None if absent/unclosed."""
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
    data: Dict[str, Any] = {}
    for raw in lines[1:end]:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "" or value.lower() == "null":
            data[key] = None
        elif value.lower() in ("true", "false"):
            data[key] = value.lower() == "true"
        elif value.lstrip("-").isdigit():
            data[key] = int(value)
        else:
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            data[key] = value
    return data


def read_frontmatter(path: Path) -> Tuple[Optional[Dict[str, Any]], str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, "read_error: %s" % exc
    data = parse_simple_yaml(text)
    if data is None:
        return None, "missing_or_unclosed_frontmatter"
    return data, "ok"


def read_stale_days(root: Path) -> Tuple[int, Optional[str]]:
    config = root / ".handover" / "config.yaml"
    if not config.is_file():
        return DEFAULT_STALE_DAYS, None
    try:
        text = config.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return DEFAULT_STALE_DAYS, "config_unreadable: %s" % exc
    data = parse_simple_yaml(text)
    if not data or "stale_after_days" not in data:
        return DEFAULT_STALE_DAYS, None
    value = data.get("stale_after_days")
    if isinstance(value, int) and value > 0:
        return value, None
    return DEFAULT_STALE_DAYS, "invalid stale_after_days; using default %d" % DEFAULT_STALE_DAYS


def within_root(root: Path, path: Path) -> bool:
    try:
        root_resolved = root.resolve()
        path_resolved = path.resolve()
        return os.path.commonpath([str(root_resolved), str(path_resolved)]) == str(root_resolved)
    except (OSError, ValueError):
        return False


def normalize_rel(rel: str) -> str:
    return os.path.normpath(rel).replace("\\", "/")


def is_excluded(rel: str) -> bool:
    rel = normalize_rel(rel)
    return (
        rel == "handover.md"
        or rel.startswith(".handover/")
        or rel.startswith(".claude/")
        or rel.startswith(".git/")
    )


def hash_file(path: Path, max_bytes: int) -> Tuple[Optional[str], Optional[int], str]:
    try:
        size = path.stat().st_size
    except OSError as exc:
        return None, None, "stat_error: %s" % exc
    if size > max_bytes:
        return None, size, "too_large"
    h = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
    except OSError as exc:
        return None, size, "read_error: %s" % exc
    return h.hexdigest(), size, "ok"


def record_for(root: Path, rel: str, max_bytes: int) -> Dict[str, Any]:
    path = root / rel
    if not within_root(root, path):
        return {"status": "outside_root", "sha256": None, "size": None}
    if path.is_symlink():
        try:
            target = os.readlink(path)
        except OSError as exc:
            return {"status": "symlink_error: %s" % exc, "sha256": None, "size": None}
        resolved = (path.parent / target).resolve() if not os.path.isabs(target) else Path(target)
        if not within_root(root, resolved):
            return {"status": "symlink_outside_root", "sha256": None, "size": None, "target": target}
        value, size, status = hash_file(resolved, max_bytes)
        return {"status": status, "sha256": value, "size": size, "symlink": target}
    if not path.exists():
        return {"status": "missing", "sha256": None, "size": None}
    if not path.is_file():
        return {"status": "not_file", "sha256": None, "size": None}
    value, size, status = hash_file(path, max_bytes)
    return {"status": status, "sha256": value, "size": size}


def run_git(root: Path, args: List[str]) -> Tuple[Optional[str], Optional[str]]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root)] + args,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    if proc.returncode != 0:
        return None, proc.stderr.strip() or ("exit %d" % proc.returncode)
    return proc.stdout, None


def parse_status_z(raw: str) -> List[Tuple[str, str, Optional[str]]]:
    """Parse `git status --porcelain=v1 -z` into (XY, path, old_path)."""
    parts = raw.split("\0")
    entries: List[Tuple[str, str, Optional[str]]] = []
    i = 0
    while i < len(parts):
        item = parts[i]
        if not item:
            i += 1
            continue
        if len(item) < 4:
            entries.append((item[:2], item[3:] if len(item) > 3 else "", None))
            i += 1
            continue
        xy = item[:2]
        path = item[3:]
        old: Optional[str] = None
        if xy[0] in ("R", "C") or (len(xy) > 1 and xy[1] in ("R", "C")):
            if i + 1 < len(parts):
                old = parts[i + 1]
                i += 2
            else:
                i += 1
        else:
            i += 1
        entries.append((xy, path, old))
    return entries


def path_relevant(path: str, scope_paths: List[str], scope_dirs: List[str]) -> bool:
    p = normalize_rel(path)
    if p in scope_paths:
        return True
    for directory in scope_dirs:
        d = directory.rstrip("/")
        if d and (p == d or p.startswith(d + "/")):
            return True
    return False


def entry_relevant(
    entry: Tuple[str, str, Optional[str]],
    scope_paths: List[str],
    scope_dirs: List[str],
) -> bool:
    _, path, old = entry
    return path_relevant(path, scope_paths, scope_dirs) or (
        bool(old) and path_relevant(str(old), scope_paths, scope_dirs)
    )


def derive_scope_dirs(rels: List[str]) -> List[str]:
    dirs = set()
    for rel in rels:
        parent = str(Path(rel).parent).replace("\\", "/")
        if parent and parent != ".":
            dirs.add(parent.rstrip("/") + "/")
    return sorted(dirs)


def normalize_scope_dir(value: str) -> Optional[str]:
    value = value.strip().replace("\\", "/")
    if not value or os.path.isabs(value):
        return None
    norm = os.path.normpath(value).replace("\\", "/")
    if norm == "." or norm.startswith("../") or norm == "..":
        return None
    return norm.rstrip("/") + "/"


def git_snapshot(root: Path, scope_paths: List[str], scope_dirs: List[str]) -> Dict[str, Any]:
    inside, error = run_git(root, ["rev-parse", "--is-inside-work-tree"])
    if error or (inside or "").strip() != "true":
        return {
            "available": False,
            "reason": error or "not a git work tree",
            "branch": None,
            "head": None,
            "status_sha256": None,
            "status_entries": [],
            "ignored_entries": 0,
            "scope_paths": sorted(scope_paths),
            "scope_dirs": sorted(scope_dirs),
        }

    branch_out, branch_err = run_git(root, ["rev-parse", "--abbrev-ref", "HEAD"])
    head_out, head_err = run_git(root, ["rev-parse", "HEAD"])
    if branch_err or head_err:
        return {
            "available": False,
            "reason": branch_err or head_err,
            "branch": None,
            "head": None,
            "status_sha256": None,
            "status_entries": [],
            "ignored_entries": 0,
            "scope_paths": sorted(scope_paths),
            "scope_dirs": sorted(scope_dirs),
        }

    status_out, status_err = run_git(root, ["status", "--porcelain=v1", "-z", "--untracked-files=all"])
    if status_err:
        return {
            "available": False,
            "reason": status_err,
            "branch": (branch_out or "").strip(),
            "head": (head_out or "").strip(),
            "status_sha256": None,
            "status_entries": [],
            "ignored_entries": 0,
            "scope_paths": sorted(scope_paths),
            "scope_dirs": sorted(scope_dirs),
        }

    relevant: List[str] = []
    ignored = 0
    for entry in parse_status_z(status_out or ""):
        _, path, old = entry
        if is_excluded(path) or (old and is_excluded(str(old))):
            continue
        if entry_relevant(entry, scope_paths, scope_dirs):
            relevant.append("%s\t%s\t%s" % (entry[0], path, old or ""))
        else:
            ignored += 1
    relevant.sort()
    status_sha = hashlib.sha256("\n".join(relevant).encode("utf-8")).hexdigest()
    return {
        "available": True,
        "reason": None,
        "branch": (branch_out or "").strip(),
        "head": (head_out or "").strip(),
        "status_sha256": status_sha,
        "status_entries": relevant,
        "ignored_entries": ignored,
        "scope_paths": sorted(scope_paths),
        "scope_dirs": sorted(scope_dirs),
    }


def cmd_fingerprint(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    task = args.task
    if not TASK_RE.match(task):
        print("error: invalid task-id: %s" % task, file=sys.stderr)
        return 2
    snapshot_id = args.snapshot_id or uuid.uuid4().hex
    if not SNAPSHOT_RE.match(snapshot_id):
        print("error: invalid snapshot-id", file=sys.stderr)
        return 2

    paths_file = Path(args.paths)
    if not paths_file.is_file():
        print("error: paths file not found: %s" % paths_file, file=sys.stderr)
        return 2

    rels: List[str] = []
    skipped: List[str] = []
    for raw in paths_file.read_text(encoding="utf-8").splitlines():
        rel = raw.strip()
        if not rel or rel.startswith("#"):
            continue
        if os.path.isabs(rel):
            print("error: absolute path not allowed: %s" % rel, file=sys.stderr)
            return 2
        norm = normalize_rel(rel)
        if is_excluded(norm):
            skipped.append(norm)
            continue
        if norm not in rels:
            rels.append(norm)

    files: Dict[str, Any] = {}
    issues = 0
    for rel in rels:
        record = record_for(root, rel, args.max_bytes)
        files[rel] = record
        if record.get("status") != "ok":
            issues += 1

    scope_dirs = set(derive_scope_dirs(rels))
    for value in args.scope_dir or []:
        normalized = normalize_scope_dir(value)
        if normalized is None:
            print("error: invalid scope-dir: %s" % value, file=sys.stderr)
            return 2
        scope_dirs.add(normalized)
    scope_dirs_list = sorted(scope_dirs)
    git_info = git_snapshot(root, rels, scope_dirs_list)

    payload = {
        "schema": SCHEMA,
        "snapshot_id": snapshot_id,
        "task_id": task,
        "created_at": iso_now(),
        "root": str(root),
        "scope": "relevant-files+git",
        "max_file_bytes": args.max_bytes,
        "files": files,
        "git": git_info,
        "overall": "complete" if issues == 0 else "partial",
        "skipped_excluded": skipped,
    }
    out = Path(args.out) if args.out else (root / ".handover" / (task + ".fingerprint.json"))
    out = out.resolve()
    if not within_root(root, out):
        print("error: output must be inside the project root", file=sys.stderr)
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=out.name + ".", suffix=".tmp", dir=str(out.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(tmp, out)
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        print("error: write failed: %s" % exc, file=sys.stderr)
        return 2

    sidecar_sha = hashlib.sha256(out.read_bytes()).hexdigest()
    print("sidecar: %s" % out)
    print("sidecar_sha256: %s" % sidecar_sha)
    print("snapshot_id: %s" % snapshot_id)
    print("overall: %s" % payload["overall"])
    print("git_available: %s" % ("true" if git_info.get("available") else "false"))
    print("files: %d ok, %d issue(s)" % (len(rels) - issues, issues))
    if skipped:
        print("skipped_excluded: %s" % ", ".join(skipped))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    if not TASK_RE.match(args.task):
        print("consistency: unknown")
        print("reason: invalid task-id")
        return 2

    sidecar = Path(args.sidecar) if args.sidecar else (root / ".handover" / (args.task + ".fingerprint.json"))
    sidecar = sidecar.resolve()
    if not within_root(root, sidecar):
        print("consistency: unknown")
        print("reason: sidecar outside project root")
        return 2
    if not sidecar.is_file():
        print("consistency: unknown")
        print("reason: sidecar missing")
        return 2
    try:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print("consistency: unknown")
        print("reason: sidecar unreadable: %s" % exc)
        return 2

    if payload.get("schema") != SCHEMA:
        print("consistency: unknown")
        print("reason: unsupported sidecar schema=%s" % payload.get("schema"))
        return 2
    if payload.get("task_id") != args.task:
        print("consistency: unknown")
        print("reason: sidecar task_id mismatch")
        return 2
    recorded_root = payload.get("root")
    if recorded_root and Path(recorded_root).resolve() != root:
        print("consistency: unknown")
        print("reason: sidecar root mismatch")
        return 2

    sidecar_sha = hashlib.sha256(sidecar.read_bytes()).hexdigest()
    if args.expected_sha256 and sidecar_sha != args.expected_sha256:
        print("consistency: unknown")
        print("reason: sidecar sha256 mismatch")
        return 2

    snapshot_id = payload.get("snapshot_id")
    if not snapshot_id:
        print("consistency: unknown")
        print("reason: sidecar has no snapshot_id")
        return 2
    if args.expected_snapshot_id and snapshot_id != args.expected_snapshot_id:
        print("consistency: unknown")
        print("reason: sidecar snapshot_id mismatch")
        return 2

    task_file = Path(args.task_file) if args.task_file else (root / ".handover" / (args.task + ".md"))
    task_file = task_file.resolve()
    if not within_root(root, task_file):
        print("consistency: unknown")
        print("reason: task file outside project root")
        return 2
    if not task_file.is_file():
        print("consistency: unknown")
        print("reason: task file missing; cannot bind snapshot")
        return 2
    task_data, task_status = read_frontmatter(task_file)
    if task_data is None:
        print("consistency: unknown")
        print("reason: task frontmatter unreadable: %s" % task_status)
        return 2
    if task_data.get("snapshot_id") != snapshot_id:
        print("consistency: unknown")
        print("reason: task/sidecar snapshot_id mismatch")
        return 2
    recorded_fingerprint_file = task_data.get("fingerprint_file")
    if recorded_fingerprint_file:
        recorded_path = (root / str(recorded_fingerprint_file)).resolve()
        if recorded_path != sidecar:
            print("consistency: unknown")
            print("reason: task fingerprint_file does not point to this sidecar")
            return 2
    recorded_fingerprint_sha = task_data.get("fingerprint_sha256")
    if recorded_fingerprint_sha and recorded_fingerprint_sha != sidecar_sha:
        print("consistency: unknown")
        print("reason: task fingerprint_sha256 mismatch")
        return 2

    content_changed: List[str] = []
    incomplete: List[str] = []
    for rel, old in sorted(payload.get("files", {}).items()):
        if old.get("status") != "ok":
            incomplete.append("%s: baseline status %s" % (rel, old.get("status")))
            continue
        record = record_for(root, rel, int(payload.get("max_file_bytes", DEFAULT_MAX_BYTES)))
        if record.get("status") == "missing":
            content_changed.append("%s: missing" % rel)
        elif record.get("status") != "ok":
            incomplete.append("%s: current status %s" % (rel, record.get("status")))
        elif record.get("sha256") != old.get("sha256"):
            content_changed.append(rel)

    git_changed: List[str] = []
    old_git = payload.get("git") or {}
    if old_git.get("available"):
        scope_paths = list(old_git.get("scope_paths") or [])
        scope_dirs = list(old_git.get("scope_dirs") or [])
        current_git = git_snapshot(root, scope_paths, scope_dirs)
        if not current_git.get("available"):
            incomplete.append("git unavailable now: %s" % current_git.get("reason"))
        else:
            if current_git.get("branch") != old_git.get("branch"):
                git_changed.append("branch: %s -> %s" % (old_git.get("branch"), current_git.get("branch")))
            if current_git.get("head") != old_git.get("head"):
                git_changed.append("HEAD changed")
            if current_git.get("status_sha256") != old_git.get("status_sha256"):
                git_changed.append("status changed")
    else:
        incomplete.append("no git baseline: %s" % old_git.get("reason"))

    if content_changed or git_changed:
        print("consistency: changed")
        if content_changed:
            print("content_changed: %s" % ", ".join(content_changed))
        if git_changed:
            print("git_changed: %s" % ", ".join(git_changed))
        print("incomplete: %s" % ("true" if incomplete else "false"))
        if incomplete:
            print("incomplete_reason: %s" % "; ".join(incomplete))
        return 1
    if incomplete:
        print("consistency: unknown")
        print("reason: %s" % "; ".join(incomplete))
        return 2
    print("consistency: matched")
    print("scope: %d file(s), %d git entries" % (
        len(payload.get("files", {})),
        len(old_git.get("status_entries") or []),
    ))
    return 0


def iter_task_files(root: Path, include_archive: bool) -> List[Path]:
    base = root / ".handover"
    files: List[Path] = []
    if base.is_dir():
        files.extend(sorted(p for p in base.glob("*.md") if p.is_file()))
    if include_archive:
        archive = base / "archive"
        if archive.is_dir():
            files.extend(sorted(p for p in archive.glob("*.md") if p.is_file()))
    return files


def cmd_list(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    include_archive = bool(args.all)
    stale_days, config_warning = read_stale_days(root)
    if config_warning:
        print("warning: %s" % config_warning, file=sys.stderr)

    active_rows: List[Tuple[str, str, str, str, str]] = []
    exception_rows: List[Tuple[str, str, str, str, str]] = []
    ended_rows: List[Tuple[str, str, str, str]] = []
    archived_rows: List[Tuple[str, str, str, str]] = []
    ended_count = 0
    archived_count = 0
    seen: Dict[str, str] = {}

    for path in iter_task_files(root, include_archive=False):
        rel = str(path.relative_to(root))
        data, status = read_frontmatter(path)
        if data is None:
            exception_rows.append((path.stem, "unknown", "-", "frontmatter: %s" % status, rel))
            continue
        task_id = str(data.get("task_id") or "")
        task_status = str(data.get("status") or "unknown")
        updated_at = data.get("updated_at")
        fresh = freshness(updated_at if isinstance(updated_at, str) else None, stale_days)
        reasons: List[str] = []
        if not task_id:
            reasons.append("missing task_id")
        elif path.stem != task_id:
            reasons.append("filename/task_id mismatch")
        elif task_id in seen:
            reasons.append("duplicate task_id")
        else:
            seen[task_id] = rel
        schema = data.get("schema")
        if schema is None:
            reasons.append("missing schema")
        elif not isinstance(schema, int) or schema != SCHEMA:
            reasons.append("unsupported schema=%s" % schema)
        if task_status not in KNOWN_STATUS:
            reasons.append("unknown status")
        if reasons:
            exception_rows.append((task_id or path.stem, task_status, fresh, "; ".join(reasons), rel))
        elif task_status in ACTIVE:
            active_rows.append((task_id, task_status, fresh, str(updated_at or "-"), rel))
        elif task_status in ENDED:
            ended_count += 1
            if include_archive:
                ended_rows.append((task_id, task_status, str(updated_at or "-"), rel))
        else:
            exception_rows.append((task_id or path.stem, task_status, fresh, "status unknown", rel))

    archive = root / ".handover" / "archive"
    if archive.is_dir():
        for path in sorted(archive.glob("*.md")):
            if not path.is_file():
                continue
            archived_count += 1
            if not include_archive:
                continue
            data, status = read_frontmatter(path)
            rel = str(path.relative_to(root))
            if data is None:
                archived_rows.append((path.stem, "unknown", "-", "%s (frontmatter: %s)" % (rel, status)))
                continue
            task_id = str(data.get("task_id") or path.stem)
            task_status = str(data.get("status") or "unknown")
            updated_at = data.get("updated_at") or "-"
            archived_rows.append((task_id, task_status, str(updated_at), rel))

    print("## ACTIVE")
    if active_rows:
        print("| task | status | freshness | updated_at | path |")
        print("|---|---|---|---|---|")
        for row in sorted(active_rows):
            print("| %s | %s | %s | %s | %s |" % row)
    else:
        print("(none)")

    print("")
    print("## EXCEPTIONS")
    if exception_rows:
        print("| task | status | freshness | reason | path |")
        print("|---|---|---|---|---|")
        for row in exception_rows:
            print("| %s | %s | %s | %s | %s |" % row)
    else:
        print("(none)")

    if include_archive:
        print("")
        print("## ENDED")
        if ended_rows:
            print("| task | status | updated_at | path |")
            print("|---|---|---|---|")
            for row in ended_rows:
                print("| %s | %s | %s | %s |" % row)
        else:
            print("(none)")
        print("")
        print("## ARCHIVED")
        if archived_rows:
            print("| task | status | updated_at | path |")
            print("|---|---|---|---|")
            for row in archived_rows:
                print("| %s | %s | %s | %s |" % row)
        else:
            print("(none)")
    else:
        print("")
        print("## HIDDEN")
        print("ended: %d, archived: %d (use --all to show)" % (ended_count, archived_count))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Handover skill helpers (stdlib only)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="list task frontmatter")
    p_list.add_argument("--root", required=True)
    p_list.add_argument("--all", action="store_true")
    p_list.set_defaults(func=cmd_list)

    p_fp = sub.add_parser("fingerprint", help="write a fingerprint sidecar")
    p_fp.add_argument("--root", required=True)
    p_fp.add_argument("--task", required=True)
    p_fp.add_argument("--paths", required=True)
    p_fp.add_argument("--out")
    p_fp.add_argument("--snapshot-id")
    p_fp.add_argument("--scope-dir", action="append", default=[])
    p_fp.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    p_fp.set_defaults(func=cmd_fingerprint)

    p_check = sub.add_parser("check", help="check a fingerprint sidecar")
    p_check.add_argument("--root", required=True)
    p_check.add_argument("--task", required=True)
    p_check.add_argument("--task-file")
    p_check.add_argument("--sidecar")
    p_check.add_argument("--expected-sha256")
    p_check.add_argument("--expected-snapshot-id")
    p_check.set_defaults(func=cmd_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
