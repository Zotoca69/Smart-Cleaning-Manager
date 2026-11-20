import json
import unittest

import config
import protocol
from _testsupport import IDS, snapshot


class ConfigValidationTests(unittest.TestCase):
    def test_entity_ids(self):
        self.assertEqual(config.validate_entity_ids(IDS), IDS)
        for bad in ([], ["*"], ["sensor.*"], ["Sensor.x"], ["sensor"], ["a.b", "a.b"], ["sensor.x "], [1],
                    [f"sensor.s{i}" for i in range(config.MAX_ENTITIES + 1)]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                config.validate_entity_ids(bad)

    def test_duration(self):
        self.assertEqual(config.validate_duration("10"), 10)
        self.assertEqual(config.validate_duration(config.MAX_DURATION_S), config.MAX_DURATION_S)
        for bad in (0, config.MAX_DURATION_S + 1, "1.5", "", "abc", True, None, 2.0):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                config.validate_duration(bad)

    def test_url(self):
        config.validate_url("wss://synthetic.invalid/api/websocket")
        for bad in ("ws://synthetic.invalid/api/websocket", "https://x", "", None):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                config.validate_url(bad)


class ProtocolTests(unittest.TestCase):
    def test_subscription_is_exact_and_scoped(self):
        raw = protocol.build_subscription(IDS)
        self.assertEqual(json.loads(raw), {"id": 1, "type": "subscribe_entities", "entity_ids": IDS})
        with self.assertRaises(ValueError):
            protocol.build_subscription([])  # empty list would mean "all entities" in HA

    def test_valid_messages(self):
        protocol.parse_message(json.dumps({"id": 1, "type": "result", "success": True}), IDS)
        protocol.parse_message(json.dumps(snapshot()), IDS)
        protocol.parse_message(json.dumps({"id": 1, "type": "event", "event": {"c": {IDS[0]: {"+": {"s": "x"}, "-": {"a": ["k"]}}}}}), IDS)
        protocol.parse_message(json.dumps({"id": 1, "type": "event", "event": {"r": [IDS[0]]}}), IDS)

    def test_rejected_messages(self):
        bad = [
            b"{", b"[]", b'"text"', b"null",
            json.dumps([snapshot()]),  # coalesced array never requested
            json.dumps({"id": 2, "type": "event", "event": {"a": {}}}),
            json.dumps({"type": "event", "event": {"a": {}}}),
            json.dumps({"id": 1, "type": "result", "success": False}),
            json.dumps({"id": 1, "type": "pong"}),
            json.dumps({"id": 1, "type": "event"}),
            json.dumps({"id": 1, "type": "event", "event": {}}),
            json.dumps({"id": 1, "type": "event", "event": {"x": {}}}),
            json.dumps({"id": 1, "type": "event", "event": {"a": {"sensor.other": {"s": "on"}}}}),
            json.dumps({"id": 1, "type": "event", "event": {"c": {"sensor.other": {"+": {}}}}}),
            json.dumps({"id": 1, "type": "event", "event": {"r": ["sensor.other"]}}),
            json.dumps({"id": 1, "type": "event", "event": {"r": "vacuum.synthetic_robot"}}),
            json.dumps({"id": 1, "type": "event", "event": {"a": {IDS[0]: "on"}}}),
            json.dumps({"id": 1, "type": "event", "event": {"c": {IDS[0]: {"s": "on"}}}}),
            json.dumps({"id": 1, "type": "event", "event": {"c": {IDS[0]: {}}}}),
        ]
        for raw in bad:
            with self.subTest(raw=raw), self.assertRaises(protocol.ProtocolError):
                protocol.parse_message(raw, IDS)

    def test_handshake(self):
        self.assertEqual(protocol.parse_handshake('{"type":"auth_required","ha_version":"2026.11.2"}', "auth_required"), "2026.11.2")
        self.assertIsNone(protocol.parse_handshake('{"type":"auth_ok","ha_version":"<bad version!>"}', "auth_ok"))
        for raw in ('{"type":"auth_invalid"}', "{", "[]"):
            with self.assertRaises(protocol.ProtocolError):
                protocol.parse_handshake(raw, "auth_ok")

    def test_describe_event(self):
        message = {"id": 1, "type": "event", "event": {
            "a": {IDS[0]: {"s": "unavailable", "lc": 10.0, "lu": 12.5}},
            "c": {IDS[1]: {"+": {"s": "unknown", "lc": 11.0}}},
            "r": []}}
        info = protocol.describe_event(message)
        self.assertEqual(info["server_times"], {IDS[0]: 12.5, IDS[1]: 11.0})
        self.assertEqual(info["unavailable"], sorted(IDS))


if __name__ == "__main__":
    unittest.main()
