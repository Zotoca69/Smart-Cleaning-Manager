"""Shared helpers for the POC12C regression tests (synthetic data only)."""
import asyncio
import json
import tempfile
import threading
from pathlib import Path

import config
from collector import capture
from synthetic import SyntheticSocket, change, default_script

IDS = ["vacuum.synthetic_robot", "sensor.synthetic_status"]
URL = "wss://synthetic.invalid/api/websocket"
TOKEN = "synthetic-token-must-never-be-stored"
ACK = {"id": config.SUBSCRIPTION_ID, "type": "result", "success": True, "result": None}


def snapshot(ids=IDS, state="idle"):
    return {"id": 1, "type": "event", "event": {"a": {i: {"s": state, "lc": 1000.0} for i in ids}}}


class Run:
    """Run one synthetic capture in a temporary folder and expose its artefacts."""

    def __init__(self, script, ids=IDS, seconds=1, stop_after=None, fail_at=None, raw_script=False):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "capture"
        messages = script if raw_script else default_script(ids)[:2] + list(script)
        self.socket = SyntheticSocket(messages, fail_at=fail_at)
        self.stop = threading.Event()
        self.exception = None
        self.result = None

        def notify(n):
            if stop_after is not None and n >= stop_after:
                self.stop.set()

        try:
            self.result = asyncio.run(capture(URL, TOKEN, ids, self.path, seconds, self.stop, lambda url: self.socket, notify, synthetic=True))
        except BaseException as exc:  # inspected by the test
            self.exception = exc

    @property
    def manifest(self):
        return json.loads((self.path / config.MANIFEST_FILE).read_text(encoding="utf-8"))

    @property
    def rows(self):
        return [json.loads(line) for line in (self.path / config.MESSAGES_FILE).read_bytes().splitlines()]

    def all_file_bytes(self):
        return b"".join(p.read_bytes() for p in self.path.iterdir())

    def cleanup(self):
        self.tmp.cleanup()


__all__ = ["IDS", "URL", "TOKEN", "ACK", "snapshot", "change", "Run"]
