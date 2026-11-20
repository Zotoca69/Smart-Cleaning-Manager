# Room mapping and map change detection — proposed design v0.1
Refs: #3, [architecture](../ARCHITECTURE.md), [requirements](../REQUIREMENTS.md), [POC report](../poc/POC_REPORT.md), [gap analysis](../GAP_ANALYSIS.md).
Scope: engine-neutral contract only. No engine, database, UI framework or deployment selection. All examples synthetic.

## Responsibility and information model
- Configuration owner approves local immutable baseline revisions; candidate discovery never grants approval. Store privately, version schema and baseline separately, atomic activation and rollback by explicit approval plus fresh validation.
- Baseline: schema_version, baseline_revision, robot_binding (stable installation identity plus current integration entity reference), maps (per robot map key, raw name, complete segment inventory of ID and raw name), area mappings (stable HA area ID, expected floor ID where configured, map key, nonempty set of segment IDs), approval metadata. Map and segment IDs are scoped to robot/map, not globally unique or guaranteed stable after remap. Floor ID is not a map ID.
- Example: synthetic robot R, map M, segments 101/102/103 with synthetic names A/B/C; area X maps to [101,102], Y to [103]. Another map may reuse 101. An area binding targets one map; split multi-map jobs into separate physical jobs. No implicit cross-map command.
- Require unique robot/map keys, unique segment IDs within each map, valid HA area references, explicit floor consistency if configured, no duplicated segment ownership within a map in v0.1. Unmapped inventory segments allowed but never implicitly scheduled. Validate nonempty targets and unsupported schema; never silently migrate or discard unknown required fields.
- Configuration interface presents discovered candidates, changes and diagnostics for owner confirmation; no particular UI assumed.

## Adapter and evidence
Logical operations: discover_inventory(robot) -> complete inventory or typed failure; resolve_active_map(robot) -> reliable active identity or unknown; resolve_areas() -> registry snapshot or failure; dispatch_segments(robot,map,ids,profile) -> accepted/rejected/unknown. These are proposed contracts, not existing API names.
Native Roborock get_maps was observed to return map flags, names and room ID/name dictionaries (read-only). Active map identity and freshness guarantees require separate validation; inventory listing is not proof of active map. A selected-map name alone is insufficient if ambiguous or stale. Native app_segment_clean via vacuum.send_command was exercised in POC 04D/06F; acceptance/app confirmation is not physical completion. Matter is not required. Evaluate reusable engine mapping interfaces before building an adapter; candidate engines are not yet acceptance-tested.
Record discovery time, source, success and completeness. Require a successful fresh observation for each execution attempt, no cached fallback on timeout, malformed payload or unavailable state. Adapter must report inability to establish freshness/active identity. Installed versions, stale-cache semantics and map switching support are open implementation validation items.

## Validation algorithm
1. Load one approved baseline revision; reject missing, invalid, unsupported or unapproved configuration. Resolve target logical areas against current registry and expected floor/binding.
2. Read current complete inventory and active map; reject unknown, malformed, duplicate identifiers, wrong robot or ambiguous identity. Compare all configured map inventories; absent configured maps or new unexpected maps require review. For target execution, require correct active map; do not automatically switch in this increment.
3. Compare target map complete raw ID/name pairs against baseline, ignoring ordering only. Added/deleted IDs, changed names (even case or whitespace), map rename or replacement => changed. Normalized Unicode NFC + trim + casefold may assist diagnostic matching, never authorization. Normalized collisions are flagged; no name-based remap. A canonical ordered serialization/digest may accelerate comparison, not substitute for explicit diff or geometry proof.
4. If other configured map changed, invalidate jobs targeting that map; if scope/identity cannot be determined, block all affected robot jobs. New unexpected maps or ambiguous shared identities block robot pending review. Unmapped added segment on target map still invalidates target inventory.
5. Return VALID_METADATA or BLOCKED with machine-readable reason, baseline revision, affected scope and safe diagnostic. Reasons include NO_BASELINE, SCHEMA_INVALID, AREA_MISSING, FLOOR_MISMATCH, INVENTORY_UNAVAILABLE, INVENTORY_INVALID, MAP_UNKNOWN, WRONG_ACTIVE_MAP, MAP_CHANGED, SEGMENT_ADDED, SEGMENT_REMOVED, SEGMENT_RENAMED, AMBIGUOUS_IDENTITY, BASELINE_CHANGED, GEOMETRY_REVIEW_REQUIRED. Store detailed diagnostics locally; public reports redact installation data.
6. Geometry is not verified by metadata equality. Known remap/geometry edit, even identical metadata, invalidates approval until manual inspection and new explicit approval. Undetectable changes remain residual risk; do not advertise geometry detection. Before unattended deployment owner must accept residual risk or require a reliable independent map revision/geometry signal. No live commands authorized by this design.

