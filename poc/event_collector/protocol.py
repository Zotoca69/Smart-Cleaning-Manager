"""HA WebSocket `subscribe_entities` protocol handling (no I/O).

Reviewed against HA Core 2026.11.2 `websocket_api/commands.py`; see API.md.
Only the subscription request is ever produced here. Anything that is not an
expected message for the exact allowlist is rejected (fail closed).
"""
import json

import config


DIFF_KEYS = frozenset({"+", "-"})


class ProtocolError(ValueError):
    """Unexpected or malformed message; capture must stop as incomplete."""


def build_subscription(ids):
    """Return the single outgoing application message as UTF-8 bytes."""
    ids = config.validate_entity_ids(ids)
    message = {"id": config.SUBSCRIPTION_ID, "type": config.SUBSCRIBE_TYPE, "entity_ids": ids}
    return json.dumps(message, separators=(",", ":")).encode("utf-8")


def parse_handshake(raw, expected_type):
    """Parse an auth handshake message; return the reported HA version or None.

    Handshake messages are never stored (they precede capture and the auth
    message carries the token); only a validated version string is kept.
    """
    try:
        message = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ProtocolError("malformed authentication handshake") from exc
    if not isinstance(message, dict) or message.get("type") != expected_type:
        raise ProtocolError(f"expected {expected_type}")
    version = message.get("ha_version")
    if isinstance(version, str) and config.HA_VERSION_PATTERN.fullmatch(version):
        return version
    return None


def parse_message(raw, ids):
    """Decode and validate one subscription message for the exact allowlist.

    Returns the decoded dict. Raises ProtocolError on anything unexpected,
    including JSON arrays (coalesced messages are never requested).
    """
    try:
        message = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ProtocolError("malformed JSON message") from exc
    if not isinstance(message, dict):
        raise ProtocolError("unexpected message structure")
    if message.get("id") != config.SUBSCRIPTION_ID:
        raise ProtocolError("unexpected message ID")
    kind = message.get("type")
    if kind == "result":
        if message.get("success") is not True:
            raise ProtocolError("subscription rejected")
        return message
    if kind != "event":
        raise ProtocolError("unexpected message type")
    event = message.get("event")
    if not isinstance(event, dict) or not event or set(event) - config.EVENT_KEYS:
        raise ProtocolError("unknown delta schema")
    allowed = set(ids)
    for key, value in event.items():
        if key == "r":
            if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
                raise ProtocolError("invalid removal")
            entities = set(value)
        else:
            if not isinstance(value, dict) or not all(isinstance(v, dict) for v in value.values()):
                raise ProtocolError("invalid delta")
            if key == "c" and any(set(diff) - DIFF_KEYS or not diff for diff in value.values()):
                raise ProtocolError("invalid change diff")
            entities = set(value)
        if entities - allowed:
            raise ProtocolError("unexpected entity")
    return message


def _effective_last_updated(compressed):
    """HA compressed state: `lu` is omitted when equal to `lc`."""
    value = compressed.get("lu", compressed.get("lc"))
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def describe_event(message):
    """Derive reviewer metadata from a validated event; raw bytes stay authoritative.

    Returns dict(added, changed, removed, server_times, unavailable) where
    server_times maps entity -> server last_updated (epoch seconds) if present.
    """
    event = message["event"]
    added = event.get("a", {})
    changed = event.get("c", {})
    removed = list(event.get("r", []))
    server_times, unavailable = {}, []
    for entity_id, state in added.items():
        stamp = _effective_last_updated(state)
        if stamp is not None:
            server_times[entity_id] = stamp
        if state.get("s") in config.UNAVAILABLE_STATES:
            unavailable.append(entity_id)
    for entity_id, diff in changed.items():
        plus = diff.get("+", {}) if isinstance(diff.get("+", {}), dict) else {}
        stamp = _effective_last_updated(plus)
        if stamp is not None:
            server_times[entity_id] = stamp
        if plus.get("s") in config.UNAVAILABLE_STATES:
            unavailable.append(entity_id)
    return {
        "added": sorted(added),
        "changed": sorted(changed),
        "removed": sorted(removed),
        "server_times": server_times,
        "unavailable": sorted(set(unavailable)),
    }
