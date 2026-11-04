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
    SHA-256 for the task frontmatter. `overall` is `complete` only when the
    file hashes and the git baseline are both available; a non-git project or
    a git failure is `partial` (and `check` reports unknown). A custom --out
    must be directly under .handover/ or .handover/archive/, use a
    <task>[-<timestamp>].fingerprint.json name, and may only overwrite an
    existing sidecar for the same task and project; ordinary business files
    and task Markdown are never overwritten.

check --root ROOT --task TASK [--task-file FILE] [--sidecar SIDECAR]
      [--expected-sha256 HASH] [--expected-snapshot-id ID]
    Re-hash the sidecar's files and git state. Verifies the task frontmatter
    and sidecar belong to the same snapshot. Reports matched / changed /
    unknown, with the precedence:
      definite change -> changed (even if incomplete)
      no definite change + incomplete -> unknown
      complete + no change -> matched

status-guard --root ROOT --task TASK [--task-file FILE] [--reopen-authorised]
            [--legacy-migration]
    Check whether a task may be reused as the target of `save`. Exit 0 =
    absent or active (new/reuse allowed); 1 = completed/cancelled (stop and
    ask the user to create a new task or explicitly authorise reopen);
    2 = unknown/error; 3 = a recognisable frontmatter-less legacy record
    when --legacy-migration is explicitly requested (migrate, re-read, then
    rerun status-guard without the flag). `--reopen-authorised` is only for
    an explicit user request to reopen the completed/cancelled task.
    The guard checks task_id, schema, project_root, and status; it is not a
    write lock and does not validate the task body.

ignore-check --root ROOT
    Check whether .handover/ and handover.md are both ignored by Git and not
    tracked. Exit 0 = ok or not a git work tree; 1 = warning; 2 = unknown.

stats --root ROOT --task TASK [--task-file FILE] [--json]
    Estimate the token distribution of a task document: frontmatter and each
    "## " section. Read-only. Uses a rough UTF-8-bytes/3 heuristic, not a
    tokenizer; use it to find expensive sections, not exact counts.

analysis --root ROOT [--session ID] [--transcript FILE]
         [--context-window N] [--json]
    Read-only context audit. Parses the latest api-request-shape (system prompt
    and tool schemas), transcript blobs (message/tool-result sizes), and
    on-disk config sizes. Reports approximate tokens by category and ranked
    recommendations. Does not print message contents or secrets. An explicit
    --session that does not exist is an error; it never falls back to another
    transcript.

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
DEFAULT_CONTEXT_WINDOW = 1000000
CLAUDE_HOME = Path.home() / ".claude"
TASK_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
SNAPSHOT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SESSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SIDECAR_SUFFIX = ".fingerprint.json"
KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
POSITIVE_INT_RE = re.compile(r"^[0-9]+$")

ACTIVE = {"in-progress", "pending", "blocked", "paused"}
ENDED = {"completed", "cancelled"}
KNOWN_STATUS = ACTIVE | ENDED | {"unknown"}
RESERVED_TASK_IDS = {"save", "load", "brief", "list", "archive", "restore", "analysis"}


class FrontmatterError(ValueError):
    """Raised when flat frontmatter uses unsupported or malformed syntax."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(detail or code)

    def __str__(self) -> str:
        return "%s: %s" % (self.code, self.detail) if self.detail else self.code


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


def _strip_inline_comment(value: str) -> str:
    """Strip a YAML inline comment.

    Quoting is only special when it starts the scalar. An apostrophe inside a
    plain scalar (for example `It's fine`) is an ordinary character.
    """
    value = value.rstrip()
    if not value:
        return value
    quote = value[0] if value[0] in ("'", '"') else None
    i = 1 if quote else 0
    while i < len(value):
        ch = value[i]
        if quote == '"':
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                quote = None
        elif quote == "'":
            if ch == "'":
                if i + 1 < len(value) and value[i + 1] == "'":
                    i += 2
                    continue
                quote = None
        elif ch == "#" and (i == 0 or value[i - 1].isspace()):
            return value[:i].rstrip()
        i += 1
    if quote is not None:
        raise FrontmatterError("unclosed_quote", "unterminated quoted value")
    return value


def _parse_scalar(value: str) -> Any:
    """Parse one restricted flat-YAML scalar.

    Supported: null, true/false, quoted strings, and plain strings. Nested
    mappings, sequences, anchors, tags, aliases, and block scalars are
    rejected instead of being silently misread.
    """
    if value == "":
        return None
    if value.startswith("'"):
        chars: List[str] = []
        i = 1
        while i < len(value):
            if value[i] == "'":
                if i + 1 < len(value) and value[i + 1] == "'":
                    chars.append("'")
                    i += 2
                    continue
                if value[i + 1 :].strip():
                    raise FrontmatterError(
                        "invalid_quoted_value",
                        "trailing content after single-quoted value",
                    )
                return "".join(chars)
            chars.append(value[i])
            i += 1
        raise FrontmatterError("unclosed_quote", "unterminated single-quoted value")
    if value.startswith('"'):
        if len(value) < 2 or not value.endswith('"'):
            raise FrontmatterError("unclosed_quote", "unterminated double-quoted value")
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise FrontmatterError("invalid_quoted_value", str(exc))
    if value[0] in "[{|>&*!%@`" or (
        value[0] == "?" and (len(value) == 1 or value[1].isspace())
    ):
        raise FrontmatterError("unsupported_syntax", "unsupported YAML value: %s" % value)
    if value.startswith("- ") or value == "-":
        raise FrontmatterError("unsupported_syntax", "sequences are not supported: %s" % value)
    if ": " in value or value.endswith(":"):
        raise FrontmatterError(
            "unsupported_syntax", "nested mappings are not supported: %s" % value
        )
    lower = value.lower()
    if lower in ("null", "~"):
        return None
    if lower in ("true", "false"):
        return lower == "true"
    # Keep numbers as strings. The task schema and config validate numeric
    # fields explicitly, which avoids YAML type ambiguity for values such as
    # task IDs and commit hashes that happen to be all digits.
    return value


def parse_flat_yaml(lines: List[str]) -> Dict[str, Any]:
    """Parse a restricted flat YAML block.

    The protocol uses one `key: value` pair per line with no nesting. Invalid
    lines, duplicate keys, and unsupported YAML constructs raise
    FrontmatterError instead of being ignored.
    """
    data: Dict[str, Any] = {}
    for raw in lines:
        line = raw.rstrip("\r")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line[:1] in (" ", "\t"):
            raise FrontmatterError(
                "indented_line", "indented frontmatter is not supported: %s" % stripped
            )
        if ":" not in line:
            raise FrontmatterError(
                "unsupported_line", "expected 'key: value': %s" % stripped
            )
        key, value = line.split(":", 1)
        key = key.strip()
        if not KEY_RE.match(key):
            raise FrontmatterError("invalid_key", "unsupported frontmatter key: %s" % key)
        if key in data:
            raise FrontmatterError("duplicate_key", "duplicate frontmatter key: %s" % key)
        if value and not value[0].isspace():
            raise FrontmatterError(
                "unsupported_line", "expected a space after ':' in: %s" % stripped
            )
        data[key] = _parse_scalar(_strip_inline_comment(value.strip()))
    return data


def parse_simple_yaml(text: str) -> Optional[Dict[str, Any]]:
    """Parse a flat YAML frontmatter block.

    Returns None when the block is absent. Raises FrontmatterError when the
    opening delimiter has no closing delimiter or the block is malformed.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        raise FrontmatterError(
            "unclosed_frontmatter", "missing closing frontmatter delimiter"
        )
    return parse_flat_yaml(lines[1:end])


