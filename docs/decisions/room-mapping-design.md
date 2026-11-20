# Room mapping and map change detection — proposed design v0.2
Refs: #3, [architecture](../ARCHITECTURE.md), [requirements](../REQUIREMENTS.md), [POC report](../poc/POC_REPORT.md), [gap analysis](../GAP_ANALYSIS.md).
Status: proposed; full approval pending G3. Owner approved normalized name comparison (Ä1) in PR #4. Alternatives: strict raw equality (rejected for avoidable interruptions), normalized equality with warning (selected), automatic name-based remapping (rejected for ambiguous identity). Consequence: fewer typographic false blocks, residual geometry risk unchanged.
Scope: engine-neutral contract only. No engine, database, UI framework or deployment selection. All examples synthetic.

## Responsibility and information model
- Configuration owner approves local immutable baseline revisions; candidate discovery never grants approval. Store privately, version schema and baseline separately, atomic activation and rollback by explicit approval plus fresh validation.
- Baseline: schema_version, baseline_revision, robot_binding (local HA device registry ID plus separately validated integration/entity reference; feasibility of stable binding to be verified), maps (per robot map key, raw name, complete segment inventory of ID and raw name), area mappings (stable HA area ID, expected floor ID where configured, map key, nonempty set of segment IDs), approval metadata. Map and segment IDs are scoped to robot/map, not globally unique or guaranteed stable after remap. Floor ID is not a map ID.
- Example: synthetic robot R, map M, segments 101/102/103 with synthetic names A/B/C; area X maps to [101,102], Y to [103]. Another map may reuse 101. Unique binding key is (robot_binding, HA area ID); each binding targets exactly one map. Multiple areas on different maps form separate physical jobs; robot selection is explicit, never inferred from active map. No implicit cross-map command.
- Map key is a local approved identity linked to adapter locator (e.g. flag), not the flag itself; locator reuse with identical metadata may escape detection. Entity rename requires explicit reference reconciliation with unchanged device identity; no silent rebinding. Require unique area binding keys and robot/map keys, unique segment IDs within each map, valid HA area references, explicit floor consistency if configured, no duplicated segment ownership within a map in v0.1. Shared segment across multiple HA areas (N:1) is unsupported in v0.2. Unmapped inventory segments allowed but never implicitly scheduled. Validate nonempty targets and unsupported schema; never silently migrate or discard unknown required fields.
- Configuration interface presents discovered candidates, changes and diagnostics for owner confirmation; no particular UI assumed.

