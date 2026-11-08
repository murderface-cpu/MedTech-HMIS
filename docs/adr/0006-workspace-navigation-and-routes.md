# 0006. Workspace navigation and routes

- Status: accepted
- Date: 2026-10-30

## Context

Navigation was a row of 17 icon buttons, one per page, plus a column of icon buttons for search,
settings, password and sign-out. Paths were flat (`/cashier/`, `/radiology/`, `/doctor/`) and gave
no sense of where a page belongs. Many pages hold several tabs that the menu could not reach. The
blueprint's roadmap adds emergency, inpatient, procurement and reporting modules, and a flat row
cannot hold them.

## Decision

- Define the menu once, in `apps.manager.navigation.WORKSPACES`: workspaces, sections and pages.
  Each page is either live (a URL name plus an optional tab) or planned (a reserved route).
- Render it as a left menu with collapsible workspaces, a page filter (`/`), a planned-pages
  toggle, and the user's account actions in the footer. Below 64rem it becomes a drawer.
- Prefix each page's path with its workspace (`/outpatient/`, `/diagnostics/`, `/procedures/`,
  `/accounting/`, and so on). Keep URL names unchanged so templates and tests need no edits.
- Redirect every moved path permanently, keeping the query string.
- Show planned pages to holders of the module that will own them, greyed out and unlinked.
- Keep the visual identity (blue accent, system font) and add a cooler neutral layer for the menu.

## Consequences

- Adding a page is one entry in `WORKSPACES`. Tests check that every live entry opens and its tab
  exists, and that no planned route is already in use.
- The menu shows the roadmap. When a planned page is built, its route is already reserved and
  documented.
- Old bookmarks and printed links keep working through the 301 redirects. Remove those redirects
  once logs show no hits.
- Routes now encode the workspace. Moving a page between workspaces changes its URL and needs a
  new redirect.
