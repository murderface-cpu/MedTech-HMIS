# 0004. Versioned REST API under `/api/v1/`

- Status: accepted
- Date: 2026-10-30

## Context

The blueprint requires versioned REST endpoints under `/api/v1`, FHIR resources under `/fhir`, and
an OpenAPI description kept in the repository. The API was served from `/api/`, and the
JavaScript hardcoded every path.

## Decision

- Mount the API at `/api/v1/` with the URL namespace `api`. `GET /api/v1/` returns the version and
  the main collection URLs.
- The base layout renders `{% url 'api:root' %}` into `<meta name="api-root">`.
  `static/js/requests.js` exposes `apiUrl(path)`, and every client call uses it.
- Generate `docs/openapi/openapi.yaml` with `manage.py generateschema`. CI regenerates it and fails
  if the committed file differs.
- A breaking change ships as `/api/v2/` alongside v1, never as an in-place change.
- FHIR R4 endpoints, when built, live under `/fhir/` as a separate URLconf and are not mixed into
  `/api/v1/`.

## Consequences

- Moving the API again (a new version or a URL prefix) needs no JavaScript changes.
- Some endpoint names are reused across routes, so the generated schema has duplicate
  operationIds. Tools that need unique IDs require those views to be renamed first.
- Idempotency keys, correlation IDs and the standard error envelope from the blueprint's API
  standards are not implemented yet. See the traceability matrix.
