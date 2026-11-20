"""Shared limits, protocol constants and input validation for the POC12C collector.

All tunable values live here so that collector, storage, export and GUI apply
the same rules. No HA address, token or household identifier belongs here.
"""
import re

SCHEMA_VERSION = "poc12c-evidence-2"

# Capture bounds
MIN_DURATION_S = 1
MAX_DURATION_S = 900
MAX_ENTITIES = 100
MAX_MESSAGE_BYTES = 1_000_000
MAX_CAPTURE_BYTES = 10_000_000

# Timeouts (seconds)
OPEN_TIMEOUT_S = 10
HANDSHAKE_TIMEOUT_S = 10
CLOSE_TIMEOUT_S = 3
RECEIVE_POLL_S = 0.25

# Protocol
SUBSCRIPTION_ID = 1
SUBSCRIBE_TYPE = "subscribe_entities"
REQUIRED_URL_SCHEME = "wss://"
EVENT_KEYS = frozenset({"a", "c", "r"})
UNAVAILABLE_STATES = frozenset({"unavailable", "unknown"})

ENTITY_ID_PATTERN = re.compile(r"[a-z0-9_]+\.[a-z0-9_]+")
HA_VERSION_PATTERN = re.compile(r"[0-9A-Za-z.+_-]{1,40}")

# File names inside a capture folder
MESSAGES_FILE = "messages.jsonl"
MANIFEST_FILE = "manifest.json"


def validate_entity_ids(ids):
    """Return a list of exact, unique, well-formed entity IDs or raise ValueError.

    An empty list is rejected because HA then applies no entity filter at all.
    """
    ids = list(ids)
    if not ids:
        raise ValueError("at least one exact entity ID required")
    if len(ids) > MAX_ENTITIES:
        raise ValueError(f"at most {MAX_ENTITIES} entity IDs allowed")
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate entity IDs")
    for entity_id in ids:
        if not isinstance(entity_id, str) or not ENTITY_ID_PATTERN.fullmatch(entity_id):
            raise ValueError("exact lowercase entity IDs required (no wildcards)")
    return ids


def validate_duration(seconds):
    """Return an integer duration within bounds or raise ValueError."""
    if isinstance(seconds, int) and not isinstance(seconds, bool):
        value = seconds
    elif isinstance(seconds, str) and seconds.strip().isdigit():
        value = int(seconds.strip())
    else:
        raise ValueError("duration must be an integer")
    if not MIN_DURATION_S <= value <= MAX_DURATION_S:
        raise ValueError(f"duration must be {MIN_DURATION_S}–{MAX_DURATION_S} seconds")
    return value


def validate_url(url):
    """Require an encrypted WebSocket URL; local non-TLS use is an open owner decision."""
    if not isinstance(url, str) or not url.startswith(REQUIRED_URL_SCHEME):
        raise ValueError("TLS WebSocket URL (wss://) required")
    return url
