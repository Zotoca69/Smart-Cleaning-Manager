# POC report
| Test | Evidence/status |
|---|---|
| 01 | Matter inventory: 7 entities. |
| 02 | Official integration: 44 entities; exposure does not guarantee function. |
| 03 | Map segment IDs retrieved; app order differs from API IDs. |
| 04 | Ordinary service commands inconsistent/rejected. |
| 04B | Combined command and tested Custom transition verified. |
| 04C | Partial parameter mapping. |
| 04D | Selected room vacuum/mop, app confirmed, docked without reported error; physical suction/water flow not measured. |
| 05 | Maintenance entities identified; alerts untested. |
| 06A–C | Multi-room start, pause, resume preserving progress verified. |
| 06D | Abort/dock verified, progress reset; app records user abort. Room completion inferred, not authoritative. |
| 06E | Start after dock entered preparation at zero progress; aborted before scope established. |
| 06F | Explicit remaining segments selected, app plan excludes previously cleaned segment; aborted at user request; returning verified, final dock and cleaning outcome not verified. |
Next: history/abort/completed-segment API, persistence across restart, alert tests, presence and interactive notification tests, engine POCs, installed versions and firmware regression. Private room maps, names, times and occupancy details omitted.

## POC 07 — inventory observation (2026-11-20, #3)
ChatGPT executed read-only native Roborock get_maps via HA service interface. Response contained one map entry with flag, name and dictionary of segment ID/name pairs. Private values omitted; approved baseline retained privately. This is an implementer-reported observation, not independently verified raw evidence. No cleaning command. Does not establish active map identity, freshness, inactive-map inventory completeness, geometry or historical ID stability.

## POC10A–F — source investigation and offline spike
HA 2026.11.2 core Roborock coordinator exposes internal status and clean summary traits; cached data can be returned on suppressed refresh failure. vacuum.send_command does not return RPC payload. python-roborock 7.12.0 provides optional complete/finish_reason in CleanRecord; no explicit active task ID identified in StatusV2. Source findings recorded in #3 comments 7040450724 and 7040500257. Offline spike in poc/evidence_adapter projects allowlisted scalar data from synthetic coordinator objects; freshness always UNKNOWN and dispatch always forbidden. No runtime binding, record ID, field population or actual device semantics proven. Tests are synthetic; deployment separate.

Claude review d1e6734: unknown enum codes may be silently coerced to unknown or first member; raw codes cannot be recovered after parsing. Correction marks library-normalized provenance and masks possible fallback values; diagnostics retain normalized value only. records[0] exists but is not projected because separate awaited record retrieval can yield inconsistent ID/content. No runtime evidence established.

### Field-specific limitations (U8)
For python-roborock 7.12.0, the conservative enum projection masks these possible fallback values even when the underlying code was genuine. Normalized values remain in ambiguous diagnostic metadata, not in interpretable fields.

| Field | Masked value | Ordinary meaning / limitation |
|---|---:|---|
| in_cleaning | 0 | No cleaning in progress; cannot establish termination from this value. |
| error_code | 0 | No error; cannot establish absence of errors. |
| finish_reason | 21 | Manual interruption (including alias manual_interrupt_2); cannot establish manual abort. |
| start_type | 1 | Button start; cannot establish start source. |
| clean_type | 1 | Whole-area cleaning; cannot establish cleaning type. |
| state | 0 | Unknown status. |

Other interruption codes (29, 35–37) are not these fallback values. Raw integer fields complete, error and in_returning are not affected by enum fallback masking when supplied as integers. None of these observations alone establishes task identity, termination, completion or freshness. Source: Claude follow-up review of e1e388f, PR #6 comment 7040828568; python-roborock v7.12.0 enum implementation. Actual field population remains unverified. Reliable raw-code access or equivalent independently verified evidence is an implementation gate before relying on affected values. U9: next POC shall test actual pinned python-roborock classes in isolation (including unknown-code coercion and genuine fallback codes) before live bridge; no runtime verification claimed here.

## POC11A–D — library evidence and remaining gates
Claude executed U9 using Python 3.13.18 and python-roborock 7.12.0, synthetic input only, adapter main e74b1cc. Source report and script: https://github.com/Zotoca69/Smart-Cleaning-Manager/issues/3#issuecomment-7041058843. Wheel SHA256 a63f35cda13c9f95724c22b8337617ec58e0f3ae04c00befe79981530a45cdaf (reported). Preserved script: poc/evidence_adapter/poc11a.py. Reported 14/14 unit tests and six field checks passed. For state/error_code/in_cleaning fallback 0, finish_reason 21, start_type/clean_type 1: genuine and synthetic unknown 987654 become identical enum members; adapter masks both and preserves ambiguous metadata. Nonfallback sample per field preserved. DPS unknown conversion observed for state/error_code, not in_cleaning (no DPS mapping). Warning observed once per unknown code/process; not suitable for correlation. All observations remain freshness UNKNOWN and dispatch forbidden per report.

### Independent assessment of Claude evidence (ChatGPT)
Static review of published script, reported outputs and unchanged adapter: field checks compare actual library converters, genuine fallback, unknown and one other member; synthetic coordinator correctly limits scope. No contradiction found in six reported passes. U9 executed for bounded converter semantics, not full runtime. No independent rerun by ChatGPT; reported installed hashes and results not independently reproduced. Script prints failures but does not exit nonzero on deviations; DPS and alias checks are observational rather than asserted; diagnostic and metadata origin not asserted, HA version supplied as fixture, actual environment package version printed not enforced. Reproduction must inspect results/deviations, not exit code alone. Preserve original script as evidence rather than silently alter it. Future automated regression harness must assert these conditions and pin/check dependencies. Reported output JSON not supplied; do not claim it is archived. No private runtime evidence.

POC11B: v7.12.0 V1TraitMixin.refresh receives RPC response before converter; DPS update_from_dps receives decoded values before convert_dict. No supported stable raw observer identified; avoid internal hooks and separate client by default. POC11C: clean summary ID updated before awaited record retrieval; mismatch may persist on failure; aggregate records further limit interpretation. Cached coordinator data and timestamp do not prove atomicity/freshness. POC11D: prioritize existing integration and independently verified lifecycle evidence; upstream narrow raw/validity/correlation interface only if necessary. Entailed raw-code ambiguity cannot be reversed from normalized enum. Do not weaken approved validation gates.

External risk ER11: in_cleaning raw 4 normalizes to 0 per Claude; HA 2026.11.2 vacuum.py async_start branch comparing ==4 may be unreachable via tested conversion path, potentially falling through to generic APP_START depending on other state. Not verified on device or running HA. No generic start on unknown retained task. No upstream fix in scope. Sources: https://github.com/home-assistant/core/blob/2026.11.2/homeassistant/components/roborock/vacuum.py ; https://github.com/Python-roborock/python-roborock/blob/v7.12.0/roborock/devices/traits/v1/clean_summary.py ; https://github.com/Python-roborock/python-roborock/blob/v7.12.0/roborock/devices/traits/v1/common.py ; https://github.com/Python-roborock/python-roborock/blob/v7.12.0/roborock/devices/traits/common.py .

U9 executed (Claude); runtime and physical gates still open. See docs/poc/POC11_VERIFICATION.md for planned scenarios, none executed. #3 remains open.
