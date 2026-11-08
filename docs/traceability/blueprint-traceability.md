# Blueprint traceability

This matrix maps the HMIS Master Blueprint's modules and cross-cutting requirements to the current
code and tests. Update a row whenever a change implements or alters that requirement.

Status: **Done** (meets the blueprint's intent), **Partial** (a working base exists, but blueprint
scope is missing), **Gap** (not started).

## Functional modules

| ID | Module | Status | Where | Tests | Gap against the blueprint |
| --- | --- | --- | --- | --- | --- |
| REG | Registration | Partial | Django `apps.patients` | `apps/api/tests.py` | UUID identifiers, external-identifier table, duplicate detection, IPRS/SHA lookups, search benchmark at scale |
| CSH | Cashier / front-desk payments | Partial | `apps.finance` CashierView, Payment | `apps/finance/tests.py` | M-Pesa Daraja STK push and callbacks, eTIMS receipts |
| QUE | Queue management | Gap | | | Journey-driven visit stage, queues per service point, queue tokens and display boards |
| TRG | Triage | Partial | Django `apps.patients` Triage | `apps/api/tests.py` | NEWS2 early-warning score, PEWS for under-16s, FHIR Observation mapping |
| CON | Consultation | Partial | Django `apps.doctor` | `apps/api/tests.py` | Terminology service (ICD-11), FHIR Encounter/Condition, lab and imaging orders, decision support |
| DEN | Dental | Partial | `apps.departments` DentalProcedure, `/procedures/dental/` | `apps/departments/tests.py` | Odontogram, treatment plans |
| EYE / ORT / ENT | Eye, orthopaedics, ENT clinics | Gap | Eye services can be ordered as a service category | | Specialty templates and workflows |
| DIA | Diagnostics (cardiology) | Partial | `apps.departments` DepartmentRequest, `/diagnostics/cardiology/` | `apps/departments/tests.py` | Device and DICOM integration |
| LAB | Laboratory | Partial | `apps.lab`, `/laboratory/` | `apps/lab/tests.py` | Sample tracking and barcodes, analyser integration, LOINC codes, FHIR DiagnosticReport |
| RAD | Radiology | Partial | `apps.departments` DepartmentRequest, `/diagnostics/radiology/` | `apps/departments/tests.py` | PACS/DICOM, structured reporting |
| PHM | Pharmacy | Partial | Django `apps.departments` | `apps/departments/tests.py` | Drug interaction checks, FHIR MedicationRequest/Dispense, payment before dispense |
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
| Idempotency keys, correlation IDs | Gap | | `Idempotency-Key` on unsafe endpoints, `X-Correlation-ID` middleware |
| Journey events | Gap | | Append-only `journey_event` table, wait-time analytics on top |
| Integrations via outbox | Gap | | Outbox table and worker for SHA, eTIMS, M-Pesa, SMS |
| Authentication | Partial | Session auth (ADR 0005) | OIDC SSO, MFA |
| Authorisation | Partial | Module groups | ABAC (care relationship, department), break-glass with review |
| Audit trail | Gap | | Tamper-evident audit events for every write, sign-in and record read |
| Secrets via environment | Done | `.env`, `.env.example` | Secret manager in production |
| Transport security | Partial | Secure cookies outside DEBUG; HSTS and SSL redirect via env | TLS termination and HSTS in deployed environments |
| Configuration over code | Done | Hospital, currency, time zone, hosts from env | Per-facility configuration in the database |
| Localisation (English/Swahili, KES, EAT) | Partial | Currency and time zone configurable; `.env.example` defaults to KES / Africa/Nairobi | Swahili translations (`gettext`), locale formatting |
| Offline tolerance | Gap | | Front desk, triage, consultation, pharmacy and cashier keep working without the internet |
| Availability 99.5%, RPO 15 min / RTO 4 h | Gap | | Production hosting, WAL archiving, restore drills |
| CI: lint, tests, scans | Partial | Django checks, migrations, OpenAPI, tests | Linting, dependency and SAST scans, coverage gate |
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
