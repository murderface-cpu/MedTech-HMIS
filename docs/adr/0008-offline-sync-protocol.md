# 0008. Offline-first workstations: commands, outbox and pull cursor

- Status: accepted
- Date: 2026-10-30

## Context

Blueprint 3.9: front desk, triage, consultation and pharmacy keep working when the link drops,
with clinical notes appending, stock and payments sequenced on the server, and registration
conflicts going to merge review. Wait-time analytics (3.6) need the time care happened, not the
time it reached the server.

## Decision

**One write path.** Every change is a command (`patient.register`, `triage.record`,
`dispense.record`, ...) with a UUID op id and a device timestamp. The device writes it to an
IndexedDB outbox *and* applies its effect to the local copy in one transaction, then sends it to
`POST /api/v1/sync/push`. Online and offline run the same code. Handlers live in
`backend/app/sync/commands.py`; their local mirrors in `frontend/app/local/commands.ts`.

**Idempotent push.** The server records every op id (`sync_op`). A replayed op returns its stored
outcome and changes nothing. Ops are applied in order, each in its own transaction. An op is
`applied`, `rejected` (never retried; shown to staff with the reason) or `held`.

**Client-generated ids.** Records get UUIDs on the device, so offline work keeps its identity.
Human-facing numbers (MRN, visit number) are assigned by the server and show as "Pending" until
synced. The patient card's QR token is random and made on the device, so cards print offline.

**Pull cursor.** Every synced row carries `seq`, taken from a counter row whose lock is held to
commit, so `seq` order is commit order. `GET /sync/pull?since=n` reads the committed counter
first and caps the page there, so a late commit can never be skipped. Visit-scoped records are
sent for visits opened in the last 72 h or still open; older history is fetched on demand and
cached.

**Local rows ahead of the server** carry `_pending = op id`. A pull doesn't overwrite them while
that op is still queued. When an op is rejected, the server re-stamps the rows the device changed
optimistically (for a dispense: prescription, drug stock and visit) so the next pull corrects them.

**Conflict rules.**

| Data | Rule |
| --- | --- |
| Notes, diagnoses, vitals, allergies | Append-only, own ids; corrections are new entries or "entered in error" |
| Patient demographics | Last write wins per field; every change audited |
| Duplicate registrations | Both kept; `duplicate_review` row; front desk merges or dismisses |
| Stock | Decided on the server in sync order (first expiry, first out); an overdraw is a rejected dispense that syncs back |
| Visit stage | Follows the journey event with the latest *device* time, so sync order doesn't matter |
| Device clock ahead of server | Clamped to server time and flagged |

**Shared workstations.** Signing in online stores a PBKDF2 password verifier and the user's
tokens on the device. Offline, a user who has signed in there in the last 7 days can unlock it.
Queued ops are pushed with *their author's* token (refreshed as needed), so one user's work is
never sent under another's identity. If an author's refresh token has expired, pushing stops at
their first op, because later ops may depend on it, and the device asks for that user to sign in.

## Consequences

- Patient data is stored in the browser's IndexedDB. Protection at rest relies on device disk
  encryption and OS accounts; encrypting the local store is a follow-up.
- The edge-node option (blueprint 3.9) is the same backend run on the hospital network; devices
  sync to it, and edge-to-cloud replication is a separate piece of work.
- Every new command needs a server handler, a local mirror and a test in
  `backend/tests/test_sync.py`.
