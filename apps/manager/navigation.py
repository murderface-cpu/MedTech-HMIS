"""The application menu: workspaces, their sections and the pages in each.

A live page names its URL and, optionally, the tab it opens. A planned page names the route it
will take once built, so staff can see the roadmap in the menu. Both are visible only to holders
of the modules listed against them. docs/design/navigation.md describes the same structure.
"""
from dataclasses import dataclass
from urllib.parse import urlencode

from django.urls import reverse

from apps.manager.access import (
    ADMINISTRATION, CARDIOLOGY, DENTAL, DOCTOR, FINANCE, INVENTORY, LABORATORY, PATIENTS, PHARMACY,
    MODULES, RADIOLOGY, THEATRE, user_modules,
)


@dataclass(frozen=True)
class Page:
    label: str
    modules: tuple
    url_name: str = ""
    tab: str = ""
    planned_route: str = ""
    staff_only: bool = False

    @property
    def planned(self):
        return not self.url_name


@dataclass(frozen=True)
class Section:
    label: str
    pages: tuple


@dataclass(frozen=True)
class Workspace:
    label: str
    icon: str
    sections: tuple


def live(label, url_name, *modules, tab=""):
    return Page(label, modules, url_name=url_name, tab=tab)


def planned(label, route, *modules):
    return Page(label, modules, planned_route=route)


CLINICAL = (PATIENTS, DOCTOR)

