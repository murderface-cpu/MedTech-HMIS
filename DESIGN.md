# Design

MedSafe follows the category standard for clinical systems: a white, blue-accent, worklist-first
interface in the conventions clinicians already know from Epic-class EHRs and Unumed. It has no
novelty styling. The quality comes from precision: legible type, consistent controls, honest
empty states and calm colour. Product context lives in [PRODUCT.md](PRODUCT.md).

## Sources of truth

| File | Owns |
| --- | --- |
| `static/css/system.css` | Tokens and every shared component. It loads last, so it wins. |
| `static/css/shell.css` | The app shell: left navigation, top bar, drawer on small screens. |
| `static/css/auth.css` | Sign-in page (repeats the tokens it needs; no shell). |
| `templates/utils/layout.html` | Page frame: breadcrumb, `h1`, tab row, content. |
| `apps/manager/navigation.py` | Workspaces, sections and pages, including Planned pages. |
| `apps/manager/templatetags/hmis.py` | `tone` (status to tone class), `money`, `whole`, `compact`, `percent_of`, `get_item`. |
| `templates/reports/_columns.html`, `_bars.html` | The two chart partials. Use them; don't draw charts per page. |

`styles.css`, `components.css` and `app.css` are legacy. Don't add to them; move rules into
`system.css` when you touch them.

## Tokens

| Role | Token | Value |
| --- | --- | --- |
| Page ground | `--c-ground` | `#F4F6F8` |
| Panels, dialogs | `--c-surface` | `#FFFFFF` |
| Table heads, dialog footers | `--c-subtle` | `#F9FAFB` |
| Hairlines / control borders | `--c-line` / `--c-line-strong` | `#E4E7EC` / `#D0D5DD` |
| Text: primary / secondary / muted | `--c-ink` / `--c-ink-2` / `--c-muted` | `#101828` / `#344054` / `#475467` |
| Primary action, link, selection | `--c-primary` (hover `--c-primary-hover`) | `#1F5BD8` (`#194CB5`) |
| Success / warning / danger | `--c-success` / `--c-warning` / `--c-danger` | `#067647` / `#B54708` / `#B42318` |

Blue is reserved for things you can act on and for the current selection. Status colours appear
only in status pills, errors and confirmations, always with a text label (never colour alone).

Type uses the system UI stack (`--font-ui`, Segoe UI on the hospital's Windows machines) at a
16px base with 1.5 line height and tabular figures for amounts. Page titles are 1.625rem/650,
dialog titles 1.25rem/650, and section titles 1rem/650. No webfonts are downloaded.

Shape: controls are 2.5rem tall with a 6px radius, panels have an 8px radius, and there is one
overlay shadow (dialogs only). Panels use hairline borders, not shadows.

## Components

- **Page frame**: breadcrumb shows Workspace / Section, and the `h1` names the page. On tabbed
  pages the `h1` follows the active tab.
- **Tabs** (`.section-togglers`): underline tabs, active one in blue with `is-active` and
  `aria-selected`. Page actions sit at the end of the tab row. Counts go in brackets:
  "Pending requests (3)".
- **Buttons**: neutral outline by default. `.accented` and form submits are primary blue. Submits
  inside `form[data-confirm]` are danger red. Press feedback is `scale(0.98)`.
- **Tables** (`table.display`, DataTables): white panel, subtle head, search at the top right,
  pagination at the bottom. Empty copy comes from `data-empty` on the table and says what will
  appear and how ("No lab requests are waiting. New requests appear here when a doctor orders
  tests.").
- **Dialogs** (`.modal`, opened by `modals.js`): centred, `role="dialog"`, a title and close
  button in the header, Cancel and a primary Save in the footer. A dimmed backdrop blocks the page.
  Escape closes. Focus moves to the first field and returns to the trigger on close. Entry is
  180–220ms ease-out with `@starting-style`.
- **Status pills, totals, summary strip, empty state, flash messages**: see `system.css`.
- **Tones** (`tone-ok`, `tone-warn`, `tone-bad`, `tone-info`, `tone-neutral`): the one way to
  colour a status. Pick it with the `tone` filter (`{{ claim.status|tone }}`) so a word such as
  "rejected" is red on every page. The pill always carries the word.
- **Stat strip** (`.stat-strip` > `.stat`): a row of plain figures (label, value, optional note
  with `is-up` / `is-down`). Figures sit on the page ground, not in cards. Don't build hero
  numbers or gradient tiles.
- **Panels** (`.panel-grid` > `.panel`, `.panel-head`): white hairline panels holding a worklist
  extract or a chart. `is-full` spans the row. A panel ends with one text link to the full page.
- **Charts**: one series per chart, in `--c-primary` blue. Columns (`.col-chart`, one `li` per day
  with `--h`) for change over time; bars (`.meter-list`) for ranking. Every column is focusable
  with a label, and every chart has a "Show as a table" `<details>`. The age and sex pyramid is
  the only two-colour chart: female `#E0622C`, male `--c-primary`, with a legend. Both colours
  passed the palette validator against white.
- **Segmented control** (`.segmented`): radio buttons styled as a joined group, for a short
  choice such as the report period. `data-auto-submit` sends the form on change.
- **Row popover** (`.row-popover`, a `<details>`): small actions on a worklist row (assign a bed,
  match a payment). One is open at a time; Escape or a click outside closes it.
- **Queue board** (`.queue-board`): one column per step of the visit journey, each with a count.
- **Acuity** (`.acuity-red` to `.acuity-green`, `.acuity-tag`, `.acuity-picker`): emergency
  triage colours. They always show the acuity word and the target time. They are not reused
  for anything else.
- **Ward board** (`.ward-panel`): one panel per ward with a bed grid. Bed status shows as a tone
  and a word.
- **Matrix** (`.matrix`): roles against modules, a checkbox per cell, with sticky headings.
- **MOH tables** (`.moh-table`): wide day-by-day tables that scroll sideways with a sticky first
  column. Zero rows are muted, not hidden, because the return lists every condition.
- **Auto refresh** (`data-auto-refresh="60"`): queues reload themselves, but not while the user
  is typing or has a popover open.

## Copy

Use sentence case everywhere: titles, tabs, buttons, labels and column headings ("Register
patient", "Created at"). Keep acronyms (ID, KES, SHA, M-Pesa). Show amounts in KES with
tabular figures. Error and empty messages say what happened and what to do next.

## Motion

Motion is only for dialogs entering, press feedback and chart tooltips appearing. Never animate navigation, tab
switches or anything triggered from the keyboard. `prefers-reduced-motion` removes transitions.

## Accessibility

Target WCAG 2.2 AA with large text. Body text is at least 16px, and all text/background pairs
above meet 4.5:1. Every control shows a visible `:focus-visible` ring. Icon-only buttons have an
`aria-label`. Touch targets are at least 40px.
