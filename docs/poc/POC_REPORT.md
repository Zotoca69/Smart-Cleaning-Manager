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
