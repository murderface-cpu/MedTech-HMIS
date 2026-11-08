# 0007. Port to FastAPI and Nuxt, module by module

- Status: accepted
- Date: 2026-10-30
- Amends: [0001](0001-modular-monolith-on-django.md), [0005](0005-session-auth-and-module-access.md)

## Context

Blueprint 3.9 requires the front desk, triage, consultation and pharmacy to keep working when the
internet drops. Server-rendered Django pages can't do that: every screen needs a round trip. The
workstations have to run in the browser from a local copy of the data, which makes the server an
API plus a sync endpoint rather than a page renderer.

## Decision

- **Backend:** FastAPI, SQLAlchemy 2 and Alembic in `backend/`, on the same PostgreSQL server
  (separate `hmis` database). Still a modular monolith: one deployable.
- **Frontend:** Nuxt 4 with Vue, built as a client-only PWA in `frontend/`. A service worker
  precaches the whole app; data lives in IndexedDB (Dexie).
- **Auth:** JWT access tokens (15 min) and refresh tokens (one shift, 12 h), replacing Django
  sessions for the new workstations. Offline sign-in is covered in ADR 0008.
- **Port order:** the four offline workstations first (Release 1 certification core), then the
  remaining Django modules. The Django app stays runnable at the repository root until each of
  its modules has been ported, then is removed.

## Consequences

- Two stacks run side by side during the port. The Django app keeps its own database and is
  not migrated automatically; a data migration from it is a separate, planned step.
- The design system carries over: `frontend/app/assets/css/system.css` uses the same tokens as
  `static/css/system.css` (DESIGN.md).
- CI runs both stacks.
