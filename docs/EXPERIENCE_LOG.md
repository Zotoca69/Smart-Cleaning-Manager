# Experience log — 2026-11-15
Anonymized from a private POC record. HA Green, Saros 20 Sonic, official Roborock and Matter integrations. Firmware/library versions unknown. See [POC report](poc/POC_REPORT.md) and [device profile](poc/SAROS_20_SONIC.md).
| ID | Observation / implication |
|---|---|
| ER01 | Combined motor command works; adapter profile. |
| ER02 | Tested Custom transition via Balanced/Off; state-dependent command. |
| ER03 | Model-specific codes; versioned capability profiles. |
| ER04 | Explicit segment command works. |
| ER05 | Progress and cleaned area reported. |
| ER06 | Cleaning mode unknown despite correct app mode; separate requested/reported/verified. |
| ER07 | Progress resets after job. |
| ER08 | Start/end/area available; end does not prove success. |
| ER09 | Pause asynchronous; bounded status polling. |
| ER10 | Start after pause preserves progress; exact position unverified. |
| ER11 | Carpet priority and dynamic room order; current room not completion proof. |
| ER12 | Return to base aborts; verify returning/docked. |
| ER13 | Progress resets after docking; persist journal before interruption. |
| ER14 | App history records user abort; API access unverified. |
| ER15 | Completion checkmark also seen for interrupted room. |
| ER16 | Native resume after dock unverified; explicit remaining segments proposed. |
| ER17 | Mop intensity reverted between jobs; reapply and read back. |
| ER18 | Logical job may span physical jobs. |
