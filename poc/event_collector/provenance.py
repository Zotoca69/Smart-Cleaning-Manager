"""Collector provenance recorded in every manifest (no secrets, no HA address)."""
import hashlib
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

import config

_HERE = Path(__file__).resolve().parent
_SHA = re.compile(r"[0-9a-f]{40}")


def collector_revision():
    """Best-effort source revision: env override, git checkout, or GitHub archive folder name."""
    value = os.environ.get("SCM_COLLECTOR_REVISION", "")
    if _SHA.fullmatch(value):
        return value, "environment"
    try:
        out = subprocess.run(["git", "-C", str(_HERE), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5, check=False)
        if out.returncode == 0 and _SHA.fullmatch(out.stdout.strip()):
            dirty = subprocess.run(["git", "-C", str(_HERE), "status", "--porcelain", "--", "."], capture_output=True, text=True, timeout=5, check=False)
            return out.stdout.strip(), "git-dirty" if dirty.stdout.strip() else "git"
    except (OSError, subprocess.SubprocessError):
        pass
    for parent in _HERE.parents:
        match = re.search(r"-([0-9a-f]{40})$", parent.name)
        if match:
            return match.group(1), "archive-folder"
    return "unknown", "unavailable"


def source_digest():
    """SHA-256 over the collector's own Python sources, for tamper evidence."""
    digest = hashlib.sha256()
    for name in sorted(p.name for p in _HERE.glob("*.py") if not p.name.startswith("test_")):
        digest.update(name.encode() + b"\0" + (_HERE / name).read_bytes() + b"\0")
    return digest.hexdigest()


def runtime_provenance(url=None, synthetic=False):
    try:
        import websockets
        ws_version = websockets.__version__
    except ImportError:
        ws_version = "not installed"
    revision, revision_source = collector_revision()
    info = {
        "collector_revision": revision,
        "collector_revision_source": revision_source,
        "collector_source_sha256": source_digest(),
        "schema": config.SCHEMA_VERSION,
        "python": platform.python_version(),
        "implementation": sys.implementation.name,
        "websockets": ws_version,
        "os": platform.system(),
        "os_release": platform.release(),
        "synthetic": bool(synthetic),
        "ha_version": None,
        "endpoint_sha256": hashlib.sha256(url.encode()).hexdigest() if url else None,
    }
    return info