def parse_config_yaml(text: str) -> Optional[Dict[str, Any]]:
    """Parse a flat key/value config, with optional frontmatter delimiters."""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        try:
            parsed = parse_simple_yaml(text)
        except FrontmatterError as exc:
            if exc.code != "unclosed_frontmatter":
                raise
            # A leading YAML document marker does not require a closing marker.
            return parse_flat_yaml(lines[1:])
        if parsed is not None:
            return parsed
    return parse_flat_yaml(lines)


def read_frontmatter(path: Path) -> Tuple[Optional[Dict[str, Any]], str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, "read_error: %s" % exc
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, "missing_frontmatter"
    try:
        data = parse_simple_yaml(text)
    except FrontmatterError as exc:
        if exc.code == "unclosed_frontmatter":
            return None, "unclosed_frontmatter"
        return None, "frontmatter_error: %s" % exc
    if data is None:
        return None, "missing_frontmatter"
    return data, "ok"


def positive_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str):
        text = value.strip()
        if POSITIVE_INT_RE.match(text):
            parsed = int(text)
            return parsed if parsed > 0 else None
    return None


def schema_is_current(value: Any, allow_string: bool = False) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value == SCHEMA
    if allow_string and isinstance(value, str):
        text = value.strip()
        return bool(POSITIVE_INT_RE.match(text)) and int(text) == SCHEMA
    return False


def task_id_error(task: str) -> Optional[str]:
    if not TASK_RE.match(task):
        return "invalid task-id: %s" % task
    if task.lower() in RESERVED_TASK_IDS:
        return "reserved task-id: %s" % task
    return None


def read_stale_days(root: Path) -> Tuple[int, Optional[str]]:
    config = root / ".handover" / "config.yaml"
    if not within_root(root, config):
        return (
            DEFAULT_STALE_DAYS,
            "config resolves outside project root; using default %d" % DEFAULT_STALE_DAYS,
        )
    if not config.is_file():
        return DEFAULT_STALE_DAYS, None
    try:
        text = config.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return DEFAULT_STALE_DAYS, "config_unreadable: %s" % exc
    try:
        data = parse_config_yaml(text)
    except FrontmatterError as exc:
        return (
            DEFAULT_STALE_DAYS,
            "config_error: %s; using default %d" % (exc, DEFAULT_STALE_DAYS),
        )
    if not data or "stale_after_days" not in data:
        return DEFAULT_STALE_DAYS, None
    days = positive_int(data.get("stale_after_days"))
    if days is not None:
        return days, None
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


def git_work_tree_state(root: Path) -> Tuple[str, Optional[str]]:
    """Classify git availability as yes / not-git / error.

    Only the definite `not a git repository` response is reported as
    not-git. A timeout, missing git executable, permission failure, or any
    other git error is an error (unknown), not a successful non-git result.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "error", str(exc)
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if proc.returncode == 0:
        if out == "true":
            return "yes", None
        return "error", "not a git work tree (git reported %r)" % out
    if proc.returncode == 128 and "not a git repository" in err.lower():
        return "not-git", None
    return "error", err or ("exit %d" % proc.returncode)


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
        if directory == ".":
            if "/" not in p:
                return True
            continue
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
        else:
            # Root-level files scope only their direct siblings, not the whole tree.
            dirs.add(".")
    return sorted(dirs)


def normalize_scope_dir(value: str) -> Optional[str]:
    value = value.strip().replace("\\", "/")
    if not value or os.path.isabs(value):
        return None
    norm = os.path.normpath(value).replace("\\", "/")
    if norm == ".":
        return "."
    if norm.startswith("../") or norm == "..":
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


def git_check_ignore(root: Path, rel: str) -> Tuple[Optional[bool], Optional[str]]:
    """Return (ignored, error) for one path, using `git check-ignore`."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "check-ignore", "--no-index", "-q", "--", rel],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    if proc.returncode == 0:
        return True, None
    if proc.returncode == 1:
        return False, None
    return None, proc.stderr.strip() or ("exit %d" % proc.returncode)


def git_is_tracked(root: Path, rel: str) -> Tuple[Optional[bool], Optional[str]]:
    """Return (tracked, error) for one path, using `git ls-files`."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--error-unmatch", "--", rel],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    if proc.returncode == 0:
        return True, None
    if proc.returncode == 1:
        return False, None
    return None, proc.stderr.strip() or ("exit %d" % proc.returncode)


def cmd_ignore_check(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    state, error = git_work_tree_state(root)
    if state == "not-git":
        print("git: false")
        print("result: not-git")
        return 0
    if state == "error":
        print("git: unknown")
        if error:
            print("reason: %s" % error)
        print("result: unknown")
        return 2

    targets = [(".handover/", ".handover/"), ("handover.md", "handover.md")]
    results: List[Tuple[str, str, str]] = []
    unknown = False
    warning = False
    for display, rel in targets:
        ignored, ignore_error = git_check_ignore(root, rel)
        tracked, tracked_error = git_is_tracked(root, rel)
        if ignored is None or tracked is None:
            unknown = True
            results.append((display, "unknown", "unknown"))
            for reason in (ignore_error, tracked_error):
                if reason:
                    print("reason: %s" % reason)
            continue
        ignore_label = "ignored" if ignored else "not-ignored"
        tracked_label = "tracked" if tracked else "not-tracked"
        if not ignored or tracked:
            warning = True
        results.append((display, ignore_label, tracked_label))

    print("git: true")
    for display, ignore_label, tracked_label in results:
        print("%s: %s, %s" % (display, ignore_label, tracked_label))
    if unknown:
        print("result: unknown")
        return 2
    if warning:
        print("result: warning")
        return 1
    print("result: ok")
    return 0


def existing_sidecar_error(path: Path, root: Path, task: str) -> Optional[str]:
    """Return why an existing --out target is not a reusable sidecar, or None."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return "existing output is not a readable JSON sidecar: %s" % exc
    if not isinstance(payload, dict):
        return "existing output is not a JSON object"
    if not schema_is_current(payload.get("schema")):
        return "existing output sidecar schema is missing or unsupported"
    if payload.get("task_id") != task:
        return "existing output belongs to task %r" % payload.get("task_id")
    recorded_root = payload.get("root")
    if not recorded_root or Path(str(recorded_root)).resolve() != root:
        return "existing output belongs to another project root"
    if (
        not isinstance(payload.get("files"), dict)
        or not payload.get("files")
        or not payload.get("snapshot_id")
    ):
        return "existing output is not a complete sidecar"
    return None


