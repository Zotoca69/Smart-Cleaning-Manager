# Offline evidence snapshot spike
POC10D–F, #3. Exact source versions HA 2026.11.2 and python-roborock 7.12.0. Not installable, not a product adapter. Caller binding and actual installed library version discovery are deliberately outside this spike. Candidate list must contain only V1 coordinators resolved against the approved device binding; cardinality check alone cannot verify identity. No commands, polling, credentials, services or HA imports. Scalar snapshot only, no active task ID claimed. The private coordinator timestamp is observation metadata, never proof of current data; mutable traits can change without that timestamp changing. All results forbid dispatch. Missing records/fields mean unknown; no outcome classification. Record ID not exposed by this projection; begin/end are correlation candidates only. Tests: cd poc/evidence_adapter && python -m unittest -v. Synthetic fixtures only. Before any live test: verify actual trait names/types and version, resolve device registry binding, handle reload/unload and access authorization; explicit deployment approval, backup and rollback. No separate client or refresh. Sources: HA core tag coordinator.py and vacuum.py, python-roborock tag v7.12.0 status.py, clean_summary.py and v1_containers.py. Prior source observations in #3. Rollback: remove offline files; no HA effect.

Review corrections B1/U1–U7: enum values are library-normalized, not raw codes; raw codes cannot be reconstructed. The fallback member (unknown if present, otherwise first member) is ambiguous even when genuinely returned; projected value is None and normalized diagnostic retained separately. No enum value establishes outcome or dispatch permission. Call synchronously on HA event loop, never from executor/thread; no timestamp double-read is used because it cannot establish consistency. records[0] exists but is not projected: records and last_clean_record update across separate awaited RPC calls. Actual snapshots including begin/end remain local; redact before publication. Unexpected exceptions propagate; caller must fail closed. Initial tests reported on Python 3.13.5 (implementer) and 3.13.18 (Claude). Corrected revision test evidence in PR. record_present distinguishes absent from empty records.

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

### Preserved U9 evidence
poc11a.py is Claude's original standalone reproduction artifact, not product code or part of unittest discovery. It requires an isolated environment with python-roborock 7.12.0; see #3 comment 7041058843 and POC_REPORT. Inspect reported deviations, not exit status alone. No HA or device connections.
