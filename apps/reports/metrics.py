"""Figures for the overview and the analytics dashboard, computed from the records."""
import datetime
import math
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum, Min
from django.db.models.functions import Lower, Trim, TruncDate
from django.utils import timezone

from apps.clinical import models as ClinicalModels
from apps.departments import models as DepartmentModels
from apps.finance import models as FinanceModels
from apps.lab import models as LabModels
from apps.patients import models as PatientModels

ZERO = Decimal("0")
LINE_TOTAL = ExpressionWrapper(F("unit_price") * F("quantity"), output_field=DecimalField(max_digits=16, decimal_places=2))

STREAMS = (
    ("visitservice", "Consultations and procedures"),
    ("labtest", "Laboratory"),
    ("prescription", "Pharmacy"),
    ("deptrequest", "Imaging and cardiology"),
    ("dental", "Dental"),
    ("bedcharge", "Inpatient bed days"),
    ("", "Other charges"),
)


def day_range(start, end):
    days = (end - start).days
    return [start + datetime.timedelta(days=offset) for offset in range(days + 1)]


def local_bounds(start, end):
    """Aware datetimes covering the local dates start..end inclusive."""
    tz = timezone.get_current_timezone()
    return (timezone.make_aware(datetime.datetime.combine(start, datetime.time.min), tz),
            timezone.make_aware(datetime.datetime.combine(end + datetime.timedelta(days=1), datetime.time.min), tz))


def nice_ceiling(value):
    """The next clean axis maximum above `value`: 1, 2, 2.5, 5 or 10 times a power of ten."""
    if value <= 0:
        return 1
    exponent = math.floor(math.log10(value))
    for step in (1, 2, 2.5, 5, 10):
        candidate = step * 10 ** exponent
        if candidate >= value:
            return candidate
    return 10 ** (exponent + 1)


def compact(number):
    number = float(number)
    if abs(number) >= 1_000_000:
        return f"{number / 1_000_000:.1f}M".replace(".0M", "M")
    if abs(number) >= 10_000:
        return f"{number / 1_000:.0f}K"
    return f"{number:,.0f}"


def column_chart(series, money=False, label_every=None):
    """Columns for a single series of (date, value). Heights are percentages of a clean axis maximum."""
    peak = max((float(value) for _, value in series), default=0)
    top = nice_ceiling(peak)
    ticks = [{"value": compact(top * share), "at": share * 100} for share in (0, 0.5, 1)]
    count = len(series)
    every = label_every or (1 if count <= 10 else 7 if count > 45 else 5 if count > 20 else 2)
    today = timezone.localdate()
    columns = []
    for index, (day, value) in enumerate(series):
        shown = f"{float(value):,.2f}" if money else f"{float(value):,.0f}"
        columns.append({
            "height": round(float(value) * 100 / top, 2) if top else 0,
            "value": shown,
            "label": "Today" if day == today else day.strftime("%a %d %b"),
            "tick": day.strftime("%d %b") if (count - 1 - index) % every == 0 else "",
            "is_today": day == today,
            "empty": not value,
        })
    total = sum((Decimal(str(value)) for _, value in series), ZERO)
    return {"columns": columns, "ticks": ticks, "total": total, "average": (total / count) if count else ZERO,
            "peak": max(series, key=lambda item: item[1]) if series else None}


def bar_list(rows, money=False, limit=None):
    """Horizontal bars for (label, value[, link]) rows, sorted largest first."""
    rows = sorted(rows, key=lambda row: row[1], reverse=True)
    if limit:
        rows = rows[:limit]
    peak = max((float(row[1]) for row in rows), default=0)
    total = sum((float(row[1]) for row in rows), 0)
    return {
        "rows": [{"label": row[0], "value": f"{float(row[1]):,.2f}" if money else f"{float(row[1]):,.0f}",
                  "width": round(float(row[1]) * 100 / peak, 2) if peak else 0,
                  "share": round(float(row[1]) * 100 / total) if total else 0,
                  "link": row[2] if len(row) > 2 else ""} for row in rows],
        "total": total,
    }


# ------------------------------------------------------------------ series

def visits_per_day(start, end):
    low, high = local_bounds(start, end)
    counts = dict(PatientModels.Visit.objects.filter(visit_date__gte=low, visit_date__lt=high)
                  .annotate(day=TruncDate("visit_date")).values_list("day").annotate(total=Count("id")))
    return [(day, counts.get(day, 0)) for day in day_range(start, end)]


def money_received_per_day(start, end):
    low, high = local_bounds(start, end)
    patient = dict(FinanceModels.Payment.objects.filter(received_on__gte=low, received_on__lt=high)
                   .annotate(day=TruncDate("received_on")).values_list("day").annotate(total=Sum("amount")))
    company = dict(FinanceModels.CompanyPayment.objects.filter(received_on__gte=low, received_on__lt=high)
                   .annotate(day=TruncDate("received_on")).values_list("day").annotate(total=Sum("amount")))
    return [(day, (patient.get(day) or ZERO) + (company.get(day) or ZERO)) for day in day_range(start, end)]


def billed_by_stream(start, end):
    items = (FinanceModels.InvoiceItem.objects.filter(invoice__issued_on__gte=start, invoice__issued_on__lte=end)
             .exclude(invoice__status="cancelled").annotate(line=LINE_TOTAL).values_list("source", "line"))
    totals = {prefix: ZERO for prefix, _ in STREAMS}
    for source, line in items:
        prefix = (source or "").split(":", 1)[0]
        totals[prefix if prefix in totals else ""] += line or ZERO
    return [(label, totals[prefix]) for prefix, label in STREAMS if totals[prefix]]


