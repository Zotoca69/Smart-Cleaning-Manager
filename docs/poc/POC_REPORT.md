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
