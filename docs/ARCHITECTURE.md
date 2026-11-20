# Architecture — proposed
Admin UI -> configuration manager -> policy/orchestration -> execution adapter -> existing engine or HA integration -> robot. Separate configuration, policy decisions, persistent journal, device capabilities and physical state. Logical jobs may span physical jobs. Unknown room completion is not success. Reject unsupported profiles or expose limitations; no uncontrolled generic start after dock. Evaluate Compose, Extend, Fork, Build before selecting engine. No engine selected. Local orchestration and no external telemetry proposed. Persistence, concurrency, migration and failure semantics require design and tests.

Proposed mapping validation contract: [room mapping design](decisions/room-mapping-design.md). Engine and persistence selection remain open.