## Execution and resume
Orchestrator resolves logical targets into explicit segment list using approved revision. Bind validation result to robot, active map, revision, target IDs and execution attempt. Serialize local configuration activation and dispatch per robot; immediately recheck active map/inventory and baseline revision before submission, discard stale result on delay or change. Exact freshness window and locking implementation are open; external app edits can still race, so absolute atomicity is not claimed. If state changes while cleaning, notify orchestration to evaluate safe interruption; do not invent device abort semantics.
Resume after docking revalidates baseline and remaining logical targets from persistent journal. If baseline changed, block automatic resume and require reconciliation of already-cleaned vs remaining targets; never reinterpret old segment IDs. Unknown completion stays unknown, no blind generic start. On restart discard validation tokens and revalidate. Duplicate attempts require orchestration idempotency; unknown command outcome must be reconciled before retry. No completion claim from room mapping alone.

## Acceptance scenarios (specified, not executed)
| ID | Synthetic scenario | Expected result |
|---|---|---|
| T01 | Approved matching inventory, active map M, target X | VALID_METADATA, explicit [101,102] |
| T02 | Same inventory in different order | Same result |
| T03 | Rename, case-only or whitespace-only edit | BLOCKED, rename diagnostic |
| T04 | ID replaced, removed or added (including unmapped) | BLOCKED, explicit diff |
| T05 | Map renamed, missing, unexpected or wrong active map | BLOCKED for affected scope |
| T06 | Timeout, stale cache, missing fields, duplicate IDs or ambiguous active name | BLOCKED, no command |
| T07 | Two maps reuse segment 101 | Correct scoped resolution; no cross-map dispatch |
| T08 | Area removed, floor mismatch, duplicate ownership, empty list or unsupported schema | BLOCKED |
| T09 | Known geometry edit with unchanged metadata | GEOMETRY_REVIEW_REQUIRED |
| T10 | Baseline or map changes between validation and dispatch | Invalidate token; no command |
| T11 | Abort/dock, same baseline, remaining logical target Y | Revalidate, explicit [103]; no generic start |
| T12 | Resume after baseline change or unknown completion | Block automatic resume pending reconciliation |
| T13 | Restart, duplicate attempt or unknown submission outcome | Revalidate; reconcile before retry |
| T14 | No approval, discovered candidate, or rollback to stale baseline | BLOCKED |
| T15 | Diagnostic export/public fixture | No private identifiers or raw installation data |

Traceability: POC 03 supports inventory retrieval; 04D supports segment selection with physical-effect limits; 06A–C pause/resume progress; 06D abort/reset; 06E generic start not verified as resume; 06F explicit remaining plan accepted but cleaning outcome unverified. T01/T07 relate to 03/04D, T11/T12 to 06D–F. Historical private IDs not verified. Regression execution, version compatibility, active map detection and installed-engine capabilities are implementation gates, not passed tests.

## Open decisions and next increment
Evaluate Compose/Extend/Fork/Build mapping and dispatch capabilities, establish active-map and freshness semantics by read-only POC, decide local persistence/concurrency and manual geometry invalidation workflow. Establish runtime test harness and negative paths before any deployment. Design approval is not implementation or deployment approval. #3 remains open until functional acceptance and regression evidence are delivered.