def payer_mix(start, end):
    labels = dict(FinanceModels.BillingType.KindChoices)
    labels = {"cash": "Patients (cash and M-Pesa)", "insurance": "Insurance and SHA", "account": "Account companies"}
    items = (FinanceModels.InvoiceItem.objects.filter(invoice__issued_on__gte=start, invoice__issued_on__lte=end)
             .exclude(invoice__status="cancelled").annotate(line=LINE_TOTAL)
             .values_list("invoice__billing_type__kind", "invoice__insurance_company_id", "invoice__account_company_id", "line"))
    totals = {key: ZERO for key in labels}
    for kind, insurer, account, line in items:
        kind = "insurance" if insurer else "account" if account else (kind if kind in totals else "cash")
        totals[kind] += line or ZERO
    return [(labels[key], value) for key, value in totals.items() if value]


def top_diagnoses(start, end, limit=8):
    low, high = local_bounds(start, end)
    rows = (PatientModels.Diagnosis.objects.filter(created_on__gte=low, created_on__lt=high)
            .annotate(name=Lower(Trim("diagnosis"))).values("name")
            .annotate(total=Count("id"), wording=Min(Trim("diagnosis"))).order_by("-total")[:limit])
    return [(row["wording"][:1].upper() + row["wording"][1:], row["total"]) for row in rows]


def top_lab_tests(start, end, limit=8):
    low, high = local_bounds(start, end)
    rows = (LabModels.AssignedTest.objects.filter(request__created_on__gte=low, request__created_on__lt=high)
            .values("test__name").annotate(total=Count("id")).order_by("-total")[:limit])
    return [(row["test__name"], row["total"]) for row in rows]


def workload(start, end):
    low, high = local_bounds(start, end)
    return [
        ("Outpatient visits", PatientModels.Visit.objects.filter(visit_date__gte=low, visit_date__lt=high).count()),
        ("Lab tests", LabModels.AssignedTest.objects.filter(request__created_on__gte=low, request__created_on__lt=high).count()),
        ("Prescriptions", DepartmentModels.Prescription.objects.filter(created_on__gte=low, created_on__lt=high).count()),
        ("Imaging and cardiology", DepartmentModels.DepartmentRequest.objects.filter(created_on__gte=low, created_on__lt=high).count()),
        ("Emergency arrivals", ClinicalModels.EmergencyCase.objects.filter(arrived_on__gte=low, arrived_on__lt=high).count()),
        ("Admissions", ClinicalModels.Admission.objects.filter(admitted_on__gte=low, admitted_on__lt=high).count()),
        ("Theatre operations", DepartmentModels.TheatreBooking.objects.filter(scheduled_for__gte=low, scheduled_for__lt=high, status="completed").count()),
        ("Dental procedures", DepartmentModels.DentalProcedure.objects.filter(performed_on__gte=low, performed_on__lt=high).count()),
    ]


def patients_by_age_and_gender(start, end):
    low, high = local_bounds(start, end)
    bands = (("Under 5", 0, 4), ("5 to 14", 5, 14), ("15 to 24", 15, 24), ("25 to 49", 25, 49), ("50 to 64", 50, 64), ("65 and over", 65, 200))
    visits = PatientModels.Visit.objects.filter(visit_date__gte=low, visit_date__lt=high).values_list("patient__age", "patient__gender")
    table = {label: {"Male": 0, "Female": 0} for label, _, _ in bands}
    for age, gender in visits:
        age = age or 0
        for label, low_age, high_age in bands:
            if low_age <= age <= high_age:
                table[label][gender if gender in ("Male", "Female") else "Female"] += 1
                break
    peak = max((max(counts.values()) for counts in table.values()), default=0) or 1
    return [{"label": label, "male": counts["Male"], "female": counts["Female"],
             "male_width": round(counts["Male"] * 100 / peak, 2), "female_width": round(counts["Female"] * 100 / peak, 2)}
            for label, counts in table.items()]


def new_patients(start, end):
    low, high = local_bounds(start, end)
    return PatientModels.Patient.objects.filter(created_on__gte=low, created_on__lt=high).count()


def emergency_wait(start, end):
    low, high = local_bounds(start, end)
    cases = ClinicalModels.EmergencyCase.objects.filter(arrived_on__gte=low, arrived_on__lt=high, seen_on__isnull=False)
    waits = [(case.seen_on - case.arrived_on).total_seconds() / 60 for case in cases.only("arrived_on", "seen_on")]
    return round(sum(waits) / len(waits)) if waits else None


# ------------------------------------------------------------------ now

def occupancy():
    wards = []
    for ward in ClinicalModels.Ward.objects.filter(is_active=True).annotate(
            total=Count("beds"), occupied=Count("beds", filter=Q(beds__status="occupied"))).order_by("name"):
        share = round(ward.occupied * 100 / ward.total) if ward.total else 0
        wards.append({"ward": ward, "occupied": ward.occupied, "total": ward.total, "share": share,
                      "level": "full" if share >= 100 else "high" if share >= 85 else "normal"})
    occupied = sum(item["occupied"] for item in wards)
    total = sum(item["total"] for item in wards)
    return {"wards": wards, "occupied": occupied, "total": total, "share": round(occupied * 100 / total) if total else 0}


def outstanding_on_invoices():
    total = ZERO
    for invoice in FinanceModels.Invoice.objects.filter(status="pending").prefetch_related("items", "payments", "refunds"):
        line_total = sum((item.unit_price * item.quantity for item in invoice.items.all()), ZERO)
        paid = sum((payment.amount for payment in invoice.payments.all()), ZERO)
        refunded = sum((refund.amount for refund in invoice.refunds.all()), ZERO)
        total += max(line_total - invoice.company_covered, ZERO) - paid + refunded
    return total