WORKSPACES = (
    Workspace("Home", "fa-home", (
        Section("Overview", (
            live("Hospital overview", "manager:home", *MODULES),
        )),
    )),
    Workspace("Outpatient", "fa-user-md", (
        Section("Patient administration", (
            live("Registration", "patients:patients-home", PATIENTS),
            live("Visits and check-in", "patients:patients-visits", PATIENTS),
            live("Appointments", "clinical:appointments", *CLINICAL),
            live("Queue board", "clinical:queue", *CLINICAL),
        )),
        Section("Clinical care", (
            live("Triage", "patients:patients-triage", PATIENTS),
            live("Consultation", "doctor:doctor-home", DOCTOR),
            live("Clinical note templates", "clinical:note-templates", DOCTOR),
        )),
    )),
    Workspace("Emergency", "fa-ambulance", (
        Section("Emergency care", (
            live("Emergency check-in", "clinical:emergency-check-in", *CLINICAL),
            live("Emergency queue", "clinical:emergency-queue", *CLINICAL),
        )),
    )),
    Workspace("Inpatient", "fa-bed", (
        Section("Admission and discharge", (
            live("Admissions", "clinical:admissions", *CLINICAL),
            live("Awaiting admission", "clinical:awaiting-admission", *CLINICAL),
            live("Discharges", "clinical:discharges", *CLINICAL),
        )),
        Section("Ward management", (
            live("Ward board", "clinical:wards", *CLINICAL),
            live("Bed charges", "clinical:bed-charges", *CLINICAL, FINANCE),
        )),
    )),
    Workspace("Laboratory", "fa-flask", (
        Section("Worklist", (
            live("Pending requests", "lab:lab-home", LABORATORY, tab="pending_requests"),
            live("Handled requests", "lab:lab-home", LABORATORY, tab="handled_requests"),
        )),
        Section("Samples", (
            live("Sample collection", "lab:sample-collection", LABORATORY),
            live("Sample tracking", "lab:sample-tracking", LABORATORY),
        )),
        Section("Test catalogue", (
            live("Tests", "lab:lab-home", LABORATORY, tab="test_catalogue"),
            live("Add a test", "lab:lab-home", LABORATORY, tab="add_test"),
        )),
    )),
    Workspace("Imaging and diagnostics", "fa-heartbeat", (
        Section("Radiology", (
            live("Pending examinations", "departments:departments-radiology", RADIOLOGY, tab="pending_examinations"),
            live("Reported", "departments:departments-radiology", RADIOLOGY, tab="completed_examinations"),
            live("Examinations offered", "departments:departments-radiology", RADIOLOGY, tab="department_services"),
            live("Image archive", "departments:image-archive", RADIOLOGY),
        )),
        Section("Cardiology", (
            live("Pending examinations", "departments:departments-cardiology", CARDIOLOGY, tab="pending_examinations"),
            live("Reported", "departments:departments-cardiology", CARDIOLOGY, tab="completed_examinations"),
            live("Examinations offered", "departments:departments-cardiology", CARDIOLOGY, tab="department_services"),
        )),
    )),
    Workspace("Theatre and dental", "fa-scissors", (
        Section("Theatre", (
            live("To book", "departments:departments-theatre", THEATRE, tab="theatre_orders"),
            live("New booking", "departments:departments-theatre", THEATRE, tab="new_booking"),
            live("Scheduled", "departments:departments-theatre", THEATRE, tab="scheduled_bookings"),
            live("History", "departments:departments-theatre", THEATRE, tab="booking_history"),
        )),
        Section("Dental", (
            live("Record a procedure", "departments:departments-dental", DENTAL, tab="dental_patient"),
            live("Recent procedures", "departments:departments-dental", DENTAL, tab="dental_recent"),
        )),
    )),
    Workspace("Pharmacy", "fa-medkit", (
        Section("Dispensing", (
            live("To dispense", "departments:departments-pharmacy", PHARMACY, tab="pending_prescriptions"),
            live("Dispensed", "departments:departments-pharmacy", PHARMACY, tab="issued_prescriptions"),
        )),
        Section("Stock", (
            live("Pharmacy stock", "departments:departments-pharmacy", PHARMACY, tab="pharmacy_stock"),
            live("Short-expiry drugs", "departments:short-expiry", PHARMACY, INVENTORY),
        )),
    )),
    Workspace("Inventory", "fa-cubes", (
        Section("Stores", (
            live("Drugs", "manager:manager-inventory", INVENTORY, tab="drug_list"),
            live("Receive stock", "manager:manager-inventory", INVENTORY, tab="receive_stock"),
            live("Stock received", "manager:manager-inventory", INVENTORY, tab="stock_batches"),
            live("Add a drug", "manager:manager-inventory", INVENTORY, tab="add_drug"),
            live("Stock adjustments", "stores:adjustments", INVENTORY),
        )),
        Section("Procurement", (
            live("Suppliers", "manager:manager-inventory", INVENTORY, tab="suppliers"),
            live("Purchase orders", "stores:purchase-orders", INVENTORY),
            live("Requisitions", "stores:requisitions", INVENTORY, PHARMACY, LABORATORY),
        )),
    )),
    Workspace("Accounting", "fa-calculator", (
        Section("Cashier", (
            live("Pending invoices", "finance:finance-cashier", FINANCE, tab="pending_invoices"),
            live("Receive payment", "finance:finance-cashier", FINANCE, tab="receive_payment"),
            live("Company payments", "finance:finance-cashier", FINANCE, tab="company_payments"),
            live("Record expenditure", "finance:finance-cashier", FINANCE, tab="expenditures"),
            live("Issue a refund", "finance:finance-cashier", FINANCE, tab="refunds"),
            live("M-Pesa payments", "finance:mpesa", FINANCE),
            live("Cashier shifts", "finance:shifts", FINANCE),
        )),
        Section("Billing", (
            live("Invoices", "finance:finance-invoices", FINANCE, tab="all_invoices"),
            live("New invoice", "finance:finance-invoices", FINANCE, tab="new_invoice"),
            live("SHA claims", "finance:claims", FINANCE),
            live("eTIMS submissions", "finance:etims", FINANCE),
        )),
        Section("Insurance and accounts", (
            live("Insurance companies", "finance:finance-insurance", FINANCE, tab="insurance_companies"),
            live("Account companies", "finance:finance-insurance", FINANCE, tab="account_companies"),
            live("Billing types", "finance:finance-insurance", FINANCE, tab="billing_types"),
        )),
        Section("Ledger", (
            live("Income", "finance:finance-finances", FINANCE, tab="income"),
            live("Company income", "finance:finance-finances", FINANCE, tab="company_income"),
            live("Expenditure", "finance:finance-finances", FINANCE, tab="spending"),
            live("Refunds", "finance:finance-finances", FINANCE, tab="refund_list"),
            live("Chart of accounts", "finance:chart-of-accounts", FINANCE),
            live("Bank accounts", "finance:banks", FINANCE),
        )),
        Section("Price lists", (
            live("Services", "finance:finance-pricing", FINANCE, tab="services"),
            live("Laboratory tests", "finance:finance-pricing", FINANCE, tab="lab_prices"),
            live("Drugs", "finance:finance-pricing", FINANCE, tab="drug_prices"),
        )),
    )),
    Workspace("Reports", "fa-bar-chart", (
        Section("Reports", (
            live("Analytics dashboard", "reports:analytics", ADMINISTRATION, FINANCE),
            live("MOH 705 and 717 returns", "reports:moh", ADMINISTRATION),
        )),
    )),
    Workspace("System admin", "fa-cogs", (
        Section("People and access", (
            live("Staff", "manager:manager-admin", ADMINISTRATION, tab="staff_list"),
            live("Register staff", "manager:manager-admin", ADMINISTRATION, tab="register_staff"),
            live("Roles and permissions", "manager:roles", ADMINISTRATION),
            live("Audit log", "manager:audit-log", ADMINISTRATION),
        )),
        Section("Configuration", (
            live("Titles and categories", "manager:manager-admin", ADMINISTRATION, tab="settings"),
            live("Facility locations", "manager:locations", ADMINISTRATION),
            Page("Data maintenance", (), url_name="admin:index", staff_only=True),
        )),
    )),
)


