"""POC11A/U9: verify python-roborock 7.12.0 enum normalisation against the Evidence Adapter.

Synthetic input only. No network, no Home Assistant, no device.
Usage: python -I poc11a.py <adapter_dir> <out_json>
"""
import importlib.metadata as md
import json
import logging
import sys
from datetime import datetime, timezone
from types import SimpleNamespace as NS

ADAPTER_DIR, OUT = sys.argv[1], sys.argv[2]
sys.path.insert(0, ADAPTER_DIR)

from snapshot import snapshot  # noqa: E402  (repo code under test)
from roborock.data import CleanRecord, CleanSummaryWithDetail, StatusV2  # noqa: E402
from roborock.data.v1.v1_code_mappings import (  # noqa: E402
    RoborockCleanType, RoborockErrorCode, RoborockFinishReason,
    RoborockInCleaning, RoborockStartType, RoborockStateCode)
from roborock.devices.traits.v1.clean_summary import CleanRecordConverter  # noqa: E402
from roborock.devices.traits.v1.common import DefaultConverter  # noqa: E402
from roborock.devices.traits.v1.status import _DPS_CONVERTER  # noqa: E402


class Capture(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


cap = Capture()
rlog = logging.getLogger("roborock")
rlog.addHandler(cap)
rlog.setLevel(logging.DEBUG)
rlog.propagate = False

UNKNOWN_RAW = 987654  # synthetic code that is not a member of any tested enum
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
VERSIONS = dict(ha_version="2026.11.2", library_version="7.12.0")

# (container, field, enum class)
FIELDS = [
    ("status", "state", RoborockStateCode),
    ("status", "error_code", RoborockErrorCode),
    ("status", "in_cleaning", RoborockInCleaning),
    ("record", "finish_reason", RoborockFinishReason),
    ("record", "start_type", RoborockStartType),
    ("record", "clean_type", RoborockCleanType),
]

status_conv = DefaultConverter(StatusV2)
record_conv = CleanRecordConverter()


def library_fallback(cls):
    """What RoborockEnum._missing_ returns, derived independently of the adapter."""
    return cls.unknown if hasattr(cls, "unknown") else next(item for item in cls)


def parse(container, field, raw):
    """Parse through the library's real converters (RPC path)."""
    if container == "status":
        return getattr(status_conv.convert({field: raw}), field)
    return getattr(record_conv.convert({field: raw}), field)


def adapter_view(container, field, value):
    """Run the unchanged adapter on real library objects."""
    status = StatusV2()
    record = CleanRecord()
    setattr(status if container == "status" else record, field, value)
    summary = CleanSummaryWithDetail()  # real class; constructor does not take last_clean_record
    summary.last_clean_record = record
    coord = NS(_last_update_success_time=NOW,
               properties_api=NS(status=status, clean_summary=summary))
    out = snapshot(candidates=[coord], now=NOW, **VERSIONS)
    return {
        "diagnostic": out["diagnostic"],
        "projected": out[container][field],
        "metadata": out["enum_metadata"][container].get(field),
        "usable_for_dispatch": out["usable_for_dispatch"],
        "freshness": out["freshness"],
    }


def describe(v):
    return None if v is None else {"type": type(v).__name__, "member": v.name, "int": int(v)}


results = {"environment": {
    "python": sys.version.split()[0],
    "python_roborock": md.version("python-roborock"),
    "adapter_dir": ADAPTER_DIR,
}, "fields": [], "dps": [], "alias": None, "deviations": []}

for container, field, cls in FIELDS:
    assert UNKNOWN_RAW not in cls._value2member_map_, (cls, UNKNOWN_RAW)
    fb = library_fallback(cls)
    other = next(m for m in cls if m is not fb)
    cap.messages.clear()
    genuine = parse(container, field, int(fb))
    warn_genuine = list(cap.messages)
    cap.messages.clear()
    unknown = parse(container, field, UNKNOWN_RAW)
    warn_unknown = list(cap.messages)
    cap.messages.clear()
    unknown_again = parse(container, field, UNKNOWN_RAW)
    warn_unknown_again = list(cap.messages)
    nonfb = parse(container, field, int(other))
    row = {
        "container": container, "field": field, "enum": cls.__name__,
        "fallback_rule": "unknown" if hasattr(cls, "unknown") else "first member",
        "fallback": describe(fb),
        "genuine_fallback_parsed": describe(genuine),
        "unknown_raw": UNKNOWN_RAW,
        "unknown_parsed": describe(unknown),
        "indistinguishable": genuine is unknown,
        "warning_on_genuine": warn_genuine,
        "warning_on_unknown_first": warn_unknown,
        "warning_on_unknown_repeat": warn_unknown_again,
        "nonfallback_raw": int(other),
        "nonfallback_parsed": describe(nonfb),
        "adapter_genuine_fallback": adapter_view(container, field, genuine),
        "adapter_unknown": adapter_view(container, field, unknown),
        "adapter_nonfallback": adapter_view(container, field, nonfb),
    }
    ok = (row["indistinguishable"]
          and row["adapter_genuine_fallback"]["projected"] is None
          and row["adapter_unknown"]["projected"] is None
          and row["adapter_unknown"]["metadata"]["ambiguous"] is True
          and row["adapter_unknown"]["metadata"]["normalized"] == int(fb)
          and row["adapter_nonfallback"]["projected"] == int(other)
          and row["adapter_nonfallback"]["metadata"]["ambiguous"] is False
          and all(row[k]["usable_for_dispatch"] is False and row[k]["freshness"] == "UNKNOWN"
                  for k in ("adapter_genuine_fallback", "adapter_unknown", "adapter_nonfallback")))
    row["pass"] = ok
    if not ok:
        results["deviations"].append(f"{field}: expectation not met")
    results["fields"].append(row)

# DPS push path (StatusV2 fields carrying dps metadata).
for dps_id, field in _DPS_CONVERTER._dps_field_map.items():
    if field not in ("state", "error_code", "in_cleaning"):
        continue
    target = StatusV2()
    _DPS_CONVERTER.update_from_dps(target, {dps_id: UNKNOWN_RAW})
    v = getattr(target, field)
    cls = dict((f, c) for _, f, c in FIELDS)[field]
    results["dps"].append({"field": field, "dps_id": int(dps_id), "unknown_parsed": describe(v),
                           "equals_fallback": v is library_fallback(cls)})

# Alias check: manual_interrupt_2 shares value 21 with the first member.
a = parse("record", "finish_reason", 21)
results["alias"] = {"raw": 21, "parsed": describe(a),
                    "alias_manual_interrupt_2_is_same_member":
                        RoborockFinishReason.manual_interrupt_2 is RoborockFinishReason.manual_interrupt,
                    "adapter": adapter_view("record", "finish_reason", a)}

# HA vacuum.py L239 compares in_cleaning == 4; check what 4 becomes.
c4 = parse("status", "in_cleaning", 4)
results["in_cleaning_4"] = {"parsed": describe(c4), "equals_4": c4 == 4}

with open(OUT, "w") as fh:
    json.dump(results, fh, indent=2, default=str)

print(f"python {results['environment']['python']}, python-roborock {results['environment']['python_roborock']}")
for r in results["fields"]:
    print(f"{r['field']:14} fallback={r['fallback']['member']}({r['fallback']['int']}) "
          f"[{r['fallback_rule']}]  genuine->{r['genuine_fallback_parsed']['int']}  "
          f"{UNKNOWN_RAW}->{r['unknown_parsed']['int']}  same={r['indistinguishable']}  "
          f"adapter: genuine={r['adapter_genuine_fallback']['projected']} "
          f"unknown={r['adapter_unknown']['projected']} "
          f"(meta {r['adapter_unknown']['metadata']['normalized']}, amb={r['adapter_unknown']['metadata']['ambiguous']}) "
          f"nonfb {r['nonfallback_raw']}->{r['adapter_nonfallback']['projected']}  "
          f"warn_unknown={len(r['warning_on_unknown_first'])}/{len(r['warning_on_unknown_repeat'])} "
          f"warn_genuine={len(r['warning_on_genuine'])}  {'PASS' if r['pass'] else 'FAIL'}")
print("DPS:", results["dps"])
print("alias:", results["alias"]["parsed"], "same member:",
      results["alias"]["alias_manual_interrupt_2_is_same_member"],
      "adapter projected:", results["alias"]["adapter"]["projected"])
print("in_cleaning=4 ->", results["in_cleaning_4"])
print("deviations:", results["deviations"] or "none")