def cmd_fingerprint(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    task = args.task
    error = task_id_error(task)
    if error:
        print("error: %s" % error, file=sys.stderr)
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
        if norm == ".." or norm.startswith("../"):
            print("error: path outside project root: %s" % rel, file=sys.stderr)
            return 2
        if is_excluded(norm):
            skipped.append(norm)
            continue
        if norm not in rels:
            rels.append(norm)

    if not rels:
        print(
            "error: no files to fingerprint after exclusions; refusing an empty baseline",
            file=sys.stderr,
        )
        return 2

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
        "overall": "complete" if issues == 0 and git_info.get("available") else "partial",
        "skipped_excluded": skipped,
    }
    handover_dir = root / ".handover"
    if handover_dir.is_symlink():
        print(
            "error: .handover is a symlink; refusing to write: %s" % handover_dir,
            file=sys.stderr,
        )
        return 2
    default_out = handover_dir / (task + SIDECAR_SUFFIX)
    if args.out:
        out_path = Path(args.out)
        if out_path.is_symlink():
            print(
                "error: output path is a symlink; refusing to overwrite: %s" % out_path,
                file=sys.stderr,
            )
            return 2
        out = out_path.resolve()
        handover_resolved = handover_dir.resolve()
        allowed_parents = {handover_resolved}
        archive_resolved = (handover_dir / "archive").resolve()
        if within_root(handover_resolved, archive_resolved):
            allowed_parents.add(archive_resolved)
        if out.parent not in allowed_parents:
            print(
                "error: --out must be directly under %s or %s/archive/"
                % (handover_dir, handover_dir),
                file=sys.stderr,
            )
            return 2
        if not out.name.endswith(SIDECAR_SUFFIX):
            print("error: --out must end with %s" % SIDECAR_SUFFIX, file=sys.stderr)
            return 2
        if out.name != task + SIDECAR_SUFFIX and not (
            out.name.startswith(task + "-") and out.name.endswith(SIDECAR_SUFFIX)
        ):
            print(
                "error: --out must be <task>.fingerprint.json or "
                "<task>-<timestamp>.fingerprint.json",
                file=sys.stderr,
            )
            return 2
    else:
        out_path = default_out
        if out_path.is_symlink():
            print(
                "error: output path is a symlink; refusing to overwrite: %s" % out_path,
                file=sys.stderr,
            )
            return 2
        out = out_path.resolve()
        if not within_root(root, out):
            print("error: output must be inside the project root", file=sys.stderr)
            return 2
    if out.exists():
        if not out.is_file():
            print(
                "error: output path exists and is not a regular file: %s" % out,
                file=sys.stderr,
            )
            return 2
        reason = existing_sidecar_error(out, root, task)
        if reason:
            print("error: refusing to overwrite: %s" % reason, file=sys.stderr)
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
    print("content_hashed_files: %d" % len(rels))
    print("git_status_dirs: %s" % (", ".join(git_info.get("scope_dirs") or []) or "(none)"))
    print(
        "coverage_note: content hash covers only the listed files; git status "
        "monitors the listed directories, not their file contents"
    )
    if skipped:
        print("skipped_excluded: %s" % ", ".join(skipped))
    return 0


def looks_like_legacy_task(text: str) -> bool:
    """A v1.0-style record starts with a Markdown heading, not frontmatter."""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        return bool(re.match(r"^#{1,6}\s+\S", line))
    return False


