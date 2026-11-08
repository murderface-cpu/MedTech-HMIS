# MedSafe HMIS

MedSafe is a Health Management Information System for outpatient and departmental care: patient
registration, visits, triage, consultation, laboratory, radiology, cardiology, pharmacy, theatre,
dental, inventory, billing, insurance and administration.

It is a Django modular monolith on PostgreSQL.

The target architecture, roadmap and delivery plan are in the *HMIS Master Blueprint*. See
[docs/](docs/README.md) for how this codebase maps onto it.

## Repository layout

```
apps/                 Django apps, one per bounded module
  api/                versioned REST API (/api/v1/)
  manager/            authentication, staff, module access, administration, inventory pages
  patients/           registration, next of kin, visits, triage, clinical notes
  doctor/             consultation workspace
  lab/                laboratory catalogue, requests and results
  departments/        pharmacy, cardiology, radiology, theatre, dental
  finance/            services, pricing, cashier, invoices, payments, insurance
core/                 project settings, root URLs, WSGI/ASGI
templates/            server-rendered pages, grouped by module
static/               CSS, JavaScript and images
infra/compose/        local infrastructure (PostgreSQL)
docs/                 architecture, ADRs, OpenAPI, runbooks, traceability
.github/workflows/    continuous integration
```

## Quick start

Requirements: Python 3.11, Docker Desktop.

```bash
cp .env.example .env            # then set DJANGO_KEY and DATABASE_PASSWORD
docker compose --env-file .env -f infra/compose/docker-compose.yml up -d
python -m venv .venv
.venv/Scripts/activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000/ and sign in. The full walkthrough is in
[docs/runbooks/local-development.md](docs/runbooks/local-development.md).

## Common commands

| Task | Command |
| --- | --- |
| Run the tests | `python manage.py test` |
| Check for missing migrations | `python manage.py makemigrations --check --dry-run` |
| Regenerate the OpenAPI schema | see [docs/openapi/README.md](docs/openapi/README.md) |
| Django admin (data maintenance) | http://127.0.0.1:8000/dashboard/ |
| Application administration | http://127.0.0.1:8000/admin/ |

## Documentation

- [Architecture overview](docs/architecture.md)
- [Architecture decision records](docs/adr/)
- [API reference (OpenAPI)](docs/openapi/)
- [Runbooks](docs/runbooks/)
- [Blueprint traceability and gap analysis](docs/traceability/blueprint-traceability.md)
