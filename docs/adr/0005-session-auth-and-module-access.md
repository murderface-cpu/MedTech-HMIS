# 0005. Session authentication and module-based access

- Status: accepted
- Date: 2026-10-30

## Context

Staff work in server-rendered pages, and the same browser session calls the API. The blueprint
targets OIDC single sign-on with MFA, RBAC plus ABAC, and break-glass access. Those need an
identity provider, which is not in place yet.

## Decision

- Use Django session authentication for pages and the API. CSRF protection applies to every unsafe
  request.
- Grant access per module. Each name in `apps.manager.access.MODULES` is a Django group, and a
  user can open a module's pages only as a member of its group. Superusers have every module.
  Navigation shows only the modules a user holds.
- API endpoints require an authenticated user with at least one module (`HasAnyModuleAccess`).
- Administrators manage staff accounts and module membership from `/admin/`.

## Consequences

- Access control works today with no external dependency.
- Module access is coarse. It does not yet restrict by patient, department or care relationship
  (ABAC), and there is no break-glass flow or MFA. Moving to OIDC means adding an authentication
  backend; the module groups can carry over as role claims.
