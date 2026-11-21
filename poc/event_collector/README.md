# HA Event Collector — POC12C offline review candidate

Standalone local observer prototype for scoped Home Assistant `subscribe_entities` evidence capture (issue #3, G1 7047775531). **Offline only:** the GUI and all tests use an in-process synthetic transport. No live HA connection, token use, installation, device command or physical test is authorized. B1 in #3 remains open, POC12B is deferred, L NOT TESTED, freshness UNKNOWN, dispatch forbidden.

## Files
| file | role |
|---|---|
| `config.py` | all limits, protocol constants and input validation (IDs, duration, URL) |
| `protocol.py` | subscription request, handshake/message validation, derived event metadata (no I/O) |
| `collector.py` | bounded capture loop; transport injected (`connect_fn`); `live_connect` = reviewable live settings, unused |
| `storage.py` | private capture folder (POSIX 0700/0600, Windows current-user-only ACL), append-only rows, manifest after every row |
| `provenance.py` | collector revision, source digest, runtime versions recorded in manifests |
| `export.py` | capture verification and ZIP export with manifest/archive SHA-256 and `.sha256` sidecar |
| `synthetic.py` | synthetic in-process transport (GUI demo and tests) |
| `app.py` | Tkinter GUI (synthetic mode only) |
| `test_*.py`, `_testsupport.py` | regression tests; run without Tkinter except `test_gui.py` |
| `API.md` | reviewed HA API baseline, permissions, client comparison (B1) |
| `windows/` | one-click Windows test package (see `windows/WINDOWS_TEST.md`) |
| `TEST_RESULTS.txt` | actual test output for the committed revision |

## Run
Requires Python 3.12+ (3.13 recommended) and `websockets==16.0`; the GUI needs Tkinter.
```
python -m pip install -r requirements.txt
python -m unittest discover -v      # regression suite; GUI test skips without Tkinter/display
python app.py                       # synthetic GUI demo
```
Environment switches for test packages: `SCM_REQUIRE_GUI=1` turns a skipped GUI test into a failure; `SCM_REQUIRE_WINDOWS_ACL=1` requires the real Windows ACL test.

## Evidence format (`schema poc12c-evidence-2`)
A capture folder contains only `messages.jsonl` and `manifest.json`.
- Row: `seq`, `session_id`, `direction` (`send` for the subscription, then `receive`), `utc`, `elapsed_ns` (monotonic), `sha256`, `duplicate_of_earlier_payload`, `payload_b64` (exact application bytes), optional `derived` (reviewer metadata, not evidence).
- Manifest: session, start/end UTC, `status`/`complete`/`reason`/`ended_by` (`deadline`, `operator`, `gap`, `error`), allowlist, provenance (collector revision and source digest, Python, websockets, OS, observed `ha_version`, SHA-256 of endpoint URL, synthetic flag), storage mechanism, message/byte counts, aggregate SHA-256 of `messages.jsonl`, flags (duplicates, out-of-order server time, unavailable/unknown, removed entities), `freshness: UNKNOWN`, `device_truth: NOT_ESTABLISHED`.
- `complete` means: acknowledgement and full initial snapshot received, bounded observation ended by deadline or operator, no protocol error, no removal gap. It does not prove device truth or that every server event was delivered.
- The manifest is rewritten after every row, so an interrupted capture stays verifiable up to its last complete row; a row written after the last manifest update makes verification fail (visible, not hidden).

## Export and review
GUI "Export capture" (or `export.export_capture(folder, zip)`) verifies the folder, writes a new ZIP (never overwrites), re-reads it, writes `<zip>.sha256` and shows manifest and archive SHA-256. Incomplete captures export with their status. Record only the digests publicly (e.g. in #3); keep captures and archives private. Hashes show integrity after capture, not authenticity.

## Limits and decisions
- Exact allowlist only (1–100 IDs), duration 1–900 s, 1 MB per message, 10 MB per capture, no reconnect.
- `wss://` required; local `ws://` is an open owner decision. No proxy, no compression.
- Write prevention is client-side only (see API.md). Token never stored; handshake not captured.
- Windows protection uses `icacls`/`Get-Acl` (built-in); crash durability is per-row fsync on a local disk, not a guarantee against disk failure.
- Live capture is intentionally not wired into the GUI and requires separate scoped approval.

## Disposition of review findings (PR #9, review 7049253477)
| item | disposition |
|---|---|
| B1 API documentation | `API.md`: version/source, schema, ordering, event and compressed formats, permission model, client-side-only write prevention, client comparison |
| B2 gaps and tests | removal → incomplete `observation gap`; duplicates, out-of-order server time and unavailable/unknown flagged; full negative suite incl. malformed, coalesced, wrong ID, rejected subscription, auth failure, disconnect, size, guards, no-write static check, loopback TLS test with real websockets |
| B3 private storage | POSIX 0700/0600 verified; Windows folder created without mode, then `icacls /reset` and `icacls /inheritance:r /grant:r *SID:(OI)(CI)F` + `Get-Acl` SID verification, fail closed (Python >=3.12.4 mkdir(0o700) adds Administrators ACEs, so the whole DACL is replaced); real Windows test in the Windows package (not executable in the Linux review environment) |
| U1 HA version | `ha_version` from handshake in manifest |
| U2 provenance | session ID, start/end, allowlist, endpoint hash, collector revision and source digest, runtime versions |
| U3 anchoring | manifest/archive SHA-256 shown and `.sha256` sidecar |
| U4 crash durability | manifest after every row, fsync, verifiable partial capture |
| U5 duplicates/order | preserved and flagged, interpretation left to review |
| U6 `wss://` vs local `ws://` | kept `wss://`; documented as open owner decision |
| U7 proxy | `proxy=None` (tested) |
| U8 no mock in production | transport injected; `synthetic.py` replaces `unittest.mock` |
| U9 shared configuration | `config.py`; GUI uses the same validators (no `assert`) |
| U10 test environment | core tests without Tkinter; GUI test separate; Windows package; `TEST_RESULTS.txt` records platform and versions |
