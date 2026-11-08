# Blueprint traceability

This matrix maps the HMIS Master Blueprint's modules and cross-cutting requirements to the current
code and tests. Update a row whenever a change implements or alters that requirement.

Status: **Done** (meets the blueprint's intent), **Partial** (a working base exists, but blueprint
scope is missing), **Gap** (not started).

## Functional modules

| ID | Module | Status | Where | Tests | Gap against the blueprint |
| --- | --- | --- | --- | --- | --- |
| REG | Registration | Partial | Django `apps.patients`; offline: `backend/app/sync/commands.py` (`patient.*`), `frontend/app/pages/front-desk/` | `apps/api/tests.py`, `backend/tests/test_sync.py` | New stack has device-made UUIDs, server MRNs, external-identifier table, opaque QR token and duplicate review with merge. Missing: next of kin, IPRS/SHA lookups, search benchmark at scale |
| CSH | Cashier / front-desk payments | Partial | `apps.finance` CashierView, Payment | `apps/finance/tests.py` | M-Pesa Daraja STK push and callbacks, eTIMS receipts |
| QUE | Queue management | Partial | Offline stack: `journey_event` drives visit stage; queues per workstation (`frontend/app/composables/useQueue.ts`) | `backend/tests/test_sync.py` | Queue tokens and display boards, service points beyond the four workstations |
| TRG | Triage | Done | Django `apps.patients` Triage; offline: `frontend/app/pages/triage/`, NEWS2 in `backend/app/domain/news2.py` and `frontend/app/utils/news2.ts` | `apps/api/tests.py`, `backend/tests/test_news2.py`, `frontend/tests/news2.test.ts` (shared cases in `shared/news2-cases.json`) | PEWS for under-16s; FHIR Observation mapping |
| CON | Consultation | Partial | Django `apps.doctor`; offline: `frontend/app/pages/consultation/`, append-only notes, ICD-10 diagnoses | `apps/api/tests.py`, `backend/tests/test_sync.py` | Terminology service (ICD-11), FHIR Encounter/Condition, lab and imaging orders, decision support |
| DEN | Dental | Partial | `apps.departments` DentalProcedure, `/procedures/dental/` | `apps/departments/tests.py` | Odontogram, treatment plans |
| EYE / ORT / ENT | Eye, orthopaedics, ENT clinics | Gap | Eye services can be ordered as a service category | | Specialty templates and workflows |
| DIA | Diagnostics (cardiology) | Partial | `apps.departments` DepartmentRequest, `/diagnostics/cardiology/` | `apps/departments/tests.py` | Device and DICOM integration |
| LAB | Laboratory | Partial | `apps.lab`, `/laboratory/` | `apps/lab/tests.py` | Sample tracking and barcodes, analyser integration, LOINC codes, FHIR DiagnosticReport |
| RAD | Radiology | Partial | `apps.departments` DepartmentRequest, `/diagnostics/radiology/` | `apps/departments/tests.py` | PACS/DICOM, structured reporting |
| PHM | Pharmacy | Partial | Django `apps.departments`; offline: `frontend/app/pages/pharmacy/`, server-side FEFO dispensing and allergy re-check | `apps/departments/tests.py`, `backend/tests/test_sync.py` | Drug interaction checks, FHIR MedicationRequest/Dispense, payment before dispense |
| STR | Stores / inventory | Partial | `apps.departments` StockBatch, Supplier, `/inventory/` | `apps/manager/tests.py` | Purchase orders, goods received notes, inter-store transfers, expiry alerts |
| INP | Inpatient | Gap | Menu entries reserved under `/inpatient/` | | Admissions, wards and beds, nursing charts, discharge |
| MNU | Menu / dietary | Gap | | | |
| BIL | Billing | Partial | `apps.finance` billing, invoices, `/accounting/invoices/`, `/accounting/price-lists/` | `apps/finance/tests.py` | KRA eTIMS invoice submission, price lists per payer |
| CLM | Insurance claims | Partial | `apps.finance` insurance and corporate accounts, `/accounting/insurance/` | `apps/finance/tests.py` | SHA claim submission, pre-authorisation, claim status tracking |
| HRM | Human resources | Partial | `apps.manager` Staff, StaffTitle, `/admin/` | `apps/manager/tests.py` | Leave, rosters, contracts, licensing renewals |
| PAY | Payroll | Gap | | | |
| RPT | Reporting | Partial | `/accounting/ledger/` summaries | `apps/finance/tests.py` | KHIS/DHIS2 reports (MOH 705/717), operational dashboards |
| AI | Analytics and AI | Gap | | | |

