# HA WebSocket API baseline for the POC12C collector (B1)

Status: offline design reference. The installed HA version must be confirmed by the owner before any separately approved live run. Nothing here authorizes live use.

## Source and version
- Reviewed source: Home Assistant Core tag `2026.11.2` (`homeassistant/const.py` reports `__version__ = "2026.11.2"`).
  - `homeassistant/components/websocket_api/commands.py` (`handle_subscribe_entities`, `_forward_entity_changes`, `_async_get_allowed_states`)
  - `homeassistant/components/websocket_api/messages.py` (compressed state and diff construction)
  - `homeassistant/const.py` (compressed key constants)
- Public developer documentation describes the WebSocket API at `/api/websocket` but does not document `subscribe_entities`; behaviour below is taken from source and should be re-checked for the installed version.
- The collector records the `ha_version` reported in `auth_required`/`auth_ok` in each manifest so captures are tied to the server version actually observed.

## Messages used by the collector
Only these application messages are sent:
1. `{"type":"auth","access_token":…}` — required handshake; never stored.
2. `{"id":1,"type":"subscribe_entities","entity_ids":[…exact IDs…]}` — stored as row 1 (`direction: send`).

No `call_service`, `fire_event`, `subscribe_events`, `get_states` or other commands exist in the code (static test `test_no_write_command_path_in_sources`).

## `subscribe_entities` (HA 2026.11.2)
- Schema: `type`, optional `entity_ids` (`cv.entity_ids`), plus include/exclude entity filter options. The collector never sends filters.
- **An omitted or empty `entity_ids` means no ID filter (all readable entities).** `config.validate_entity_ids` rejects empty lists, wildcards, duplicates and malformed IDs before anything is sent or stored.
- Ordering: the state-change listener is registered, then the `result` acknowledgement is sent, then one initial snapshot event. The collector requires exactly this order (ack, then an `a`-only snapshot containing every allowlisted ID) or stops as incomplete.
- Entities that do not exist are absent from the snapshot → capture stops as incomplete ("incomplete initial snapshot").

## Event format
Top-level event keys (`ENTITY_EVENT_*`):
| key | meaning |
|---|---|
| `a` | added entities → full compressed state |
| `c` | changed entities → diff with `+` (added/changed fields) and optional `-` (removed attribute keys) |
| `r` | removed entity IDs (list) |

Compressed state keys (`homeassistant.const`): `s` state, `a` attributes, `c` context, `lc` last_changed, `lu` last_updated (epoch seconds). In diffs `lc` is sent when last_changed changed, otherwise `lu` when only last_updated changed. In full states `lu` may be absent; the collector then treats `lc` as last_updated (derived metadata only; verify against raw bytes).

Collector handling:
- Raw application bytes are stored before interpretation; derived fields (`added`, `changed`, `removed`, `server_times`, `unavailable`) are kept separately under `derived`.
- `r` for an allowlisted entity (e.g. entity deleted or integration reloaded) ends the capture as **incomplete: observation gap**; the removal message itself is kept.
- `unavailable`/`unknown` states, identical repeated payloads and decreasing server `lu`/`lc` per entity are **flagged in the manifest, not dropped or reinterpreted**.
- Any other key, entity, ID, message type, JSON array (message coalescing is never requested) or malformed JSON stops the capture as incomplete; the rejected message is not stored.

## Permissions and write prevention
- `subscribe_entities` is not admin-only. Initial states are filtered by the user's read permission (all states for admins or users with global read access, otherwise per-entity `POLICY_READ`), and permissions are re-checked for every forwarded change.
- A Home Assistant access token is **not** inherently read-only: ordinary users can call services. Write prevention in this POC is enforced only by the client (single subscription message, static test). Any future live run needs a separately approved decision on the HA user/token and its revocation.

## Existing clients considered (P3)
| option | assessment |
|---|---|
| HA frontend `home-assistant-js-websocket` (`subscribeEntities`) | Maintained by HA and uses the same command, but reconstructs entity state objects for UI use; it does not keep the raw message bytes needed as evidence and would add a JavaScript runtime. |
| Python wrappers (e.g. `homeassistant_api` WebsocketClient, `py-ha-ws-client`, `hassapi`, `hass-websocket-client`) | General-purpose clients oriented to state retrieval and service calls. They parse messages before the application sees them and include command paths (service calls) that this POC must not have. None was verified to expose raw frame bytes; adopting one would require the same audit plus a wrapper. Not verified as replacements. |
| `subscribe_events` (`state_changed`) | Rejected: household-wide disclosure, much higher volume. |
| Minimal client on `websockets` 16.0 (chosen) | One pinned dependency, raw bytes via `recv(decode=False)`, no command API surface, every message validated against the allowlist. |

## Transport
- `wss://` is required (token protection). Local non-TLS `ws://` access is an **open owner decision**; it is not supported in this revision.
- `live_connect` sets `proxy=None` (websockets otherwise honours system proxy settings), `compression=None`, `max_size` 1 MB, fixed open/close timeouts. No automatic reconnect; a disconnect ends the capture as incomplete.
- Base64 rows preserve application message bytes after TLS and WebSocket framing are removed; they are not network packets and do not prove device truth or freshness.
