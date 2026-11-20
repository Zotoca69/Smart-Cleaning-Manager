import base64
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import config
from _testsupport import ACK, Run, change, snapshot, IDS
from export import IntegrityError, export_capture, verify_capture


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.run = Run([ACK, snapshot(), change(IDS[0], "cleaning", 1001.0)], stop_after=4)
        self.addCleanup(self.run.cleanup)
        self.out = Path(self.run.tmp.name) / "out.zip"

    def test_export_roundtrip_digests_and_no_overwrite(self):
        result = export_capture(self.run.path, self.out)
        with zipfile.ZipFile(self.out) as archive:
            self.assertEqual(sorted(archive.namelist()), [config.MANIFEST_FILE, config.MESSAGES_FILE])
            for name in archive.namelist():
                self.assertEqual(archive.read(name), (self.run.path / name).read_bytes())
        self.assertEqual(result["archive_sha256"], hashlib.sha256(self.out.read_bytes()).hexdigest())
        self.assertEqual(result["manifest_sha256"], hashlib.sha256((self.run.path / config.MANIFEST_FILE).read_bytes()).hexdigest())
        self.assertEqual(Path(result["sidecar"]).read_text(), f"{result['archive_sha256']}  out.zip\n")
        self.assertTrue(result["complete"])
        with self.assertRaises(FileExistsError):
            export_capture(self.run.path, self.out)

    def test_incomplete_capture_exports_with_status(self):
        gap = Run([ACK, snapshot(), {"id": 1, "type": "event", "event": {"r": [IDS[0]]}}])
        self.addCleanup(gap.cleanup)
        result = export_capture(gap.path, Path(gap.tmp.name) / "gap.zip")
        self.assertFalse(result["complete"])
        self.assertIn("observation gap", result["reason"])

    def _rewrite_rows(self, mutate):
        path = self.run.path / config.MESSAGES_FILE
        rows = [json.loads(l) for l in path.read_bytes().splitlines()]
        rows = mutate(rows)
        path.write_bytes(b"".join((json.dumps(r, sort_keys=True) + "\n").encode() for r in rows))

    def test_tampering_detected(self):
        def payload(rows):
            rows[1]["payload_b64"] = base64.b64encode(b'{"id":1}').decode()
            return rows
        mutations = {
            "payload": payload,
            "dropped_row": lambda rows: rows[:-1],
            "reordered": lambda rows: [rows[0], rows[2], rows[1], rows[3]],
            "extra_row_after_interruption": lambda rows: rows + [dict(rows[-1], seq=len(rows) + 1)],
        }
        original = (self.run.path / config.MESSAGES_FILE).read_bytes()
        for name, mutate in mutations.items():
            with self.subTest(name):
                (self.run.path / config.MESSAGES_FILE).write_bytes(original)
                self._rewrite_rows(mutate)
                with self.assertRaises(IntegrityError):
                    verify_capture(self.run.path)
                self.assertFalse(self.out.exists())

    def test_row_hash_checked_even_if_aggregate_recomputed(self):
        def forge(rows):
            rows[1]["payload_b64"] = base64.b64encode(b"forged").decode()
            return rows
        self._rewrite_rows(forge)
        manifest_path = self.run.path / config.MANIFEST_FILE
        manifest = json.loads(manifest_path.read_text())
        manifest["sha256"] = hashlib.sha256((self.run.path / config.MESSAGES_FILE).read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaises(IntegrityError):
            verify_capture(self.run.path)

    def test_manifest_problems(self):
        manifest_path = self.run.path / config.MANIFEST_FILE
        good = manifest_path.read_text()
        for broken in ("{", json.dumps(dict(json.loads(good), schema="old"))):
            with self.subTest(broken=broken[:20]):
                manifest_path.write_text(broken)
                with self.assertRaises(IntegrityError):
                    verify_capture(self.run.path)
        manifest_path.unlink()
        with self.assertRaises(IntegrityError):
            verify_capture(self.run.path)


if __name__ == "__main__":
    unittest.main()