## Cross-cutting requirements

| Area | Status | Current state | Gap |
| --- | --- | --- | --- |
| Modular monolith | Done | ADR 0001 | Automated boundary checks (import-linter) |
| Repository structure (4.1) | Partial | ADR 0003: `apps/`, `infra/`, `docs/`, CI | `services/`, `packages/`, IaC and pipelines when needed |
| Versioned REST API `/api/v1` | Done | ADR 0004 | |
| OpenAPI in repo | Done | `docs/openapi/openapi.yaml`, checked in CI | Unique operationIds |
| FHIR R4 under `/fhir` | Gap | | Patient, Encounter, Observation, Condition, MedicationRequest, DiagnosticReport, Claim mappings |
| Idempotency keys, correlation IDs | Partial | New stack: every sync op is idempotent by op id (`sync_op`); `X-Correlation-ID` middleware in `backend/app/main.py` | `Idempotency-Key` on non-sync endpoints; Django app |
| Journey events | Partial | New stack: append-only `journey_event` with device time, stage follows latest device time (ADR 0008) | Wait-time analytics on top; Django app |
| Integrations via outbox | Gap | | Outbox table and worker for SHA, eTIMS, M-Pesa, SMS |
| Authentication | Partial | Django: session auth (ADR 0005). New stack: JWT access/refresh, offline unlock for 7 days (ADR 0007, 0008) | OIDC SSO, MFA |
| Authorisation | Partial | Module groups | ABAC (care relationship, department), break-glass with review |
| Audit trail | Partial | New stack: hash-chained `audit_event` for every write, sign-in and history read (`backend/app/core/audit.py`) | Reads served from the device's local copy aren't audited centrally; Django app |
| Secrets via environment | Done | `.env`, `.env.example` | Secret manager in production |
| Transport security | Partial | Secure cookies outside DEBUG; HSTS and SSL redirect via env | TLS termination and HSTS in deployed environments |
| Configuration over code | Done | Hospital, currency, time zone, hosts from env | Per-facility configuration in the database |
| Localisation (English/Swahili, KES, EAT) | Partial | Currency and time zone configurable; `.env.example` defaults to KES / Africa/Nairobi | Swahili translations (`gettext`), locale formatting |
| Offline tolerance | Partial | Front desk, triage, consultation and pharmacy work offline (ADR 0008): PWA cache, IndexedDB, command outbox, pull cursor | Local store encryption, pruning of aged-out visits, packaged edge node, cashier offline |
| Availability 99.5%, RPO 15 min / RTO 4 h | Gap | | Production hosting, WAL archiving, restore drills |
| CI: lint, tests, scans | Partial | Django checks, migrations, OpenAPI, tests; backend ruff, migrations, pytest; frontend type check, Vitest, PWA build | Dependency and SAST scans, coverage gate |
| Reversible migrations | Partial | Rule in the database runbook | CI check that migrations reverse |
| Feature flags | Gap | | |
| Navigation and routes | Done | Workspace menu with planned pages, workspace-prefixed routes, 301s from old paths ([design/navigation.md](../design/navigation.md)) | |
| Observability | Gap | | Structured logs, metrics, error tracking |

## Suggested order of work

Based on dependencies in the gaps above:

1. **Foundation:** audit trail, correlation IDs, linting and security scans in CI, structured
   logging. Everything after builds on these.
2. **Identity:** UUID patient identifiers and an external-identifier table (needs a data
   migration), then duplicate detection.
3. **Journey and queues:** the `journey_event` table, then queue management on top of it.
4. **Integrations:** the outbox, then M-Pesa, eTIMS and SHA claims in turn.
5. **Interoperability:** FHIR R4 read endpoints for the resources above.
6. **Inpatient, stores procurement, HR and payroll, reporting.**
