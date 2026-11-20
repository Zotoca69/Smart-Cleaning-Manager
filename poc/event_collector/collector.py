"""Bounded, scoped HA WebSocket evidence capture (POC12C, offline review candidate).

Only two application messages are ever sent: the auth message (never stored)
and one `subscribe_entities` request for an exact allowlist. There is no code
path that sends service calls, events or other commands.

Live use against Home Assistant is NOT approved. The GUI uses the synthetic
transport only; `live_connect` exists solely so reviewers can inspect the
exact transport settings that a later, separately approved run would use.
"""
import asyncio
import json
import os
import time

import config
import protocol
from provenance import runtime_provenance
from storage import EvidenceStore


def live_connect(url):
    """websockets client with fixed, reviewable settings (no proxy, no compression)."""
    from websockets.asyncio.client import connect

    return connect(
        url,
        max_size=config.MAX_MESSAGE_BYTES,
        open_timeout=config.OPEN_TIMEOUT_S,
        close_timeout=config.CLOSE_TIMEOUT_S,
        proxy=None,
        compression=None,
    )


async def _recv(ws, timeout, **kwargs):
    return await asyncio.wait_for(ws.recv(**kwargs), timeout)


async def capture(url, token, ids, path, seconds, stop, connect_fn, notify=lambda n: None,
                  synthetic=False, platform=os.name, runner=None):
    """Capture subscription messages into a new private folder; return the manifest.

    Protocol violations raise after the capture is marked incomplete. An
    observed removal of an allowlisted entity ends the capture as incomplete
    (observation gap) without raising. `connect_fn` must be supplied explicitly.
    """
    config.validate_url(url)
    ids = config.validate_entity_ids(ids)
    seconds = config.validate_duration(seconds)
    if connect_fn is None:
        raise ValueError("transport must be supplied explicitly")
    request = protocol.build_subscription(ids)
    store_kwargs = {"platform": platform} if runner is None else {"platform": platform, "runner": runner}
    store = EvidenceStore(path, ids, runtime_provenance(url, synthetic), **store_kwargs)
    ack = initial = False
    last_server_time = {}
    try:
        async with connect_fn(url) as ws:
            version = protocol.parse_handshake(await _recv(ws, config.HANDSHAKE_TIMEOUT_S), "auth_required")
            await ws.send(json.dumps({"type": "auth", "access_token": token}))
            raw_auth = await _recv(ws, config.HANDSHAKE_TIMEOUT_S)
            try:
                version = protocol.parse_handshake(raw_auth, "auth_ok") or version
            except protocol.ProtocolError:
                raise protocol.ProtocolError("authentication rejected") from None
            store.meta["provenance"]["ha_version"] = version
            store.record("send", request)
            await ws.send(request.decode("utf-8"))
            deadline = time.monotonic() + seconds
            while not stop.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    raw = await _recv(ws, min(config.RECEIVE_POLL_S, remaining), decode=False)
                except asyncio.TimeoutError:
                    continue
                message = protocol.parse_message(raw, ids)
                derived = protocol.describe_event(message) if message["type"] == "event" else None
                store.record("receive", raw, derived)
                notify(store.meta["messages"])
                if message["type"] == "result":
                    if ack:
                        raise protocol.ProtocolError("duplicate acknowledgement")
                    ack = True
                    continue
                if not ack:
                    raise protocol.ProtocolError("event before acknowledgement")
                if not initial:
                    if set(message["event"]) != {"a"} or set(message["event"]["a"]) != set(ids):
                        raise protocol.ProtocolError("incomplete initial snapshot")
                    initial = True
                if derived["unavailable"]:
                    store.flag("unavailable_or_unknown", derived["unavailable"])
                for entity_id, stamp in derived["server_times"].items():
                    if entity_id in last_server_time and stamp < last_server_time[entity_id]:
                        store.flag("out_of_order_server_time")
                    last_server_time[entity_id] = max(stamp, last_server_time.get(entity_id, stamp))
                if derived["removed"]:
                    store.flag("removed_entities", derived["removed"])
                    store.finish(False, "observation gap: allowlisted entity removed", "gap")
                    return dict(store.meta)
            ended_by = "operator" if stop.is_set() else "deadline"
            if ack and initial:
                store.finish(True, "bounded observation ended", ended_by)
            else:
                store.finish(False, "missing acknowledgement or initial snapshot", ended_by)
            return dict(store.meta)
    except BaseException as exc:
        detail = str(exc) if isinstance(exc, (protocol.ProtocolError, ValueError)) else ""
        store.finish(False, f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__, "error")
        raise
    finally:
        store.close()
