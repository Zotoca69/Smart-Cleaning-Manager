# Architecture and development manifest — draft 0.1
Normative after independent review and owner approval. Adapted from the Home Assistant methodology v1.4.
## Principles
- P1 Minimize hardcoding; use configuration and metadata.
- P2 Prefer simple, understandable solutions.
- P3 Evaluate existing HA capabilities and reusable implementations first.
- P4 Design for users; separate administration and daily operation.
- P5 Make incremental changes with testable acceptance criteria; verify each change before starting the next.
- P6 Trace changes, rationale, tests and rollback.
- P7 Documentation is part of delivery.
- P8 Verifiable AI-assisted learning: AI contributes alternatives, explanations and review; claims must be checkable. Make evidence, assumptions, uncertainty and lessons learned explicit.
- P9 Proportionate effort: define a budget as a reassessment point, not an automatic deadline. Stop when acceptance criteria and relevant checks pass and no blocking defects remain. New improvements do not automatically expand scope.
- P13 Local orchestration; no private household information or secrets in public Git.
- P14 Version configuration and test migrations and compatibility.
- P15 Separate development, testing, deployment and public release.
## Proposed principles (not normative until explicitly approved)
- P10 Vendor-neutral core; isolate device specifics in adapters.
- P11 UI-first configuration of household policies.
- P12 Discover and verify capabilities; distinguish accepted commands from observed effects.
## Open decisions
Engine selection (Compose, Extend, Fork, Build), deployment mechanics, persistence and concurrency model, and release path remain open. Existing safety and evidence requirements apply regardless of these choices.
## Governance
Owner decides scope, acceptance and release/deployment. AI proposes risk class with rationale; owner decides when a material trade-off or disagreement exists. ChatGPT or Claude implements; the other independently reviews where required. Self-review is not independent. Assign actual reviewer and exact revision.
R0: low-impact reversible documentation; content, diff, links and privacy self-check. R1: bounded functional change; relevant tests and independent review. R2: significant physical, security or data-loss consequences; review affected chain, negative paths, backup and verified rollback, explicit deployment approval. Governance changes always receive independent review. Classify consequences, not file types.
G1: before implementation record purpose, scope/exclusions, normally 2–5 testable criteria, risk rationale, verification, roles, dependencies and work budget in issue or PR. No extra mandatory owner gate.
G2: bounded implementation, documentation, tests and applicable independent review complete.
G3: owner approval of reviewed revision in GitHub comment/review before merge; material changes require renewed approval. Merge does not authorize deployment.
G4: merged documentation, or deployed and practically verified functionality; record limitations and concise worklog entry. Unreleased or undeployed code must be explicitly marked.
Use separate branches and bounded PRs. GitHub Issues is the sole backlog. One full review round normally; follow up blocking findings and effects. Never leave serious defects because of round limits. Escalate budget risk early; owner decides extension, scope or significant risk acceptance. New findings extend scope only if acceptance or unacceptable consequences require it.
## Safety and testing
Read current revision and affected dependencies before change. Preserve behavior and stable identities during refactoring. Verify unknown/unavailable, delayed events, restarts, duplicate commands and failure paths as relevant. R2 failures must be visible, not depend solely on the failed component for reporting. Test unit, integration and actual device behavior proportionately; simulated tests are not physical evidence. Validate UI empty/error/reload paths and migrations when applicable.
No unsolicited HA changes or physical commands. No uncontrolled cloning into /config. Verify deployment scope, access, backup and rollback before installation; Git is not HA backup. Explicitly approve current deployment scope. Public release is a separate owner decision. Do not publish secrets, household identities, private logs or topology. Validate dependencies and licenses before release.
## Records
PR is the authoritative current delivery status: review, approval, merge, deployment, verification. Record actual reviewer, reviewed commit, findings and disposition. Report only executed tests as passed. Keep concise closure entry in WORKLOG; durable decisions in docs/decisions; routine approvals in PR. Preserve history and avoid duplicate bookkeeping. Skills implement procedures, not duplicate normative rules.
