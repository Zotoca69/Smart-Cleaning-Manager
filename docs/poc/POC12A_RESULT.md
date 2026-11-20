# POC12A — observed normal start (V01)
## Scope and provenance
Approved #3 G1 comments 7042176948 / 7042366535, review 7042408467, R2 approval 7042572256. Owner operated native app; ChatGPT observed existing HA state/history only. One vacuum-only job spanning two approved segments. Public report omits household names, IDs, absolute times, geometry, screenshots and raw trace. Implementer report; independent private evidence review pending. Connection transport UNKNOWN.
## Evidence
T0 is receipt-side start confirmation, not exact command time; retrospective recorded start precedes T0 by about 25 s. Baseline owner confirmed readiness, HA corroborated docked/charging, sufficient battery, expected map and no reported errors. HA timestamps do not prove device freshness.
| Relative to T0 | HA observation | Owner/app evidence |
|---|---|---|
| Baseline | docked, charging, progress 0 | prerequisites confirmed |
| 0 s | cleaning, segment_cleaning, progress 3 | owner confirms start |
| +39 s | progress 10; area and duration increased | intended two-segment job, physical movement |
| +118 s | progress 28; area and duration increased | same job, no stop/reset |
| +184 s | progress 46; area and duration increased | subsequent app evidence supports continuity |
| +523 s | progress 81, second segment reported | app sequence confirms first segment completed, second underway |
| About +13 min | docked, charging, progress 0; new last-start/end values | owner confirms completion, dock and bin emptying finished |
Planned +90 and +180 reads were late; progress already observed at +39. Primary continuity is owner/app evidence, not a unique task ID. App progress and HA progression agree qualitatively, not synchronized point-for-point.
## History and findings
Recorder history: docked → cleaning → returning → docked, no recorded intervening idle/docked state during cleaning. Detailed status: charging → segment_cleaning → returning_home → charging → emptying_the_bin → charging → attaching_the_mop → charging. These are recorded HA transitions, not atomic device events. Progress history metadata confirms percent; 29 positive values from 3 to 94, then reset to zero without recorded 100. No inference that device never reached 100. Area and duration remain after reset. Last-start/end remained previous values during observations and changed together after cleaning; retrospective interval compatible with observed job, not unique ID or full native record. Room transition observed; room completion supported by app, not inferred from room sensor. Dock/charging alone cannot establish readiness; charging appeared between maintenance activities. No published household measurements beyond relative timing and progress needed for evidence.
## Assessment
P PASS and supplemental POC12A-specific O PASS proposed by implementer: primary scope/start/progress continuity and corroborating HA windows supported. O is not a normative new gate. L NOT TESTED, freshness UNKNOWN, dispatch forbidden under existing gates. AC01–03 positive; AC04 evidence assembled, AC05 physical safe handover confirmed; private trace review and formal acceptance pending. V02–V09 not run; incidental completion is not V05. Exact HA/SCM command path unverified.
## Procedural trace
A001–A007: seven batch_get_state calls, each 12 predeclared entities, fields state/last_changed/last_updated (attribute filtering returned empty attributes). A008–A013: six get_history calls for approved vacuum, status, progress, current-room, last-start/end entities, bounded baseline-to-final-read interval. All returned successfully. History has no field filter and returned attributes including percent unit; private trace retained in conversation. No service calls or writes during formal run. Earlier separately authorized discovery included an overbroad inventory call and lacked exact request/response timing; excluded from formal ledger, disclosed, not represented as compliant formal observation. Connector privileges broad, restriction procedural. No independent HA audit. Owner/Claude must compare actual available trace with private ledger; if not accessible, AC04/05 remain unestablished. No further HA access authorized by this report.
## Design implications (proposals, not changes)
Use progress and current-room for observation/presentation, never alone for completion, retained-task identity or readiness. Correlate independent lifecycle/record evidence; do not require 100 percent. Distinguish cleaning, return, dock and maintenance; determine readiness with independently verified criteria, not a charging sample or invented dwell threshold. Preserve all approved mapping, freshness, policy and uncertainty gates.
## Next
Independent Claude review of exact PR revision and separate private ledger check; owner acceptance before merge. POC12B V02/V03 needs separately reviewed scope and R2 authorization, fresh readiness, same-task evidence and safe handover. No physical action in this delivery.