def page_url(page):
    url = reverse(page.url_name)
    return f"{url}?{urlencode({'tab': page.tab})}" if page.tab else url


def can_see(user, page, modules):
    if page.staff_only:
        return user.is_staff
    return any(module in modules for module in page.modules)


def first_page_url(user):
    """The first live page the user may open, or None."""
    modules = user_modules(user)
    for workspace in WORKSPACES:
        for section in workspace.sections:
            for page in section.pages:
                if not page.planned and can_see(user, page, modules):
                    return page_url(page)
    return None


def menu_for(request):
    """The workspaces the signed-in user may see, with the page they are on marked current.

    The current page is the live page whose path is the longest prefix of the request path,
    preferring the one whose tab matches ?tab=, so detail pages light up their parent.
    """
    user = request.user
    if not user.is_authenticated:
        return []
    modules = user_modules(user)
    menu = []
    for workspace in WORKSPACES:
        sections = []
        for section in workspace.sections:
            pages = []
            for page in section.pages:
                if not can_see(user, page, modules):
                    continue
                entry = {"label": page.label, "planned": page.planned, "current": False,
                         "workspace": workspace.label, "section": section.label}
                if page.planned:
                    entry["route"] = page.planned_route
                else:
                    entry.update(url=page_url(page), path=reverse(page.url_name), tab=page.tab)
                pages.append(entry)
            if pages:
                sections.append({"label": section.label, "pages": pages,
                                 "all_planned": all(entry["planned"] for entry in pages)})
        if sections:
            menu.append({"label": workspace.label, "icon": workspace.icon, "sections": sections,
                         "current": False, "all_planned": all(s["all_planned"] for s in sections)})
    mark_current(menu, request.path, request.GET.get("tab", ""))
    return menu


def mark_current(menu, path, tab):
    candidates = [
        (workspace, entry)
        for workspace in menu for section in workspace["sections"] for entry in section["pages"]
        if not entry["planned"] and path.startswith(entry["path"]) and (entry["path"] != "/" or path == "/")
    ]
    if not candidates:
        return
    longest = max(len(entry["path"]) for _, entry in candidates)
    candidates = [(workspace, entry) for workspace, entry in candidates if len(entry["path"]) == longest]
    workspace, entry = next(((w, e) for w, e in candidates if tab and e["tab"] == tab), candidates[0])
    entry["current"] = workspace["current"] = True
    entry["exact"] = path == entry["path"]


def current_page(menu):
    for workspace in menu:
        for section in workspace["sections"]:
            for entry in section["pages"]:
                if entry["current"]:
                    return entry
    return None
