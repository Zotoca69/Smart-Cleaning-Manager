import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

import config
import storage
from export import verify_capture

SID = "S-1-5-21-1000-1000-1000-1001"
OTHER = "S-1-5-18"
REQUIRE_WINDOWS_ACL = os.environ.get("SCM_REQUIRE_WINDOWS_ACL") == "1"


class FakeWindows:
    """Records Windows tool invocations and returns scripted Get-Acl results."""

    def __init__(self, acl=None, whoami=f'"host\\user","{SID}"'):
        self.calls = []
        self.acl = acl if acl is not None else {"protected": True, "rules": [{"sid": SID, "type": "Allow", "rights": "FullControl", "inherited": False}]}
        self.whoami = whoami

    def __call__(self, args, env=None):
        self.calls.append((list(args), env))
        tool = Path(args[0]).name.lower()
        if tool == "whoami":
            return self.whoami
        if tool == "icacls":
            return "processed"
        if tool == "powershell":
            return json.dumps(self.acl)
        raise AssertionError(args)


class WindowsAclLogicTests(unittest.TestCase):
    """Offline checks of the Windows protection logic (real ACLs: WindowsAclRealTests)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "capture"

    def test_commands_and_success(self):
        fake = FakeWindows()
        result = storage.create_private_directory(self.path, platform="nt", runner=fake)
        self.assertEqual(result["mechanism"], "windows-acl")
        self.assertNotIn(SID, json.dumps(result))
        icacls = [c for c in fake.calls if c[0][0] == "icacls"][0][0]
        self.assertEqual(icacls, ["icacls", str(self.path), "/inheritance:r", "/grant:r", f"*{SID}:(OI)(CI)F"])
        ps = [c for c in fake.calls if c[0][0] == "powershell"][0]
        self.assertEqual(ps[1]["SCM_ACL_PATH"], str(self.path))  # path passed via env, not interpolated

    def test_fail_closed_and_cleanup(self):
        bad_acls = [
            {"protected": False, "rules": [{"sid": SID, "type": "Allow"}]},
            {"protected": True, "rules": [{"sid": SID, "type": "Allow"}, {"sid": OTHER, "type": "Allow"}]},
            {"protected": True, "rules": [{"sid": SID, "type": "Deny"}]},
            {"protected": True, "rules": []},
        ]
        for acl in bad_acls:
            with self.subTest(acl=acl):
                with self.assertRaises(storage.StorageError):
                    storage.create_private_directory(self.path, platform="nt", runner=FakeWindows(acl))
                self.assertFalse(self.path.exists())
        with self.assertRaises(storage.StorageError):
            storage.create_private_directory(self.path, platform="nt", runner=FakeWindows(whoami="garbage"))
        self.assertFalse(self.path.exists())

    def test_single_rule_object_from_convertto_json(self):
        fake = FakeWindows({"protected": True, "rules": {"sid": SID, "type": "Allow"}})
        storage.create_private_directory(self.path, platform="nt", runner=fake)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "capture"

    def test_existing_folder_rejected(self):
        self.path.mkdir()
        with self.assertRaises(FileExistsError):
            storage.EvidenceStore(self.path, ["sensor.x"], {})

    def test_manifest_tracks_every_row_so_interruption_is_verifiable(self):
        store = storage.EvidenceStore(self.path, ["sensor.x"], {})
        store.record("send", b'{"id":1}')
        store.record("receive", b'{"id":1,"type":"result","success":true}')
        verify_capture(self.path)  # verifiable while still open (simulated crash point)
        m = json.loads((self.path / config.MANIFEST_FILE).read_text())
        self.assertEqual((m["status"], m["complete"], m["messages"]), ("in_progress", False, 2))
        store.close()
        self.assertEqual(json.loads((self.path / config.MANIFEST_FILE).read_text())["status"], "incomplete")

    def test_only_bytes_accepted(self):
        store = storage.EvidenceStore(self.path, ["sensor.x"], {})
        self.addCleanup(store.close)
        with self.assertRaises(TypeError):
            store.record("send", "text")

    @unittest.skipUnless(os.name == "posix", "POSIX permission bits")
    def test_posix_private_modes(self):
        old = os.umask(0)
        try:
            store = storage.EvidenceStore(self.path, ["sensor.x"], {})
            store.record("send", b"{}")
            store.close()
        finally:
            os.umask(old)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o700)
        for child in self.path.iterdir():
            self.assertEqual(stat.S_IMODE(child.stat().st_mode), 0o600, child.name)
        self.assertTrue(storage.verify_private_capture(self.path))
        os.chmod(self.path / config.MESSAGES_FILE, 0o644)
        with self.assertRaises(storage.StorageError):
            storage.verify_private_capture(self.path)


@unittest.skipUnless(os.name == "nt" or REQUIRE_WINDOWS_ACL, "real Windows ACLs (forced by SCM_REQUIRE_WINDOWS_ACL=1)")
class WindowsAclRealTests(unittest.TestCase):
    def test_real_acl_is_current_user_only(self):
        self.assertEqual(os.name, "nt", "Windows ACL verification required but not running on Windows")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture"
            store = storage.EvidenceStore(path, ["sensor.x"], {})
            store.record("send", b"{}")
            store.close()
            self.assertEqual(store.meta["storage"]["mechanism"], "windows-acl")
            self.assertTrue(storage.verify_private_capture(path))
            sid = storage.current_windows_sid()
            for target in [path, *path.iterdir()]:
                acl = storage.read_windows_acl(target)
                self.assertEqual({r["sid"] for r in acl["rules"]}, {sid}, target.name)
            self.assertTrue(storage.read_windows_acl(path)["protected"])


if __name__ == "__main__":
    unittest.main()
