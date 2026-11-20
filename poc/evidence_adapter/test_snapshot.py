import unittest
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace as NS
from snapshot import snapshot

class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.c = NS(_last_update_success_time=self.now,
                    properties_api=NS(status=NS(in_cleaning=3, secret="hidden"),
                    clean_summary=NS(last_clean_record=NS(complete=1, finish_reason=52))))
    def read(self, **kw):
        args = dict(ha_version="2026.11.2", library_version="7.12.0",
                    candidates=[self.c], now=self.now)
        args.update(kw)
        return snapshot(**args)
    def test_observation(self):
        d = self.read()
        self.assertEqual(d["status"]["in_cleaning"], 3)
        self.assertEqual(d["record"]["finish_reason"], 52)
        self.assertNotIn("secret", d["status"])
        self.assertFalse(d["usable_for_dispatch"])
        self.assertEqual(d["freshness"], "UNKNOWN")
    def test_versions(self):
        self.assertEqual(self.read(ha_version="other")["diagnostic"], "UNSUPPORTED_VERSION")
        self.assertEqual(self.read(library_version="other")["diagnostic"], "UNSUPPORTED_VERSION")
    def test_binding(self):
        for candidates in ([], [self.c, self.c]):
            self.assertEqual(self.read(candidates=candidates)["diagnostic"], "AMBIGUOUS_OR_MISSING_COORDINATOR")
    def test_missing_trait(self):
        self.c.properties_api.status = None
        self.assertEqual(self.read()["diagnostic"], "UNSUPPORTED_OR_UNAVAILABLE")
    def test_missing_record(self):
        self.c.properties_api.clean_summary.last_clean_record = None
        self.assertIsNone(self.read()["record"]["complete"])
    def test_future_stamp(self):
        self.c._last_update_success_time = self.now + timedelta(seconds=1)
        self.assertIsNone(self.read()["coordinator_last_success"])
    def test_string_rejected(self):
        self.c.properties_api.status.in_cleaning = "private"
        self.assertIsNone(self.read()["status"]["in_cleaning"])
    def test_old_stamp(self):
        self.c._last_update_success_time = self.now - timedelta(days=1)
        self.assertEqual(self.read()["freshness"], "UNKNOWN")

if __name__ == "__main__":
    unittest.main()
