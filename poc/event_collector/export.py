"""Capture verification and ZIP export with digests for external anchoring."""
import base64
import binascii
import hashlib
import json
import zipfile
from pathlib import Path

import config


class IntegrityError(ValueError):
    """The capture folder does not match its manifest."""


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_capture(source):
    """Verify manifest, aggregate hash, sequence, session and per-row payload hashes.

    Returns the parsed manifest. Raises IntegrityError on any mismatch,
    including rows written after the last manifest update (interrupted capture).
    """
    source = Path(source)
    try:
        manifest_bytes = (source / config.MANIFEST_FILE).read_bytes()
        rows_bytes = (source / config.MESSAGES_FILE).read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, ValueError) as exc:
        raise IntegrityError("capture files missing or unreadable") from exc
    if manifest.get("schema") != config.SCHEMA_VERSION:
        raise IntegrityError("unsupported manifest schema")
    if hashlib.sha256(rows_bytes).hexdigest() != manifest.get("sha256"):
        raise IntegrityError("aggregate hash mismatch (tampered or interrupted capture)")
    lines = rows_bytes.splitlines()
    if len(lines) != manifest.get("messages"):
        raise IntegrityError("message count mismatch")
    total = 0
    previous_elapsed = -1
    for number, line in enumerate(lines, 1):
        try:
            row = json.loads(line)
            payload = base64.b64decode(row["payload_b64"], validate=True)
        except (ValueError, KeyError, binascii.Error) as exc:
            raise IntegrityError(f"row {number} unreadable") from exc
        if row.get("seq") != number or row.get("session_id") != manifest.get("session_id"):
            raise IntegrityError(f"row {number} sequence or session mismatch")
        if hashlib.sha256(payload).hexdigest() != row.get("sha256"):
            raise IntegrityError(f"row {number} payload hash mismatch")
        if row.get("direction") not in ("send", "receive") or (number == 1) != (row["direction"] == "send"):
            raise IntegrityError(f"row {number} unexpected direction")
        if not isinstance(row.get("elapsed_ns"), int) or row["elapsed_ns"] < previous_elapsed:
            raise IntegrityError(f"row {number} elapsed time not monotonic")
        previous_elapsed = row["elapsed_ns"]
        total += len(payload)
    if total != manifest.get("payload_bytes"):
        raise IntegrityError("payload byte count mismatch")
    return manifest


def export_capture(source, target):
    """Verify, write a new ZIP (never overwrite), re-verify it and write a .sha256 sidecar.

    Returns dict(manifest_sha256, archive_sha256, complete, reason, sidecar).
    Incomplete captures can be exported; their status travels in the manifest.
    """
    source, target = Path(source), Path(target)
    manifest = verify_capture(source)
    manifest_bytes = (source / config.MANIFEST_FILE).read_bytes()
    rows_bytes = (source / config.MESSAGES_FILE).read_bytes()
    with zipfile.ZipFile(target, "x", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(config.MANIFEST_FILE, manifest_bytes)
        archive.writestr(config.MESSAGES_FILE, rows_bytes)
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None or archive.read(config.MANIFEST_FILE) != manifest_bytes or archive.read(config.MESSAGES_FILE) != rows_bytes:
            raise IntegrityError("archive verification failed")
    archive_sha = sha256_file(target)
    sidecar = target.with_name(target.name + ".sha256")
    with open(sidecar, "x", encoding="ascii", newline="\n") as handle:
        handle.write(f"{archive_sha}  {target.name}\n")
    return {
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "archive_sha256": archive_sha,
        "complete": manifest["complete"],
        "reason": manifest["reason"],
        "sidecar": str(sidecar),
    }
