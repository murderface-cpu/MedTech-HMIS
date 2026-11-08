# Architecture overview

## Shape of the system

MedSafe is a **modular monolith**: one Django project and one PostgreSQL database, divided into
apps that each own a clinical or business module. This matches the blueprint's principle of a
modular monolith first, with services extracted only when scale or team boundaries require it.
See [ADR 0001](adr/0001-modular-monolith-on-django.md).

```
 Browser ──► Django (core.urls)
               ├─ server-rendered pages   apps.<module>.views  → templates/<module>/
               ├─ REST API /api/v1/       apps.api             → JSON
               └─ Django admin /dashboard/
                        │
                        ▼
                 PostgreSQL 16
```

## Modules

| App | Responsibility | Pages |
| --- | --- | --- |
| `apps.manager` | Sign-in, password change, staff and titles, module access, visit categories, administration, inventory pages, shared page helpers (`pages.PageView`, `access`, `utils`) | `/`, `/login/`, `/password/`, `/admin/`, `/inventory/` |
| `apps.patients` | Patient registry, next of kin, visits, triage, allergies, clinical notes, diagnoses | `/outpatient/patients/`, `/outpatient/visits/`, `/outpatient/triage/` |
| `apps.doctor` | Consultation workspace, doctors and specialities | `/outpatient/consultation/` |
| `apps.lab` | Test catalogue, requests, results and verification | `/laboratory/` |
| `apps.departments` | Pharmacy (drugs, stock batches, dispensing), cardiology and radiology requests and reports, theatre bookings, dental procedures | `/pharmacy/`, `/diagnostics/cardiology/`, `/diagnostics/radiology/`, `/procedures/theatre/`, `/procedures/dental/` |
| `apps.finance` | Services and pricing, billing, invoices, payments, refunds, expenditure, insurance and corporate accounts | `/accounting/cashier/`, `/accounting/invoices/`, `/accounting/ledger/`, `/accounting/insurance/`, `/accounting/price-lists/` |
| `apps.api` | Versioned REST endpoints used by the patient and doctor workspaces | `/api/v1/` |

Dependency direction: `manager` provides shared building blocks. The clinical apps
(`patients`, `doctor`, `lab`, `departments`) and `finance` depend on it. `api` depends on all of
them, and nothing depends on `api`. Billing pulls billable items from the clinical apps through
`apps.finance.billing`, so the clinical apps do not import finance views.

## Navigation

Pages are grouped into workspaces and sections defined once in `apps.manager.navigation`. That
definition drives the menu, the breadcrumbs and the post-sign-in redirect, and page paths start
with their workspace. Pages not yet built are listed as *Planned*. See
[design/navigation.md](design/navigation.md) and [ADR 0006](adr/0006-workspace-navigation-and-routes.md).

## Request flow

**Pages.** Each page view subclasses `apps.manager.pages.PageView`, which:

1. requires sign-in and membership of the page's module (`ModuleAccessMixin`);
2. renders a template from `templates/<module>/`;
3. sends every POST to a `post_<intent>` method chosen by the form's hidden `intent` field, then
   redirects back to the same tab (post/redirect/get).

**API.** The clinical workspaces (`static/js/patients.js`, `static/js/doctor/main.js`) call the
REST API. The layout renders the API root URL into `<meta name="api-root">`, and
`static/js/requests.js` builds every request from it through `apiUrl()`, so no API path is
hardcoded in JavaScript. See [ADR 0004](adr/0004-api-versioning.md).

## Data

- PostgreSQL 16, configured entirely from environment variables ([ADR 0002](adr/0002-postgresql.md)).
- Human-readable record codes (patient IDs, visit IDs, invoice numbers) are built by
  `apps.manager.utils.build_code` with a hospital prefix derived from `HOSPITAL_NAME`.
- Money is stored as `Decimal`; the display currency comes from `CURRENCY`.
- Every schema change ships as a Django migration. CI fails when models and migrations differ.

## Security

- Session authentication for pages and the API, with CSRF protection on every unsafe request.
- **Module-based access control:** each module is unlocked by membership of the Django group of
  the same name (`apps.manager.access.MODULES`). Superusers have every module. API endpoints
  additionally require at least one module (`HasAnyModuleAccess`). See
  [ADR 0005](adr/0005-session-auth-and-module-access.md).
- Secrets (`DJANGO_KEY`, database password) come only from the environment and are never
  committed.
- Session and CSRF cookies are HTTPS-only when `DEBUG` is off. SSL redirect, HSTS and the
  proxy TLS header are switched on per deployment (`SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`,
  `BEHIND_TLS_PROXY`).

## Configuration

All deployment-specific values are read from `.env` (see `.env.example`). The blueprint's
principle of configuration over code applies: hospital name, currency, time zone, allowed hosts and
origins are not hardcoded.

## What is not built yet

The blueprint targets FHIR R4 interoperability, SHA, eTIMS and M-Pesa integrations, an
event-driven patient journey, MFA and an immutable audit trail, among others. These are tracked in
[traceability/blueprint-traceability.md](traceability/blueprint-traceability.md).
