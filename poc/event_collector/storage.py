"""Private local evidence storage for the POC12C collector.

The capture folder is created new and made private before any file is
written: POSIX mode 0700 (files 0600); on Windows inherited permissions are
removed and full control is granted only to the current user's SID using the
built-in `icacls` tool, then verified with PowerShell `Get-Acl` (SIDs, not
localized names). Any failure stops the capture before evidence is written.
"""
import base64
import datetime
import hashlib
import json
import os
import stat
import subprocess
import time
import uuid
from pathlib import Path

import config


class StorageError(RuntimeError):
    """Private storage could not be established or verified."""


def _run(args, env=None):
    result = subprocess.run(args, capture_output=True, text=True, errors="replace", env=env, check=False)
    if result.returncode != 0:
        raise StorageError(f"{Path(args[0]).name} failed with exit code {result.returncode}")
    return result.stdout


def current_windows_sid(runner=_run):
    """Return the SID of the current Windows user via the built-in `whoami`."""
    output = runner(["whoami", "/user", "/fo", "csv", "/nh"]).strip()
    sid = output.rsplit(",", 1)[-1].strip().strip('"') if output else ""
    if not sid.startswith("S-1-"):
        raise StorageError("could not determine current user SID")
    return sid


_ACL_SCRIPT = (
    "$a=Get-Acl -LiteralPath $env:SCM_ACL_PATH;"
    "$r=@($a.Access|ForEach-Object{[pscustomobject]@{"
    "sid=$_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value;"
    "type=[string]$_.AccessControlType;rights=[string]$_.FileSystemRights;inherited=$_.IsInherited}});"
    "[pscustomobject]@{protected=$a.AreAccessRulesProtected;rules=$r}|ConvertTo-Json -Depth 4 -Compress"
)


def read_windows_acl(path, runner=_run):
    """Return {'protected': bool, 'rules': [...]} for a path using Get-Acl."""
    env = dict(os.environ, SCM_ACL_PATH=str(path))
    output = runner(["powershell", "-NoProfile", "-NonInteractive", "-Command", _ACL_SCRIPT], env=env)
    try:
        data = json.loads(output)
    except ValueError as exc:
        raise StorageError("unreadable ACL output") from exc
    rules = data.get("rules") or []
    if isinstance(rules, dict):
        rules = [rules]
    return {"protected": bool(data.get("protected")), "rules": rules}


def check_windows_acl(acl, sid, require_protected=True):
    """Fail closed unless every access rule is an Allow rule for `sid` only."""
    if require_protected and not acl["protected"]:
        raise StorageError("inherited permissions are still active")
    if not acl["rules"]:
        raise StorageError("no access rules found")
    for rule in acl["rules"]:
        if rule.get("sid") != sid or rule.get("type") != "Allow":
            raise StorageError("access granted to another principal")


def protect_windows_directory(path, runner=_run):
    sid = current_windows_sid(runner)
    runner(["icacls", str(path), "/inheritance:r", "/grant:r", f"*{sid}:(OI)(CI)F"])
    check_windows_acl(read_windows_acl(path, runner), sid)
    return sid


def check_posix_private(path, expected):
    mode = stat.S_IMODE(os.stat(path).st_mode)
    if mode & (stat.S_IRWXG | stat.S_IRWXO) or mode != expected:
        raise StorageError(f"{Path(path).name} is not private (mode {oct(mode)})")


def create_private_directory(path, platform=os.name, runner=_run):
    """Create a new private capture directory; returns a description of protection."""
    path = Path(path)
    path.mkdir(mode=0o700, parents=False, exist_ok=False)
    try:
        if platform == "nt":
            sid = protect_windows_directory(path, runner)
            return {"mechanism": "windows-acl", "principal_sid_sha256": hashlib.sha256(sid.encode()).hexdigest()}
        os.chmod(path, 0o700)
        check_posix_private(path, 0o700)
        return {"mechanism": "posix-mode-0700"}
    except Exception:
        path.rmdir()
        raise


