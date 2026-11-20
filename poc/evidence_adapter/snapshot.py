"""Offline prototype; no HA imports, network or commands."""
from datetime import datetime, timezone
from enum import Enum

STATUS_FIELDS = ("state", "in_cleaning", "in_returning", "clean_time",
                 "clean_area", "clean_percent", "error_code", "msg_seq")
RECORD_FIELDS = ("begin", "end", "duration", "area", "complete",
                 "finish_reason", "error", "start_type", "clean_type", "map_flag")

def scalar(value):
    if isinstance(value, Enum):
        value = value.value
    if type(value) in (int, bool) or value is None:
        return value
    # No arbitrary strings, identifiers, objects or nested payloads.
    return None

def fields(obj, names):
    return {name: scalar(getattr(obj, name, None)) for name in names}

def snapshot(*, ha_version, library_version, candidates, now):
    """Caller must supply uniquely bound native V1 coordinator candidates.
    Never authorizes dispatch: cached mutable traits cannot prove freshness.
    """
    result = {"usable_for_dispatch": False, "freshness": "UNKNOWN"}
    if (ha_version, library_version) != ("2026.11.2", "7.12.0"):
        return dict(result, diagnostic="UNSUPPORTED_VERSION")
    if len(candidates) != 1:
        return dict(result, diagnostic="AMBIGUOUS_OR_MISSING_COORDINATOR")
    try:
        coord = candidates[0]
        api = coord.properties_api
        status = api.status
        summary = api.clean_summary
        if status is None or summary is None:
            raise ValueError("missing trait")
        before = coord._last_update_success_time
        data = fields(status, STATUS_FIELDS)
        record = fields(summary.last_clean_record, RECORD_FIELDS)
        after = coord._last_update_success_time
        if before != after:
            return dict(result, diagnostic="UPDATE_CHANGED")
        stamp = None
        if isinstance(after, datetime) and after.tzinfo is not None:
            if now.tzinfo is not None and after <= now:
                stamp = after.astimezone(timezone.utc).isoformat()
        return dict(result, diagnostic="OBSERVATION_ONLY", status=data,
                    record=record, coordinator_last_success=stamp,
                    observed_at=now.astimezone(timezone.utc).isoformat()
                    if now.tzinfo is not None else None)
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return dict(result, diagnostic="UNSUPPORTED_OR_UNAVAILABLE")
