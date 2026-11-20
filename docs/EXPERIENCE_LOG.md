# Experience log — 2026-11-15
Anonymized from a private POC record. HA Green, Saros 20 Sonic, official Roborock and Matter integrations. Firmware/library versions unknown. Links below refer to [POC report](poc/POC_REPORT.md) and [device profile](poc/SAROS_20_SONIC.md). A report reference is not independent verification of raw evidence. Entries without a matching test remain unverified for this review.

| ID | Reported observation / evidence reference | Design implication or hypothesis |
|---|---|---|
| ER01 | 04B: combined motor command accepted and tested. | Adapter profile. |
| ER02 | 04B: Custom transition via Balanced/Off tested; device profile. | State-dependent command. |
| ER03 | 04C: partial parameter mapping; device profile. | Versioned model capability profiles. |
| ER04 | 03, 04D, 06F: explicit segment selection reported. | Explicit segment commands. |
| ER05 | Progress and cleaned area reported in prior log; exact test reference unverified. | Treat telemetry as evidence, not completion proof. |
| ER06 | Cleaning mode unknown despite correct app mode per prior log; exact test reference unverified. | Separate requested, reported and verified states. |
| ER07 | 06D: progress reset on abort/dock. Reset after normal completion not independently verified. | Persist progress before interruption. |
| ER08 | Start/end/area available per prior log; exact test reference unverified. | End does not prove success. |
| ER09 | Pause asynchronous per prior log; 06A–C covers pause/resume but timing not established in report. | Bounded status polling. |
| ER10 | 06A–C: resume after pause preserves progress; exact position unverified. | Preserve logical job. |
| ER11 | Carpet priority and dynamic room order reported in prior log; no matching published test. | Current room is not completion proof. |
| ER12 | 06D: return to base aborts. | Verify returning/docked. |
| ER13 | 06D: progress resets after docking. | Persist journal before interruption. |
| ER14 | 06D: app records user abort; API access unverified. | Investigate history API. |
| ER15 | Completion checkmark for interrupted room reported in prior log; no matching published test. | Do not infer completion from checkmark alone. |
| ER16 | 06E: native resume after dock unverified; 06F: explicit remaining segments selected, outcome unverified. | Evaluate explicit remaining-segment strategy. |
| ER17 | Mop intensity reverted between jobs per prior log; no matching published test. | Evaluate reapply and readback per job. |
| ER18 | No direct observation; design hypothesis informed by 06D–F. | Logical job may span physical jobs. |

Unmatched observations require reconciliation with the private source or repeat testing before being treated as verified evidence. Do not publish household-specific data.
