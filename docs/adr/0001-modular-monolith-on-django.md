# 0001. Modular monolith on Django

- Status: accepted
- Date: 2026-10-30

## Context

The blueprint calls for a modular monolith first, splitting out services only when scale or team
boundaries justify it. The system already runs on Django and Django REST Framework, and its
modules (registration, clinical, laboratory, departments, finance) share one patient and visit
record.

## Decision

Keep a single Django project. Each module is a Django app under `apps/` with its own models,
views, forms, URLs, templates and tests. Code shared between modules (access control, page base
class, code generation, test factories) lives in `apps.manager`.

Module boundaries:

- An app may import another app's models, but not its views or forms.
- Cross-module behaviour, such as billing pulling items from the clinical modules, goes through a
  named module function (`apps.finance.billing`) rather than ad hoc queries spread across views.
- `apps.api` is a consumer of the other apps. Nothing imports from it.

## Consequences

- One deployable, one database transaction boundary, and simple local development.
- Boundaries are kept by convention and review, not by the runtime. A future ADR can add an
  import-linter contract to CI.
- Extracting a module later (for example laboratory or billing) means replacing its in-process
  calls with API or event calls. The boundary rules above keep those calls few.
