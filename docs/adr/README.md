# Architecture decision records

| ADR | Decision | Status |
| --- | --- | --- |
| [0001](0001-modular-monolith-on-django.md) | Modular monolith on Django | Accepted |
| [0002](0002-postgresql.md) | PostgreSQL as the system of record | Accepted |
| [0003](0003-repository-layout.md) | Repository layout and naming | Accepted |
| [0004](0004-api-versioning.md) | Versioned REST API under `/api/v1/` | Accepted |
| [0005](0005-session-auth-and-module-access.md) | Session authentication and module-based access | Accepted |
| [0006](0006-workspace-navigation-and-routes.md) | Workspace navigation and routes | Accepted |
| [0007](0007-fastapi-and-nuxt-port.md) | Port to FastAPI and Nuxt, module by module | Accepted |
| [0008](0008-offline-sync-protocol.md) | Offline-first workstations: commands, outbox and pull cursor | Accepted |

New decisions copy [template.md](template.md) and take the next number. An accepted ADR is never
edited to reverse it; write a new ADR that supersedes it.