def verify_private_capture(path, platform=os.name, runner=_run):
    """Re-check folder and file protection (used by tests and the Windows package)."""
    path = Path(path)
    if platform == "nt":
        sid = current_windows_sid(runner)
        check_windows_acl(read_windows_acl(path, runner), sid)
        for child in path.iterdir():
            check_windows_acl(read_windows_acl(child, runner), sid, require_protected=False)
    else:
        check_posix_private(path, 0o700)
        for child in path.iterdir():
            check_posix_private(child, 0o600)
    return True


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class EvidenceStore:
    """Append-only capture rows with per-row and aggregate SHA-256.

    The manifest is rewritten atomically after every row so an interrupted
    capture remains verifiable up to its last complete row.
    """

    def __init__(self, path, ids, provenance, platform=os.name, runner=_run):
        self.path = Path(path)
        protection = create_private_directory(self.path, platform, runner)
        fd = os.open(self.path / config.MESSAGES_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
        self.file = os.fdopen(fd, "wb")
        self._hash = hashlib.sha256()
        self._start_ns = time.monotonic_ns()
        self._seen = set()
        self.closed = False
        self.meta = {
            "schema": config.SCHEMA_VERSION,
            "session_id": str(uuid.uuid4()),
            "started_utc": utc_now(),
            "ended_utc": None,
            "status": "in_progress",
            "complete": False,
            "reason": "capture in progress",
            "ended_by": None,
            "allowlist": list(ids),
            "provenance": dict(provenance),
            "storage": protection,
            "messages": 0,
            "payload_bytes": 0,
            "sha256": self._hash.hexdigest(),
            "flags": {"duplicate_payloads": 0, "out_of_order_server_time": 0, "unavailable_or_unknown": [], "removed_entities": []},
            "freshness": "UNKNOWN",
            "device_truth": "NOT_ESTABLISHED",
        }
        self._write_manifest()
        if platform != "nt":
            check_posix_private(self.path / config.MESSAGES_FILE, 0o600)
            check_posix_private(self.path / config.MANIFEST_FILE, 0o600)

    def _write_manifest(self):
        tmp = self.path / "manifest.tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0), 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(json.dumps(self.meta, indent=2, sort_keys=True).encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, self.path / config.MANIFEST_FILE)

    def record(self, direction, raw, derived=None):
        """Store exact application bytes; returns (seq, duplicate)."""
        if self.closed:
            raise RuntimeError("store closed")
        if not isinstance(raw, (bytes, bytearray)):
            raise TypeError("raw message bytes required")
        raw = bytes(raw)
        if self.meta["payload_bytes"] + len(raw) > config.MAX_CAPTURE_BYTES:
            raise ValueError("capture size limit reached")
        digest = hashlib.sha256(raw).hexdigest()
        duplicate = digest in self._seen
        self._seen.add(digest)
        seq = self.meta["messages"] + 1
        row = {
            "seq": seq,
            "session_id": self.meta["session_id"],
            "direction": direction,
            "utc": utc_now(),
            "elapsed_ns": time.monotonic_ns() - self._start_ns,
            "sha256": digest,
            "duplicate_of_earlier_payload": duplicate,
            "payload_b64": base64.b64encode(raw).decode("ascii"),
        }
        if derived is not None:
            row["derived"] = derived
        line = (json.dumps(row, sort_keys=True) + "\n").encode("utf-8")
        self.file.write(line)
        self.file.flush()
        os.fsync(self.file.fileno())
        self._hash.update(line)
        self.meta["messages"] = seq
        self.meta["payload_bytes"] += len(raw)
        self.meta["sha256"] = self._hash.hexdigest()
        if duplicate:
            self.meta["flags"]["duplicate_payloads"] += 1
        self._write_manifest()
        return seq, duplicate

    def flag(self, name, value=1):
        flags = self.meta["flags"]
        if isinstance(flags[name], list):
            flags[name] = sorted(set(flags[name]) | set(value))
        else:
            flags[name] += value
        self._write_manifest()

    def finish(self, complete, reason, ended_by, extra=None):
        if extra:
            self.meta["provenance"].update(extra)
        self.meta.update(complete=bool(complete), reason=reason, ended_by=ended_by, ended_utc=utc_now(), status="complete" if complete else "incomplete")

    def close(self):
        if self.closed:
            return
        try:
            if self.meta["status"] == "in_progress":
                self.meta.update(status="incomplete", complete=False, reason="capture closed without result", ended_utc=utc_now())
            self._write_manifest()
        finally:
            self.closed = True
            self.file.close()
