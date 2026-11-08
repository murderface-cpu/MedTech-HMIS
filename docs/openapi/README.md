# API reference

[openapi.yaml](openapi.yaml) is the OpenAPI 3 description of `/api/v1/`. It is generated from the
code, so do not edit it by hand.

## Regenerate

```bash
python manage.py generateschema --format openapi --title "MedSafe HMIS API" --api_version v1 --file docs/openapi/openapi.yaml
```

Commit the result with the API change. CI runs the same command and fails if the committed file
differs.

## Conventions

- Authentication: Django session cookie. Unsafe methods need the `X-CSRFToken` header.
- Authorisation: an authenticated user with at least one module (see ADR 0005).
- List endpoints are paginated (`count`, `next`, `previous`, `results`) and accept `page` and
  `page_size`.
- Errors use DRF's default shape: `{"detail": "..."}` or `{"field": ["message"]}`.

The generator warns about duplicate operationIds because several views share a name across
routes. Rename those views before using code generators that need unique IDs.
