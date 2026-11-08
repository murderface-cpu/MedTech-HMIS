# 0003. Repository layout and naming

- Status: accepted
- Date: 2026-10-30

## Context

The Django apps sat at the repository root next to upper-case asset folders (`TEMPLATES`,
`STATIC`), an `app_api` package and stale Selenium tests with a committed driver binary. The
blueprint (section 4.1) prescribes a repository with apps, infrastructure and docs kept apart.

## Decision

```
apps/<module>/        Django apps; AppConfig.name is "apps.<module>"
apps/api/             REST API (formerly app_api), URL namespace "api"
core/                 settings and root URLconf
templates/  static/   lower-case asset folders
infra/compose/        local infrastructure
docs/                 adr, openapi, runbooks, traceability
.github/workflows/    CI
```

- Folder names are lower case.
- App labels stay as they were (`manager`, `patients`, ...) so existing migrations, foreign keys
  and database tables are unchanged. The API app had no models, so its label changed to `api`
  without a migration.
- The application administration page is served at `/admin/`, and its templates live in
  `templates/administration/`. The folder is not called `admin/` because Django's own admin
  templates use that name, and project templates take precedence over app templates. Django's
  data-maintenance admin stays at `/dashboard/`.
- Runtime dependencies go in `requirements.txt` and tooling in `requirements-dev.txt`.

## Consequences

- Imports read `from apps.patients import models`.
- The blueprint's `/services`, `/modules` and `/packages` folders are added when the first
  extracted service or shared package exists. Empty placeholders are not created.
