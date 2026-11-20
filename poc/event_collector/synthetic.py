"""In-process synthetic transport (no network). Used by the GUI demo and tests."""
import asyncio
import json

import config

SYNTHETIC_HA_VERSION = "0.0.0-synthetic"


def default_script(ids, changes=None):
    """Handshake, acknowledgement, initial snapshot and optional change deltas."""
    script = [
        {"type": "auth_required", "ha_version": SYNTHETIC_HA_VERSION},
        {"type": "auth_ok", "ha_version": SYNTHETIC_HA_VERSION},
        {"id": config.SUBSCRIPTION_ID, "type": "result", "success": True, "result": None},
        {"id": config.SUBSCRIPTION_ID, "type": "event",
         "event": {"a": {i: {"s": "idle", "a": {}, "c": "synthetic", "lc": 1000.0} for i in ids}}},
    ]
    return script + list(changes or [])


def change(entity_id, state, stamp):
    return {"id": config.SUBSCRIPTION_ID, "type": "event",
            "event": {"c": {entity_id: {"+": {"s": state, "lc": stamp}}}}}


class SyntheticSocket:
    """Async context manager mimicking the websockets client interface used by capture()."""

    def __init__(self, script, idle_delay=0.05, repeat=None, fail_at=None):
        self._script = [m if isinstance(m, (bytes, str)) else json.dumps(m, separators=(",", ":")) for m in script]
        self._index = 0
        self._idle_delay = idle_delay
        self._repeat = repeat  # callable(n) -> message for endless synthetic changes
        self._fail_at = fail_at
        self.sent = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def send(self, message):
        self.sent.append(message)

    async def recv(self, decode=None):
        self._index += 1
        if self._fail_at is not None and self._index >= self._fail_at:
            raise ConnectionError("synthetic disconnect")
        if self._index <= len(self._script):
            item = self._script[self._index - 1]
        elif self._repeat is not None:
            await asyncio.sleep(self._idle_delay)
            item = json.dumps(self._repeat(self._index), separators=(",", ":"))
        else:
            await asyncio.sleep(3600)
            raise ConnectionError("synthetic idle")
        if decode is False:
            return item if isinstance(item, bytes) else item.encode("utf-8")
        return item.decode("utf-8") if isinstance(item, bytes) else item


def demo_connect_factory(ids):
    """Connect function for the GUI demo: endless synthetic changes for the first entity."""
    def repeat(n):
        return change(ids[0], "cleaning" if n % 2 else "idle", 1000.0 + n)

    def connect(url):
        return SyntheticSocket(default_script(ids), idle_delay=0.2, repeat=repeat)
    return connect