def cmd_status_guard(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    error = task_id_error(args.task)
    if error:
        print("status: unknown")
        print("reason: %s" % error)
        return 2
    task_file = Path(args.task_file) if args.task_file else (root / ".handover" / (args.task + ".md"))
    task_file = task_file.resolve()
    if not within_root(root, task_file):
        print("status: unknown")
        print("reason: task file outside project root")
        return 2
    if not task_file.is_file():
        print("status: absent")
        print("result: new-task-allowed")
        return 0
    data, status = read_frontmatter(task_file)
    if data is None:
        if getattr(args, "legacy_migration", False) and status == "missing_frontmatter":
            try:
                text = task_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                print("status: unknown")
                print("reason: read_error: %s" % exc)
                return 2
            if looks_like_legacy_task(text):
                print("status: legacy")
                print("result: legacy-migration-required")
                print("action: migrate-frontmatter-then-rerun-status-guard")
                return 3
            print("status: unknown")
            print("reason: frontmatter missing and file is not a recognisable legacy task")
            return 2
        print("status: unknown")
        print("reason: frontmatter unreadable: %s" % status)
        return 2
    if data.get("task_id") != args.task:
        print("status: unknown")
        print("reason: task_id mismatch")
        return 2
    if not schema_is_current(data.get("schema"), allow_string=True):
        print("status: unknown")
        print("reason: schema missing or unsupported")
        return 2
    project_root = data.get("project_root")
    if not project_root:
        print("status: unknown")
        print("reason: project_root missing")
        return 2
    if Path(str(project_root)).resolve() != root:
        print("status: unknown")
        print("reason: project_root mismatch")
        return 2
    task_status = str(data.get("status") or "unknown")
    print("status: %s" % task_status)
    if task_status in ACTIVE:
        print("record: valid")
        print("result: active-reuse-allowed")
        return 0
    if task_status in ENDED:
        if args.reopen_authorised:
            print("record: valid")
            print("result: reopen-authorised")
            print("note: only use after explicit user confirmation")
            return 0
        print("result: blocked-completed-task")
        print("action: create-new-task-or-ask-user")
        print(
            "reason: target status is %s; do not write without explicit reopen confirmation"
            % task_status
        )
        return 1
    print("result: unknown")
    print("reason: unsupported or missing status")
    return 2


def cmd_check(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    error = task_id_error(args.task)
    if error:
        print("consistency: unknown")
        print("reason: %s" % error)
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

    if not schema_is_current(payload.get("schema")):
        print("consistency: unknown")
        print("reason: unsupported sidecar schema=%s" % payload.get("schema"))
        return 2
    if payload.get("task_id") != args.task:
        print("consistency: unknown")
        print("reason: sidecar task_id mismatch")
        return 2
    recorded_root = payload.get("root")
    if not recorded_root:
        print("consistency: unknown")
        print("reason: sidecar root missing")
        return 2
    if Path(recorded_root).resolve() != root:
        print("consistency: unknown")
        print("reason: sidecar root mismatch")
        return 2
    files_payload = payload.get("files")
    if not isinstance(files_payload, dict) or not files_payload:
        print("consistency: unknown")
        print("reason: sidecar has no files; empty baseline is not valid")
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
    if not schema_is_current(task_data.get("schema"), allow_string=True):
        print("consistency: unknown")
        print("reason: task schema missing or unsupported")
        return 2
    if task_data.get("task_id") != args.task:
        print("consistency: unknown")
        print("reason: task task_id mismatch")
        return 2
    task_project_root = task_data.get("project_root")
    if not task_project_root:
        print("consistency: unknown")
        print("reason: task project_root missing")
        return 2
    if Path(str(task_project_root)).resolve() != root:
        print("consistency: unknown")
        print("reason: task project_root mismatch")
        return 2
    if task_data.get("snapshot_id") != snapshot_id:
        print("consistency: unknown")
        print("reason: task/sidecar snapshot_id mismatch")
        return 2
    recorded_fingerprint_file = task_data.get("fingerprint_file")
    if not recorded_fingerprint_file:
        print("consistency: unknown")
        print("reason: task fingerprint_file missing")
        return 2
    recorded_path = (root / str(recorded_fingerprint_file)).resolve()
    if recorded_path != sidecar:
        print("consistency: unknown")
        print("reason: task fingerprint_file does not point to this sidecar")
        return 2
    recorded_fingerprint_sha = task_data.get("fingerprint_sha256")
    if not recorded_fingerprint_sha:
        print("consistency: unknown")
        print("reason: task fingerprint_sha256 missing")
        return 2
    if recorded_fingerprint_sha != sidecar_sha:
        print("consistency: unknown")
        print("reason: task fingerprint_sha256 mismatch")
        return 2

    content_changed: List[str] = []
    incomplete: List[str] = []
    for rel, old in sorted(files_payload.items()):
        if old.get("status") != "ok":
            incomplete.append("%s: baseline status %s" % (rel, old.get("status")))
            continue
        record = record_for(root, rel, int(payload.get("max_file_bytes", DEFAULT_MAX_BYTES)))
        if record.get("status") == "missing":
            content_changed.append("%s: missing" % rel)
        elif record.get("status") != "ok":
            old_size = old.get("size")
            new_size = record.get("size")
            if (
                isinstance(old_size, int)
                and isinstance(new_size, int)
                and old_size != new_size
            ):
                content_changed.append("%s: size changed" % rel)
            else:
                incomplete.append("%s: current status %s" % (rel, record.get("status")))
        elif record.get("sha256") != old.get("sha256"):
            content_changed.append(rel)

    git_changed: List[str] = []
    current_git: Optional[Dict[str, Any]] = None
    old_git = payload.get("git") or {}
    if old_git.get("available"):
        scope_paths = list(old_git.get("scope_paths") or [])
        scope_dirs = list(old_git.get("scope_dirs") or [])
        # v1.1.0 sidecars may lack root-directory scope for root-level files.
        # Add it conservatively so an existing baseline can still detect new
        # root-level entries; a new save records "." explicitly.
        if any("/" not in path for path in scope_paths) and "." not in scope_dirs:
            scope_dirs.append(".")
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
    print("content_hashed_files: %d" % len(files_payload))
    print("git_status_dirs: %s" % (", ".join(old_git.get("scope_dirs") or []) or "(none)"))
    print("scope: %d file(s), %d git entries" % (
        len(files_payload),
        len(old_git.get("status_entries") or []),
    ))
    print(
        "coverage_note: content hash covers the listed files only; git status "
        "monitors the listed directories, not their file contents"
    )
    if current_git is not None and int(current_git.get("ignored_entries") or 0) > 0:
        print(
            "out_of_scope_changes: %d (not part of matched)"
            % int(current_git.get("ignored_entries") or 0)
        )
    print("note: matched covers the declared scope only")
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
    task_dir = root / ".handover"
    if task_dir.is_symlink() and not within_root(root, task_dir):
        print(
            "error: .handover resolves outside project root: %s" % task_dir,
            file=sys.stderr,
        )
        return 2
    include_archive = bool(args.all)
    stale_days, config_warning = read_stale_days(root)
    if config_warning:
        print("warning: %s" % config_warning, file=sys.stderr)

    active_rows: List[Tuple[str, str, str, str, str, str]] = []
    exception_rows: List[Tuple[str, str, str, str, str, str]] = []
    ended_rows: List[Tuple[str, str, str, str, str]] = []
    archived_rows: List[Tuple[str, str, str, str, str]] = []
    ended_count = 0
    archived_count = 0
    records: List[Dict[str, Any]] = []

    for path in iter_task_files(root, include_archive=False):
        rel = str(path.relative_to(root))
        if not within_root(root, path):
            records.append(
                {
                    "task_id": "",
                    "title": path.stem,
                    "status": "unknown",
                    "fresh": "-",
                    "updated_at": "-",
                    "rel": rel,
                    "reasons": ["path resolves outside project root"],
                }
            )
            continue
        data, status = read_frontmatter(path)
        if data is None:
            records.append(
                {
                    "task_id": "",
                    "title": path.stem,
                    "status": "unknown",
                    "fresh": "-",
                    "updated_at": "-",
                    "rel": rel,
                    "reasons": ["frontmatter: %s" % status],
                }
            )
            continue
        task_id = str(data.get("task_id") or "")
        title = str(data.get("title") or task_id or path.stem)
        task_status = str(data.get("status") or "unknown")
        updated_at = data.get("updated_at")
        fresh = freshness(updated_at if isinstance(updated_at, str) else None, stale_days)
        reasons: List[str] = []
        if not task_id:
            reasons.append("missing task_id")
        elif path.stem != task_id:
            reasons.append("filename/task_id mismatch")
        schema = data.get("schema")
        if schema is None:
            reasons.append("missing schema")
        elif not schema_is_current(schema, allow_string=True):
            reasons.append("unsupported schema=%s" % schema)
        if task_status not in KNOWN_STATUS:
            reasons.append("unknown status")
        records.append(
            {
                "task_id": task_id,
                "title": title,
                "status": task_status,
                "fresh": fresh,
                "updated_at": str(updated_at or "-"),
                "rel": rel,
                "reasons": reasons,
            }
        )

    # Detect duplicates after reading every record so file ordering cannot
    # decide which copy stays active: all copies of a duplicated ID move to
    # EXCEPTIONS.
    id_counts: Dict[str, int] = {}
    for record in records:
        task_id = record["task_id"]
        if task_id:
            id_counts[task_id] = id_counts.get(task_id, 0) + 1

    for record in records:
        task_id = record["task_id"]
        title = record["title"]
        task_status = record["status"]
        fresh = record["fresh"]
        rel = record["rel"]
        reasons = list(record["reasons"])
        if task_id and id_counts.get(task_id, 0) > 1:
            reasons.append("duplicate task_id (%d files)" % id_counts[task_id])
        if reasons:
            exception_rows.append(
                (task_id or Path(rel).stem, title, task_status, fresh, "; ".join(reasons), rel)
            )
        elif task_status in ACTIVE:
            active_rows.append((task_id, title, task_status, fresh, record["updated_at"], rel))
        elif task_status in ENDED:
            ended_count += 1
            if include_archive:
                ended_rows.append((task_id, title, task_status, record["updated_at"], rel))
        else:
            exception_rows.append(
                (task_id or Path(rel).stem, title, task_status, fresh, "status unknown", rel)
            )

    archive = root / ".handover" / "archive"
    if archive.is_dir():
        for path in sorted(archive.glob("*.md")):
            if not path.is_file():
                continue
            rel = str(path.relative_to(root))
            if not within_root(root, path):
                exception_rows.append(
                    (
                        path.stem,
                        path.stem,
                        "unknown",
                        "-",
                        "archive path resolves outside project root",
                        rel,
                    )
                )
                continue
            archived_count += 1
            if not include_archive:
                continue
            data, status = read_frontmatter(path)
            if data is None:
                archived_rows.append((path.stem, path.stem, "unknown", "-", "%s (frontmatter: %s)" % (rel, status)))
                continue
            task_id = str(data.get("task_id") or path.stem)
            title = str(data.get("title") or task_id)
            task_status = str(data.get("status") or "unknown")
            updated_at = data.get("updated_at") or "-"
            archived_rows.append((task_id, title, task_status, str(updated_at), rel))

    print("## ACTIVE")
    if active_rows:
        print("| task | title | status | freshness | updated_at | path |")
        print("|---|---|---|---|---|---|")
        for row in sorted(active_rows):
            print("| %s | %s | %s | %s | %s | %s |" % row)
    else:
        print("(none)")

    print("")
    print("## EXCEPTIONS")
    if exception_rows:
        print("| task | title | status | freshness | reason | path |")
        print("|---|---|---|---|---|---|")
        for row in exception_rows:
            print("| %s | %s | %s | %s | %s | %s |" % row)
    else:
        print("(none)")

    if include_archive:
        print("")
        print("## ENDED")
        if ended_rows:
            print("| task | title | status | updated_at | path |")
            print("|---|---|---|---|---|")
            for row in ended_rows:
                print("| %s | %s | %s | %s | %s |" % row)
        else:
            print("(none)")
        print("")
        print("## ARCHIVED")
        if archived_rows:
            print("| task | title | status | updated_at | path |")
            print("|---|---|---|---|---|")
            for row in archived_rows:
                print("| %s | %s | %s | %s | %s |" % row)
        else:
            print("(none)")
    else:
        print("")
        print("## HIDDEN")
        print("ended: %d, archived: %d (use --all to show)" % (ended_count, archived_count))
    return 0


def estimate_tokens(text: str) -> int:
    """Rough mixed-language estimate: UTF-8 bytes / 3.

    This is not a tokenizer. For mixed Chinese/English it is usually within
    roughly 10-20% of cl100k-style counts; use it for relative distribution,
    not exact billing.
    """
    return max(1, (len(text.encode("utf-8")) + 2) // 3)


def split_sections(body_lines: List[str]) -> List[Tuple[str, List[str]]]:
    """Split Markdown body into ("## " heading, lines) sections."""
    sections: List[Tuple[str, List[str]]] = []
    name = "(preamble)"
    current: List[str] = []
    for line in body_lines:
        if line.startswith("## "):
            sections.append((name, current))
            name = line[3:].strip() or "(untitled)"
            current = [line]
        else:
            current.append(line)
    sections.append((name, current))
    return [(n, lines) for n, lines in sections if "\n".join(lines).strip()]


def cmd_stats(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    error = task_id_error(args.task)
    if error:
        print("error: %s" % error, file=sys.stderr)
        return 2
    task_file = Path(args.task_file) if args.task_file else (root / ".handover" / (args.task + ".md"))
    task_file = task_file.resolve()
    if not within_root(root, task_file):
        print("error: task file outside project root", file=sys.stderr)
        return 2
    if not task_file.is_file():
        print("error: task file not found: %s" % task_file, file=sys.stderr)
        return 2
    try:
        text = task_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print("error: cannot read task file: %s" % exc, file=sys.stderr)
        return 2

    lines = text.splitlines()
    fm_end: Optional[int] = None
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                fm_end = i
                break
    if fm_end is None:
        frontmatter_lines: List[str] = []
        body_lines = lines
    else:
        frontmatter_lines = lines[: fm_end + 1]
        body_lines = lines[fm_end + 1 :]

    fm_text = "\n".join(frontmatter_lines)
    fm_tokens = estimate_tokens(fm_text) if frontmatter_lines else 0
    decorative_lines = sum(1 for line in body_lines if line.strip() in ("---", "***", "___"))
    sections: List[Dict[str, Any]] = []
    for name, sec_lines in split_sections(body_lines):
        sec_text = "\n".join(sec_lines)
        sections.append(
            {
                "section": name,
                "lines": len(sec_lines),
                "bytes": len(sec_text.encode("utf-8")),
                "approx_tokens": estimate_tokens(sec_text),
            }
        )
    total_tokens = fm_tokens + sum(int(s["approx_tokens"]) for s in sections)
    if total_tokens <= 0:
        total_tokens = 1
    for section in sections:
        section["percent"] = round(100.0 * float(section["approx_tokens"]) / total_tokens, 1)
    fm_percent = round(100.0 * fm_tokens / total_tokens, 1)

    payload: Dict[str, Any] = {
        "task_id": args.task,
        "file": str(task_file.relative_to(root)) if within_root(root, task_file) else str(task_file),
        "bytes": len(text.encode("utf-8")),
        "lines": len(lines),
        "blank_lines": sum(1 for line in lines if not line.strip()),
        "trailing_ws_lines": sum(1 for line in lines if line != line.rstrip()),
        "decorative_lines": decorative_lines,
        "approx_tokens": total_tokens,
        "estimator": "utf8_bytes/3",
        "frontmatter": {
            "lines": len(frontmatter_lines),
            "bytes": len(fm_text.encode("utf-8")),
            "approx_tokens": fm_tokens,
            "percent": fm_percent,
        },
        "sections": sorted(sections, key=lambda item: int(item["approx_tokens"]), reverse=True),
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        return 0

    print("task: %s" % payload["task_id"])
    print("file: %s" % payload["file"])
    print("bytes: %d" % payload["bytes"])
    print("lines: %d" % payload["lines"])
    print("blank_lines: %d" % payload["blank_lines"])
    print("trailing_ws_lines: %d" % payload["trailing_ws_lines"])
    print("decorative_lines: %d" % payload["decorative_lines"])
    print("approx_tokens: %d (estimator: %s)" % (payload["approx_tokens"], payload["estimator"]))
    if frontmatter_lines:
        print(
            "frontmatter: %d tokens (%.1f%%), %d lines, %d bytes"
            % (fm_tokens, fm_percent, len(frontmatter_lines), len(fm_text.encode("utf-8")))
        )
    print("sections (tokens, percent, lines):")
    for section in payload["sections"]:
        print(
            "  %6d  %5.1f%%  %4d  %s"
            % (
                section["approx_tokens"],
                section["percent"],
                section["lines"],
                section["section"],
            )
        )
    top = payload["sections"][:3]
    if top:
        print(
            "top: %s"
            % ", ".join(
                "%s (%d, %.1f%%)"
                % (section["section"], section["approx_tokens"], section["percent"])
                for section in top
            )
        )
    print("note: rough estimate (UTF-8 bytes / 3); use the actual tokenizer for exact counts.")
    return 0


def claude_project_dir(root: Path) -> Path:
    encoded = re.sub(r"[^A-Za-z0-9]", "-", str(root))
    return CLAUDE_HOME / "projects" / encoded


def find_transcript(
    root: Path, session: Optional[str], transcript: Optional[str]
) -> Tuple[Optional[Path], Optional[str]]:
    if transcript:
        path = Path(transcript).resolve()
        if path.is_file():
            return path, None
        return None, "transcript not found: %s" % path
    if session and not SESSION_RE.match(session):
        return None, "invalid session id: %s" % session
    project_dir = claude_project_dir(root)
    if session:
        path = project_dir / (session + ".jsonl")
        if path.is_file() and within_root(project_dir, path):
            return path, None
        # An explicit session is a strict selector: never fall back to the
        # newest transcript when the requested one does not exist.
        return None, "session transcript not found: %s" % path
    env_session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if env_session and SESSION_RE.match(env_session):
        path = project_dir / (env_session + ".jsonl")
        if path.is_file() and within_root(project_dir, path):
            return path, "session from CLAUDE_CODE_SESSION_ID"
    if project_dir.is_dir():
        files = sorted(
            (
                p
                for p in project_dir.glob("*.jsonl")
                if p.is_file() and within_root(project_dir, p)
            ),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if files:
            return files[0], "auto-selected latest transcript: %s" % files[0].name
    return None, "no session transcript found under %s" % project_dir


def iter_jsonl(path: Path):
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return


def measure_shape(shape: Dict[str, Any]) -> Dict[str, Any]:
    system_blocks = shape.get("system") or []
    system_items: List[Dict[str, Any]] = []
    system_tokens = 0
    for index, block in enumerate(system_blocks):
        text = block.get("text", "") if isinstance(block, dict) else str(block)
        tokens = estimate_tokens(text)
        system_items.append(
            {
                "index": index,
                "bytes": len(text.encode("utf-8")),
                "approx_tokens": tokens,
            }
        )
        system_tokens += tokens
    groups: Dict[str, Dict[str, Any]] = {}
    tool_tokens = 0
    for tool in shape.get("tools") or []:
        name = tool.get("name", "?") if isinstance(tool, dict) else "?"
        blob = json.dumps(tool, ensure_ascii=False, separators=(",", ":"))
        tokens = estimate_tokens(blob)
        group = name.split("__")[1] if name.startswith("mcp__") and "__" in name else "builtin"
        entry = groups.setdefault(group, {"tools": 0, "bytes": 0, "approx_tokens": 0})
        entry["tools"] += 1
        entry["bytes"] += len(blob.encode("utf-8"))
        entry["approx_tokens"] += tokens
        tool_tokens += tokens
    return {
        "system": {"approx_tokens": system_tokens, "blocks": system_items},
        "tools": {
            "approx_tokens": tool_tokens,
            "groups": sorted(
                ({"server": key, **value} for key, value in groups.items()),
                key=lambda item: int(item["approx_tokens"]),
                reverse=True,
            ),
        },
    }


def message_text(message: Dict[str, Any]) -> str:
    content = message.get("content")
    parts: List[str] = []
    if isinstance(content, str):
        parts.append(content)
    elif isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            kind = block.get("type")
            if kind == "text":
                parts.append(str(block.get("text") or ""))
            elif kind == "thinking":
                parts.append(str(block.get("thinking") or ""))
            elif kind == "tool_use":
                parts.append(
                    json.dumps(block.get("input") or {}, ensure_ascii=False, separators=(",", ":"))
                )
            elif kind == "tool_result":
                inner = block.get("content")
                if isinstance(inner, str):
                    parts.append(inner)
                elif isinstance(inner, list):
                    parts.append(
                        "\n".join(
                            str(item.get("text") or "")
                            for item in inner
                            if isinstance(item, dict)
                        )
                    )
    return "\n".join(parts)


def measure_blobs(blobs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    tool_names: Dict[str, str] = {}
    for message in blobs.values():
        content = message.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool_names[str(block.get("id") or "")] = str(block.get("name") or "?")
    totals = {"system": 0, "user": 0, "assistant": 0, "tool_results": 0, "other": 0}
    tool_results: Dict[str, int] = {}
    for message in blobs.values():
        role = str(message.get("role") or "other")
        content = message.get("content")
        blocks = content if isinstance(content, list) else []
        has_result = any(
            isinstance(block, dict) and block.get("type") == "tool_result" for block in blocks
        )
        tokens = estimate_tokens(message_text(message))
        if has_result:
            totals["tool_results"] += tokens
            for block in blocks:
                if not isinstance(block, dict) or block.get("type") != "tool_result":
                    continue
                name = tool_names.get(str(block.get("tool_use_id") or ""), "tool_result")
                inner = block.get("content")
                if isinstance(inner, str):
                    inner_text = inner
                elif isinstance(inner, list):
                    inner_text = "\n".join(
                        str(item.get("text") or "")
                        for item in inner
                        if isinstance(item, dict)
                    )
                else:
                    inner_text = ""
                if inner_text:
                    tool_results[name] = tool_results.get(name, 0) + estimate_tokens(inner_text)
        elif role == "system":
            totals["system"] += tokens
        elif role == "user":
            totals["user"] += tokens
        elif role == "assistant":
            totals["assistant"] += tokens
        else:
            totals["other"] += tokens
    return {
        "messages": len(blobs),
        "approx_tokens": sum(totals.values()),
        "by_category": totals,
        "top_tool_results": sorted(
            ({"tool": key, "approx_tokens": value} for key, value in tool_results.items()),
            key=lambda item: int(item["approx_tokens"]),
            reverse=True,
        )[:10],
    }


def measure_config(root: Path) -> List[Dict[str, Any]]:
    candidates: List[Tuple[str, Path]] = [
        ("project CLAUDE.md", root / "CLAUDE.md"),
        ("global CLAUDE.md", CLAUDE_HOME / "CLAUDE.md"),
    ]
    rules = CLAUDE_HOME / "rules"
    if rules.is_dir():
        candidates.extend(("global rule", path) for path in sorted(rules.glob("*.md")))
    memory = claude_project_dir(root) / "memory"
    if memory.is_dir():
        candidates.extend(("memory", path) for path in sorted(memory.glob("*.md")))
    for base, label in (
        (CLAUDE_HOME / "skills", "global skill"),
        (root / ".claude" / "skills", "project skill"),
    ):
        if base.is_dir():
            candidates.extend((label, path) for path in sorted(base.glob("*/SKILL.md")))
    if (root / "handover.md").is_file():
        candidates.append(("handover entry", root / "handover.md"))
    task_dir = root / ".handover"
    if task_dir.is_dir():
        candidates.extend(("task doc", path) for path in sorted(task_dir.glob("*.md")))
    items: List[Dict[str, Any]] = []
    for label, path in candidates:
        try:
            if not path.is_file():
                continue
            if label in ("task doc", "handover entry") and not within_root(root, path):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if label in ("global skill", "project skill"):
            display = "%s/%s" % (path.parent.name, path.name)
        else:
            display = path.name
        items.append(
            {
                "label": label,
                "display": display,
                "bytes": len(text.encode("utf-8")),
                "approx_tokens": estimate_tokens(text),
            }
        )
    return sorted(items, key=lambda item: int(item["approx_tokens"]), reverse=True)[:20]


def cmd_analysis(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    if args.session and not SESSION_RE.match(args.session):
        print("error: invalid session id", file=sys.stderr)
        return 2
    transcript_path, transcript_note = find_transcript(root, args.session, args.transcript)
    if (args.transcript or args.session) and not transcript_path:
        print("error: %s" % (transcript_note or "transcript not found"), file=sys.stderr)
        return 2
    shapes: List[Tuple[str, Dict[str, Any]]] = []
    blobs: Dict[str, Dict[str, Any]] = {}
    model: Optional[str] = None
    if transcript_path:
        for obj in iter_jsonl(transcript_path):
            kind = obj.get("type")
            if kind == "api-request-shape":
                shapes.append((str(obj.get("timestamp") or ""), obj.get("shape") or {}))
            elif kind == "api-request":
                params = obj.get("params") or {}
                if params.get("model"):
                    model = str(params.get("model"))
            elif kind == "api-request-blob":
                digest = obj.get("hash")
                message = obj.get("message")
                if digest and isinstance(message, dict):
                    blobs[digest] = message
    latest_shape = max(shapes, key=lambda item: item[0])[1] if shapes else {}
    previous_shape = sorted(shapes, key=lambda item: item[0])[-2][1] if len(shapes) >= 2 else {}
    shape_data = measure_shape(latest_shape)
    previous_data = measure_shape(previous_shape) if previous_shape else None
    blob_data = measure_blobs(blobs) if blobs else None
    config_data = measure_config(root)
    context_window = max(1, int(args.context_window))

    def pct(tokens: int) -> float:
        return round(100.0 * tokens / context_window, 1)

    prefix_tokens = int(shape_data["system"]["approx_tokens"]) + int(
        shape_data["tools"]["approx_tokens"]
    )
    blob_tokens = int(blob_data["approx_tokens"]) if blob_data else 0
    measured_total = prefix_tokens + blob_tokens

    for group in shape_data["tools"]["groups"]:
        group["percent"] = pct(int(group["approx_tokens"]))
    for item in (blob_data or {}).get("by_category", {}).items():
        if blob_data:
            blob_data["by_category"][item[0]] = {
                "approx_tokens": item[1],
                "percent": pct(item[1]),
            }
    for item in (blob_data or {}).get("top_tool_results", []):
        item["percent"] = pct(int(item["approx_tokens"]))

    shape_changes: List[Dict[str, Any]] = []
    if previous_data:
        previous_groups = {
            str(group["server"]): int(group["approx_tokens"])
            for group in previous_data["tools"]["groups"]
        }
        current_groups = {
            str(group["server"]): int(group["approx_tokens"])
            for group in shape_data["tools"]["groups"]
        }
        for server in sorted(set(previous_groups) | set(current_groups)):
            before = previous_groups.get(server, 0)
            after = current_groups.get(server, 0)
            if abs(after - before) >= 500:
                shape_changes.append(
                    {"server": server, "previous": before, "current": after, "delta": after - before}
                )
        shape_changes.sort(key=lambda item: abs(int(item["delta"])), reverse=True)

    recommendations: List[str] = []
    for group in shape_data["tools"]["groups"]:
        if str(group["server"]) != "builtin" and int(group["approx_tokens"]) >= 5000:
            recommendations.append(
                "%s: %d tools / ~%d tok (%.1f%%); disable this MCP server if the task does not need it."
                % (
                    group["server"],
                    group["tools"],
                    group["approx_tokens"],
                    pct(int(group["approx_tokens"])),
                )
            )
    if blob_data:
        for item in blob_data["top_tool_results"][:5]:
            if int(item["approx_tokens"]) >= 5000:
                recommendations.append(
                    "tool result %s: ~%d tok; use Grep/Read offset or a read budget."
                    % (item["tool"], item["approx_tokens"])
                )
        conversation = int(blob_data["by_category"].get("assistant", {}).get("approx_tokens", 0)) + int(
            blob_data["by_category"].get("user", {}).get("approx_tokens", 0)
        )
        if conversation >= 50000:
            recommendations.append(
                "conversation history: ~%d tok; use /compact or a new session for unrelated work."
                % conversation
            )
    for item in config_data:
        if item["label"] in ("global rule", "project CLAUDE.md", "global CLAUDE.md", "memory") and int(
            item["approx_tokens"]
        ) >= 5000:
            recommendations.append(
                "%s: ~%d tok; trim it or move detail into references."
                % (item["label"], item["approx_tokens"])
            )
    if not transcript_path:
        recommendations.append(
            "No transcript found; run /context in the session for the official breakdown."
        )
    if not shape_data["tools"]["groups"]:
        recommendations.append(
            "No api-request-shape found; tool schema sizes are unavailable in this transcript."
        )
    if not recommendations:
        recommendations.append("No single large item detected at the current thresholds.")

    payload: Dict[str, Any] = {
        "project_root": str(root),
        "transcript": str(transcript_path) if transcript_path else None,
        "transcript_note": transcript_note,
        "model": model,
        "context_window": context_window,
        "estimator": "utf8_bytes/3",
        "request_prefix": {
            "system": shape_data["system"],
            "tools": shape_data["tools"],
            "total_approx_tokens": prefix_tokens,
            "percent": pct(prefix_tokens),
        },
        "shape_changes": shape_changes,
        "transcript_blobs": blob_data,
        "config_on_disk": config_data,
        "measured_total_approx_tokens": measured_total,
        "measured_total_percent": pct(measured_total),
        "recommendations": recommendations,
        "note": (
            "request prefix is exact for the latest api-request-shape; transcript blobs may "
            "include compacted history; /context is the official breakdown."
        ),
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        return 0

    print("context analysis — %s" % root)
    print("transcript: %s" % (transcript_path if transcript_path else "(not found)"))
    if transcript_note:
        print("transcript_note: %s" % transcript_note)
    if model:
        print("model: %s" % model)
    print("context_window: %d" % context_window)
    print("")
    print("request prefix (latest api-request-shape):")
    print(
        "  system_prompt: %d tok (%.1f%%)"
        % (
            shape_data["system"]["approx_tokens"],
            pct(int(shape_data["system"]["approx_tokens"])),
        )
    )
    print(
        "  tool_schemas: %d tok (%.1f%%)"
        % (shape_data["tools"]["approx_tokens"], pct(int(shape_data["tools"]["approx_tokens"])))
    )
    for group in shape_data["tools"]["groups"]:
        print(
            "    %s: %d tools, %d tok (%.1f%%)"
            % (group["server"], group["tools"], group["approx_tokens"], group["percent"])
        )
    print("  prefix_total: %d tok (%.1f%%)" % (prefix_tokens, pct(prefix_tokens)))
    if shape_changes:
        print("")
        print("shape changes:")
        for change in shape_changes:
            print(
                "  %s: %d -> %d (%+d)"
                % (change["server"], change["previous"], change["current"], change["delta"])
            )
    if blob_data:
        print("")
        print("transcript blobs (all; may include compacted history):")
        print(
            "  total: %d tok (%.1f%%), %d messages"
            % (blob_data["approx_tokens"], pct(int(blob_data["approx_tokens"])), blob_data["messages"])
        )
        for name in ("system", "user", "assistant", "tool_results", "other"):
            value = blob_data["by_category"].get(name, {})
            if value:
                print("  %s: %d tok (%.1f%%)" % (name, value["approx_tokens"], value["percent"]))
        if blob_data["top_tool_results"]:
            print("  top tool results:")
            for item in blob_data["top_tool_results"]:
                print("    %s: %d tok (%.1f%%)" % (item["tool"], item["approx_tokens"], item["percent"]))
    if config_data:
        print("")
        print("config on disk (reference; may overlap with the request prefix):")
        for item in config_data[:10]:
            print("  %s: %d tok — %s" % (item["label"], item["approx_tokens"], item["display"]))
    print("")
    print("measured_total: %d tok (%.1f%%)" % (measured_total, pct(measured_total)))
    print("")
    print("recommendations:")
    for recommendation in recommendations:
        print("  - %s" % recommendation)
    print("")
    print("note: %s" % payload["note"])
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

    p_guard = sub.add_parser("status-guard", help="check whether a task may be reused for save")
    p_guard.add_argument("--root", required=True)
    p_guard.add_argument("--task", required=True)
    p_guard.add_argument("--task-file")
    p_guard.add_argument("--reopen-authorised", action="store_true")
    p_guard.add_argument(
        "--legacy-migration",
        action="store_true",
        help="report a recognisable frontmatter-less v1.0 record as migration-required",
    )
    p_guard.set_defaults(func=cmd_status_guard)

    p_ignore = sub.add_parser("ignore-check", help="check task data is ignored and untracked")
    p_ignore.add_argument("--root", required=True)
    p_ignore.set_defaults(func=cmd_ignore_check)

    p_stats = sub.add_parser("stats", help="estimate token distribution of a task document")
    p_stats.add_argument("--root", required=True)
    p_stats.add_argument("--task", required=True)
    p_stats.add_argument("--task-file")
    p_stats.add_argument("--json", action="store_true")
    p_stats.set_defaults(func=cmd_stats)

    p_analysis = sub.add_parser("analysis", help="audit context usage from the session transcript")
    p_analysis.add_argument("--root", required=True)
    p_analysis.add_argument("--session")
    p_analysis.add_argument("--transcript")
    p_analysis.add_argument("--context-window", type=int, default=DEFAULT_CONTEXT_WINDOW)
    p_analysis.add_argument("--json", action="store_true")
    p_analysis.set_defaults(func=cmd_analysis)
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
