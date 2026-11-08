# Documentation

This folder follows the layout in section 4.1 of the HMIS Master Blueprint, "Repository structure":
architecture decisions, the API contract, runbooks and requirement traceability all live next to
the code.

| Folder | Contents |
| --- | --- |
| [architecture.md](architecture.md) | How the system is built today: modules, request flow, data, security |
| [design/navigation.md](design/navigation.md) | Menu structure, every route (live and planned), moved routes, reference inventory |
| [adr/](adr/) | Architecture decision records, one per significant decision |
| [openapi/](openapi/) | Generated OpenAPI 3 description of `/api/v1/` |
| [runbooks/](runbooks/) | Step-by-step operating procedures |
| [traceability/](traceability/) | Blueprint requirements mapped to code and tests, plus the gap analysis |

## Keeping the docs current

- A change that alters architecture, a module boundary or a cross-cutting concern adds or
  supersedes an ADR (copy [adr/template.md](adr/template.md)).
- A change to the API regenerates `openapi/openapi.yaml`. CI fails if it is stale.
- A change that implements or modifies a blueprint requirement updates its row in
  [traceability/blueprint-traceability.md](traceability/blueprint-traceability.md).
- A new operational procedure gets a runbook.
