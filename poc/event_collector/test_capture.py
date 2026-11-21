import asyncio
import base64
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import collector
import protocol
from _testsupport import ACK, IDS, TOKEN, URL, Run, change, snapshot
from synthetic import SyntheticSocket, default_script


class CaptureTests(unittest.TestCase):
    def run_case(self, script, **kwargs):
        run = Run(script, **kwargs)
        self.addCleanup(run.cleanup)
        return run

    def assert_no_secret_and_only_allowed_sends(self, run):
        self.assertNotIn(TOKEN.encode(), run.all_file_bytes())
        sent = [json.loads(m) for m in run.socket.sent]
        self.assertLessEqual(len(sent), 2)
        if sent:
            self.assertEqual(sent[0], {"type": "auth", "access_token": TOKEN})
        if len(sent) == 2:
            self.assertEqual(sent[1], {"id": 1, "type": "subscribe_entities", "entity_ids": IDS})

    # --- positive path, byte fidelity, provenance -------------------------
    def test_complete_capture_byte_fidelity_and_provenance(self):
        delta = json.dumps(change(IDS[0], "cleaning", 1001.0), separators=(",", ":")) + "   "  # odd whitespace kept
        run = self.run_case([ACK, snapshot(), delta.encode()], stop_after=4)
        self.assertIsNone(run.exception)
        m = run.manifest
        self.assertTrue(m["complete"])
        self.assertEqual((m["status"], m["ended_by"], m["messages"]), ("complete", "operator", 4))
        self.assertEqual(m["provenance"]["ha_version"], "0.0.0-synthetic")
        self.assertTrue(m["provenance"]["synthetic"])
        self.assertEqual(m["allowlist"], IDS)
        self.assertEqual((m["freshness"], m["device_truth"]), ("UNKNOWN", "NOT_ESTABLISHED"))
        rows = run.rows
        self.assertEqual([r["direction"] for r in rows], ["send", "receive", "receive", "receive"])
        self.assertEqual(base64.b64decode(rows[0]["payload_b64"]), run.socket.sent[1].encode())
        self.assertEqual(base64.b64decode(rows[3]["payload_b64"]), delta.encode())
        self.assertEqual(rows[3]["derived"]["server_times"], {IDS[0]: 1001.0})
        self.assertEqual(len({r["session_id"] for r in rows}), 1)
        self.assertEqual(m["session_id"], rows[0]["session_id"])
        self.assert_no_secret_and_only_allowed_sends(run)

    def test_deadline_end(self):
        run = self.run_case([ACK, snapshot()])
        self.assertIsNone(run.exception)
        self.assertEqual((run.manifest["complete"], run.manifest["ended_by"]), (True, "deadline"))

    # --- fail-closed protocol violations ----------------------------------
    def test_protocol_violations_are_incomplete_and_not_stored(self):
        cases = {
            "malformed": [ACK, b"{"],
            "duplicate_ack": [ACK, ACK],
            "event_before_ack": [snapshot()],
            "incomplete_snapshot": [ACK, snapshot(IDS[:1])],
            "snapshot_with_change": [ACK, {"id": 1, "type": "event", "event": {"a": snapshot()["event"]["a"], "c": {}}}],
            "unexpected_entity": [ACK, snapshot(), {"id": 1, "type": "event", "event": {"c": {"sensor.other": {"+": {"s": "x"}}}}}],
            "coalesced_array": [ACK, json.dumps([snapshot()]).encode()],
            "wrong_id": [ACK, {"id": 7, "type": "event", "event": {"a": {}}}],
            "rejected_subscription": [{"id": 1, "type": "result", "success": False, "error": {"code": "x"}}],
        }
        for name, script in cases.items():
            with self.subTest(name):
                run = self.run_case(script)
                self.assertIsInstance(run.exception, protocol.ProtocolError)
                m = run.manifest
                self.assertFalse(m["complete"])
                self.assertEqual((m["status"], m["ended_by"]), ("incomplete", "error"))
                self.assertIn("ProtocolError", m["reason"])
                if name == "unexpected_entity":
                    self.assertNotIn(b"sensor.other", run.all_file_bytes())
                self.assert_no_secret_and_only_allowed_sends(run)

    def test_authentication_rejected(self):
        run = self.run_case([{"type": "auth_required"}, {"type": "auth_invalid", "message": "x"}], raw_script=True)
        self.assertIsInstance(run.exception, protocol.ProtocolError)
        self.assertEqual(run.manifest["messages"], 0)
        self.assertIn("authentication rejected", run.manifest["reason"])
        self.assert_no_secret_and_only_allowed_sends(run)

    def test_unexpected_handshake(self):
        run = self.run_case([{"type": "event"}], raw_script=True)
        self.assertIsInstance(run.exception, protocol.ProtocolError)
        self.assertEqual(run.socket.sent, [])

    # --- observation gaps and visible flags --------------------------------
    def test_removal_is_visible_gap(self):
        run = self.run_case([ACK, snapshot(), {"id": 1, "type": "event", "event": {"r": [IDS[1]]}}])
        self.assertIsNone(run.exception)
        m = run.manifest
        self.assertFalse(m["complete"])
        self.assertEqual(m["ended_by"], "gap")
        self.assertIn("observation gap", m["reason"])
        self.assertEqual(m["flags"]["removed_entities"], [IDS[1]])
        self.assertEqual(m["messages"], 4)  # the removal message itself is preserved

    def test_duplicate_out_of_order_and_unavailable_are_flagged_not_dropped(self):
        late = change(IDS[0], "unavailable", 1005.0)
        early = change(IDS[0], "idle", 1002.0)
        run = self.run_case([ACK, snapshot(), late, late, early], stop_after=6)
        self.assertIsNone(run.exception)
        m = run.manifest
        self.assertTrue(m["complete"])
        self.assertEqual(m["messages"], 6)
        self.assertEqual(m["flags"]["duplicate_payloads"], 1)
        self.assertEqual(m["flags"]["out_of_order_server_time"], 1)
        self.assertEqual(m["flags"]["unavailable_or_unknown"], [IDS[0]])
        self.assertTrue(run.rows[4]["duplicate_of_earlier_payload"])

    def test_missing_ack_or_snapshot(self):
        for script, stop_after in (([], None), ([ACK], None), ([ACK], 2)):
            with self.subTest(script=script, stop_after=stop_after):
                run = self.run_case(script, stop_after=stop_after)
                self.assertIsNone(run.exception)
                self.assertFalse(run.manifest["complete"])
                self.assertIn("missing acknowledgement", run.manifest["reason"])

    def test_operator_stop_before_start(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        stop = threading.Event()
        stop.set()
        socket = SyntheticSocket(default_script(IDS))
        result = asyncio.run(collector.capture(URL, TOKEN, IDS, Path(tmp.name) / "c", 1, stop, lambda url: socket))
        self.assertFalse(result["complete"])
        self.assertEqual(result["ended_by"], "operator")

    def test_disconnect_mid_capture(self):
        run = self.run_case([ACK, snapshot()], fail_at=5)
        self.assertIsInstance(run.exception, ConnectionError)
        m = run.manifest
        self.assertFalse(m["complete"])
        self.assertEqual(m["reason"], "ConnectionError")
        self.assertEqual(m["messages"], 3)

    def test_size_limit(self):
        with mock.patch("config.MAX_CAPTURE_BYTES", 150):
            run = self.run_case([ACK, snapshot()])
        self.assertIsInstance(run.exception, ValueError)
        self.assertIn("size limit", run.manifest["reason"])
        self.assertFalse(run.manifest["complete"])

    # --- input guards and transport settings -------------------------------
    def test_input_guards_before_any_storage(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        target = Path(tmp.name) / "c"
        connect = lambda url: self.fail("must not connect")
        for url, ids, seconds, fn in (("http://synthetic.invalid", IDS, 1, connect), (URL, [], 1, connect),
                                      (URL, IDS, 0, connect), (URL, IDS, 901, connect), (URL, IDS, 1, None)):
            with self.subTest(url=url, ids=ids, seconds=seconds), self.assertRaises(ValueError):
                asyncio.run(collector.capture(url, TOKEN, ids, target, seconds, threading.Event(), fn))
            self.assertFalse(target.exists())

    def test_live_transport_settings(self):
        with mock.patch("websockets.asyncio.client.connect") as connect:
            collector.live_connect(URL)
        kwargs = connect.call_args.kwargs
        self.assertIsNone(kwargs["proxy"])
        self.assertIsNone(kwargs["compression"])
        self.assertEqual(kwargs["max_size"], collector.config.MAX_MESSAGE_BYTES)

    def test_no_write_command_path_in_sources(self):
        """Static guard: only auth and subscribe_entities are ever constructed."""
        here = Path(__file__).resolve().parent
        for name in ("collector.py", "protocol.py", "app.py", "storage.py", "export.py"):
            text = (here / name).read_text(encoding="utf-8")
            for forbidden in ("call_service", "fire_event", "subscribe_events", "get_states", "execute_script", "\"type\": \"call"):
                self.assertNotIn(forbidden, text, f"{forbidden} found in {name}")


if __name__ == "__main__":
    unittest.main()
