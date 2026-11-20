"""Windows ACL evidence for the test package: create a synthetic capture and print its ACLs.

Prints SIDs (sanitized by run_tests.ps1 before sharing) and the icacls listing.
Synthetic data only; the sample folder is removed afterwards.
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import config
import storage


def main():
    base = Path(tempfile.mkdtemp(prefix="scm-acl-"))
    try:
        sample = base / "acl-sample"
        store = storage.EvidenceStore(sample, ["sensor.example"], {"synthetic": True})
        store.record("send", b"{}")
        store.close()
        report = {
            "storage": store.meta["storage"],
            "verified_current_user_only": storage.verify_private_capture(sample),
            "folder_acl": storage.read_windows_acl(sample),
            "file_acl": storage.read_windows_acl(sample / config.MESSAGES_FILE),
        }
        print(json.dumps(report, indent=2))
        print(subprocess.run(["icacls", str(sample)], capture_output=True, text=True, errors="replace").stdout)
        print(subprocess.run(["icacls", str(sample / config.MESSAGES_FILE)], capture_output=True, text=True, errors="replace").stdout)
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    main()
