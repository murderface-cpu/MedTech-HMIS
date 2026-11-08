# Testing and CI

## What CI runs

`.github/workflows/ci.yml` runs on every push to `main`/`master` and on every pull request, against
a PostgreSQL 16 service:

| Step | Command |
| --- | --- |
| System checks | `python manage.py check --deploy --fail-level ERROR` |
| Migrations complete | `python manage.py makemigrations --check --dry-run` |
| OpenAPI up to date | regenerate and `diff` against `docs/openapi/openapi.yaml` |
| Tests | `python manage.py test` |

## Run locally

With the database running:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test                 # all apps
python manage.py test apps.finance    # one app
```

The test runner creates and destroys a separate `test_<DATABASE_NAME>` database, so the
`DATABASE_USER` role needs the `CREATEDB` privilege. The Docker image's default superuser has it.

## Writing tests

- Tests live in `apps/<module>/tests.py`.
- Build fixtures with the factories in `apps.manager.testing` (`make_user`, `make_patient`,
  `make_visit`, `make_service`, `make_drug`) instead of repeating setup code.
- Test access as well as behaviour: a user without the module gets a redirect (pages) or a 403
  (API).

## Common failures

| Failure | Fix |
| --- | --- |
| `Migrations for '<app>':` in CI | Run `makemigrations` and commit the new file. |
| OpenAPI diff in CI | Regenerate the schema ([../openapi/README.md](../openapi/README.md)) and commit it. |
| `permission denied to create database` | Grant `CREATEDB` to the database role. |