## Adapter and evidence
Logical operations: discover_inventory(robot) -> complete inventory or typed failure; resolve_active_map(robot) -> reliable active identity or unknown; resolve_areas() -> registry snapshot or failure; dispatch_segments(robot,map,ids,profile) -> accepted/rejected/unknown. These are proposed contracts, not existing API names.
Native Roborock get_maps returned a map flag, name and segment ID/name dictionary in the read-only observation POC 07 (2026-11-20, #3). This single-map observation does not establish complete multi-map coverage. Active map identity and freshness guarantees require separate validation; inventory listing is not proof of active map. A selected-map name alone is insufficient if ambiguous or stale. Native app_segment_clean via vacuum.send_command was exercised in POC 04D/06F; acceptance/app confirmation is not physical completion. Matter is not required. Evaluate reusable engine mapping interfaces before building an adapter; candidate engines are not yet acceptance-tested.
Record discovery time, source, success and completeness. Require a successful fresh observation for each execution attempt, no cached fallback on timeout, malformed payload or unavailable state. Unknown freshness blocks execution (FRESHNESS_UNKNOWN); known stale observations block with FRESHNESS_STALE; cached-only data without validated freshness semantics cannot authorize dispatch. Installed versions, stale-cache semantics and map switching support are open implementation validation items.

## Validation algorithm
1. Load one approved baseline revision; reject missing, invalid, unsupported or unapproved configuration. Resolve target logical areas against current registry and expected floor/binding.
2. Read current complete inventory and active map; reject unknown, malformed, duplicate identifiers, wrong robot or ambiguous identity. Require reliable complete map catalog and complete inventories for all configured maps, including inactive maps. If any cannot be established, block robot (INVENTORY_INCOMPLETE); feasibility is an implementation gate. Missing configured map with unambiguous scope blocks that map; unexpected maps block robot because identity allocation may have changed. Unknown active map blocks robot (MAP_UNKNOWN); ambiguous identity uses AMBIGUOUS_IDENTITY instead. For target execution, require correct active map; do not automatically switch in this increment.
3. Compare complete ID sets and names per stable matched ID, ignoring ordering. Added/deleted IDs, materially changed names, map rename or replacement => changed. For segment names only, Unicode NFC + trim + casefold equality permits raw spelling differences with NAME_NORMALIZED warning; preserve both raw names. Any normalized collision among segment names within a map (baseline or observed) blocks that map with AMBIGUOUS_IDENTITY even when IDs match. Map names remain strict. Never use names to remap IDs. A canonical ordered serialization/digest may accelerate comparison, not substitute for explicit diff or geometry proof.
4. If other configured map changed, invalidate jobs targeting that map; if scope/identity cannot be determined, block all affected robot jobs. New unexpected maps or ambiguous shared identities block robot pending review. Unmapped added segment on target map still invalidates target inventory.
5. Return VALID_METADATA or BLOCKED with machine-readable reason, baseline revision, affected scope and safe diagnostic. Return a set of all observed applicable reason codes with scope; do not infer additional failures solely from missing evidence after an earlier failure. warnings do not override blocks. Codes: NO_BASELINE (missing/unapproved), SCHEMA_INVALID (invalid schema or empty targets/duplicate ownership), DUPLICATE_BINDING, AREA_MISSING, FLOOR_MISMATCH, ROBOT_MISMATCH (device or unresolved entity binding), INVENTORY_UNAVAILABLE (integration unavailable), INVENTORY_TIMEOUT, INVENTORY_INCOMPLETE, INVENTORY_INVALID (malformed/duplicate IDs), FRESHNESS_UNKNOWN (freshness cannot be established), FRESHNESS_STALE (known stale), MAP_UNKNOWN (active identity unknown), WRONG_ACTIVE_MAP, MAP_CHANGED, SEGMENT_ADDED, SEGMENT_REMOVED, SEGMENT_RENAMED, NAME_NORMALIZED (warning), AMBIGUOUS_IDENTITY, BASELINE_CHANGED, GEOMETRY_REVIEW_REQUIRED, COMPLETION_UNKNOWN, REVALIDATION_REQUIRED, DUPLICATE_ATTEMPT, OUTCOME_UNKNOWN. Config/robot identity failures block robot; target-specific failures block target map/job; unknown scope blocks robot. Store detailed diagnostics locally; public reports redact installation data.
6. Geometry is not verified by metadata equality. Known remap/geometry edit, even identical metadata, invalidates approval until manual inspection and new explicit approval. Undetectable changes remain residual risk; do not advertise geometry detection. Before unattended deployment owner must accept residual risk or require a reliable independent map revision/geometry signal. No live commands authorized by this design.

## Execution and resume
Orchestrator resolves logical targets into explicit segment list using approved revision. Bind validation result to robot, active map, revision, target IDs and execution attempt. Serialize local configuration activation and dispatch per robot; immediately recheck active map/inventory and baseline revision before submission, discard stale result on delay or change. Exact freshness window and locking implementation are open; external app edits can still race, so absolute atomicity is not claimed. If state changes while cleaning, notify orchestration to evaluate safe interruption; do not invent device abort semantics.
Resume after docking revalidates baseline and remaining logical targets from persistent journal. If baseline changed, block automatic resume and require reconciliation of already-cleaned vs remaining targets; never reinterpret old segment IDs. An interrupted area remains outstanding as a whole if incompletion is established; partial segment completion within an area is out of scope. Unknown completion stays unknown and blocks automatic resume (COMPLETION_UNKNOWN); currently POC evidence does not establish authoritative completion, so automatic resume is not demonstrated. No blind generic start. On restart discard validation tokens and revalidate. Duplicate attempts require orchestration idempotency; unknown command outcome must be reconciled before retry. No completion claim from room mapping alone.

## Acceptance scenarios (specified, not executed)
Each lettered subcase is a separate assertion. BLOCKED means no dispatch for affected scope. Listed codes are the minimum required set with stated scope; additional codes must be independently supported by observations. Positive cases require no blocking code affecting the target. Isolated fixtures should return exactly the listed codes when no other failure is observed.
| ID | Synthetic scenario | Expected result / code / scope |
|---|---|---|
| T01 | Matching approved inventory, active M, target X | VALID_METADATA [101,102] |
| T02 | Reordered inventory | VALID_METADATA |
| T03a | Case, edge whitespace or NFC-only segment name change | VALID_METADATA + NAME_NORMALIZED, map warning |
| T03b | Material segment rename | BLOCKED SEGMENT_RENAMED, map |
| T04a | ID replaced | BLOCKED SEGMENT_REMOVED + SEGMENT_ADDED, map |
| T04b | ID removed | BLOCKED SEGMENT_REMOVED, map |
| T04c | ID added, even unmapped | BLOCKED SEGMENT_ADDED, map |
| T05a | Map renamed | BLOCKED MAP_CHANGED, map |
| T05b | Configured map missing, identity scope known | BLOCKED MAP_CHANGED, missing map |
| T05c | Unexpected map | BLOCKED MAP_CHANGED, robot |
| T05d | Wrong active map | BLOCKED WRONG_ACTIVE_MAP, job |
| T06a | Timeout | BLOCKED INVENTORY_TIMEOUT, robot |
| T06b | Cache freshness unknown | BLOCKED FRESHNESS_UNKNOWN, robot |
| T06c | Malformed fields or duplicate IDs | BLOCKED INVENTORY_INVALID, robot |
| T06d | Ambiguous active identity | BLOCKED AMBIGUOUS_IDENTITY, robot |
| T06e | Integration unavailable | BLOCKED INVENTORY_UNAVAILABLE, robot |
| T06f | Inactive inventory incomplete | BLOCKED INVENTORY_INCOMPLETE, robot |
| T06g | Active map identity unknown, otherwise complete fresh inventory | BLOCKED MAP_UNKNOWN, robot |
| T06h | Observation known stale | BLOCKED FRESHNESS_STALE, robot |
| T07a | Maps reuse segment 101; distinct area/floor bindings | VALID_METADATA for correct active map, separate physical jobs |
| T07b | Other known map renamed; target unchanged | VALID_METADATA target; MAP_CHANGED blocks other map |
| T08a | Area removed | BLOCKED AREA_MISSING, job |
| T08b | Floor mismatch | BLOCKED FLOOR_MISMATCH, job |
| T08c | Duplicate ownership, empty target or unsupported schema | BLOCKED SCHEMA_INVALID, robot |
| T08d | Duplicate robot/area binding | BLOCKED DUPLICATE_BINDING, robot |
| T08e | Wrong device or unresolved changed entity binding | BLOCKED ROBOT_MISMATCH, robot |
| T08f | Normalized segment names collide | BLOCKED AMBIGUOUS_IDENTITY, map |
| T09 | Known geometry edit, metadata identical | BLOCKED GEOMETRY_REVIEW_REQUIRED, map |
| T10a | Baseline changed before dispatch | BLOCKED BASELINE_CHANGED, job |
| T10b | Target map renamed before dispatch | BLOCKED MAP_CHANGED, map; discard token |
| T10c | Target segment removed before dispatch | BLOCKED SEGMENT_REMOVED, map; discard token |
| T11 | Synthetic authoritative completion of X, known incomplete Y after dock | VALID_METADATA [103] after revalidation; no generic start |
| T12a | Resume with changed baseline | BLOCKED BASELINE_CHANGED, job |
| T12b | Completion unknown | BLOCKED COMPLETION_UNKNOWN, job |
| T13a | Restart | Old token rejected REVALIDATION_REQUIRED, job; fresh validation required |
| T13b | Duplicate attempt | BLOCKED DUPLICATE_ATTEMPT, job |
| T13c | Submission outcome unknown | BLOCKED OUTCOME_UNKNOWN, job pending reconciliation |
| T14a | No approved baseline or candidate only | BLOCKED NO_BASELINE, robot |
| T14b | Approved rollback but stale observation | BLOCKED FRESHNESS_STALE, robot |
| T14c | Explicitly approved rollback and fresh matching observation | VALID_METADATA under newly activated revision |
| T14d | Approved rollback candidate, fresh inventory with segment missing from candidate's expected inventory | BLOCKED SEGMENT_REMOVED, map; do not activate candidate |
| T15 | Export diagnostic/public fixture | No private identifiers or raw installation data |

G1 trace: criterion 1 (identity/1:N/multi-map) T01,T07,T08,T14; criterion 2 (change/diagnostics) T02–T10; criterion 3 (start/resume/approval) T10–T14; criterion 4 (test coverage/POC) all scenarios and trace below; criterion 5 (privacy/engine neutrality) T15 plus static adapter boundary review. Issue #3 requirements: mapping T01/T07/T08; read-only inventory and changes T02–T06/T09; blocking and diagnostics T03–T14; approval T14; adapter boundary static review. DK11 mapping, DK12 validation, DK13 execution binding correspond to G1 criteria 1–3.
Traceability: POC 03 supports inventory retrieval; 04D supports segment selection with physical-effect limits; 06A–C pause/resume progress; 06D abort/reset; 06E generic start not verified as resume; 06F explicit remaining plan accepted but cleaning outcome unverified. T01/T07 relate to 03/04D, T11/T12 to 06D–F. Historical private IDs not verified. Regression execution, version compatibility, active map detection and installed-engine capabilities are implementation gates, not passed tests.

## Open decisions and next increment
Evaluate Compose/Extend/Fork/Build mapping and dispatch capabilities, establish active-map, complete catalog and inactive-map inventory coverage, stable device binding and freshness semantics by read-only POC, decide local persistence/concurrency and manual geometry invalidation workflow. Establish runtime test harness and negative paths before any deployment. Design approval is not implementation or deployment approval. #3 remains open until functional acceptance and regression evidence are delivered.
