import unittest
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace as NS
from enum import IntEnum
from snapshot import snapshot

class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
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
        d = self.read()
        self.assertIsNone(d["record"]["complete"])
        self.assertFalse(d["record_present"])
    def test_future_stamp(self):
        self.c._last_update_success_time = self.now + timedelta(seconds=1)
        self.assertIsNone(self.read()["coordinator_last_success"])
    def test_string_rejected(self):
        self.c.properties_api.status.in_cleaning = "private"
        self.assertIsNone(self.read()["status"]["in_cleaning"])
    def test_old_stamp(self):
        self.c._last_update_success_time = self.now - timedelta(days=1)
        d = self.read()
        self.assertEqual(d["freshness"], "UNKNOWN")
        self.assertEqual(d["coordinator_last_success"], self.c._last_update_success_time.isoformat())
        self.assertFalse(d["usable_for_dispatch"])

    def test_enum_fallback(self):
        class Reason(IntEnum):
            INTERRUPT = 21
            FINISHED = 52
            @classmethod
            def _missing_(cls, value):
                return cls.INTERRUPT
        self.c.properties_api.clean_summary.last_clean_record.finish_reason = Reason(999)
        d = self.read()
        self.assertIsNone(d["record"]["finish_reason"])
        self.assertEqual(d["enum_metadata"]["record"]["finish_reason"], {
            "origin": "LIBRARY_NORMALIZED_UNKNOWN_MAY_BE_COERCED",
            "normalized": 21, "ambiguous": True})
        self.c.properties_api.clean_summary.last_clean_record.finish_reason = Reason.FINISHED
        d = self.read()
        self.assertEqual(d["record"]["finish_reason"], 52)
        self.assertFalse(d["enum_metadata"]["record"]["finish_reason"]["ambiguous"])
    def test_unknown_member(self):
        class State(IntEnum):
            active = 1
            unknown = 0
        self.c.properties_api.status.state = State.unknown
        self.assertIsNone(self.read()["status"]["state"])
        self.c.properties_api.status.state = State.active
        self.assertEqual(self.read()["status"]["state"], 1)
    def test_missing_summary(self):
        self.c.properties_api.clean_summary = None
        self.assertEqual(self.read()["diagnostic"], "UNSUPPORTED_OR_UNAVAILABLE")
    def test_naive_times(self):
        d = self.read(now=self.now.replace(tzinfo=None))
        self.assertIsNone(d["observed_at"])
        self.assertIsNone(d["coordinator_last_success"])
        self.c._last_update_success_time = self.now.replace(tzinfo=None)
        self.assertIsNone(self.read()["coordinator_last_success"])
    def test_scalar_types(self):
        self.c.properties_api.status.clean_time = 1.5
        self.c.properties_api.status.clean_area = {"secret": 1}
        self.c.properties_api.clean_summary.last_clean_record.complete = True
        d = self.read()
        self.assertIsNone(d["status"]["clean_time"])
        self.assertIsNone(d["status"]["clean_area"])
        self.assertIs(d["record"]["complete"], True)
    def test_present_empty_record(self):
        self.c.properties_api.clean_summary.last_clean_record = NS()
        d = self.read()
        self.assertTrue(d["record_present"])
        self.assertIsNone(d["record"]["complete"])

if __name__ == "__main__":
    unittest.main()
