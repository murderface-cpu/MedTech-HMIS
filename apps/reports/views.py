import csv
import datetime
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views import View

from apps.clinical import models as ClinicalModels
from apps.clinical.views import active_visits_by_stage
from apps.departments import models as DepartmentModels
from apps.finance import models as FinanceModels
from apps.lab import models as LabModels
from apps.manager.access import (
    ADMINISTRATION, CARDIOLOGY, DOCTOR, FINANCE, INVENTORY, LABORATORY, PATIENTS, PHARMACY, RADIOLOGY, user_modules,
)
from apps.manager.pages import PageView
from apps.patients import models as PatientModels
from apps.reports import metrics, moh


def view_title(title):
    return f"{settings.APPLICATION_NAME} - {title}"


def delta(today_value, average):
    """Today against the daily average of the previous seven days, as words."""
    if average is None:
        return None
    difference = round(float(today_value) - float(average))
    if difference == 0:
        return {"text": "Level with the 7-day average", "direction": "level"}
    return {"text": f"{abs(difference):,} {'above' if difference > 0 else 'below'} the 7-day average",
            "direction": "up" if difference > 0 else "down"}


class OverviewView(LoginRequiredMixin, View):
    """The home page: what is happening in the hospital now, shaped by the modules the user holds."""
    template_name = "reports/overview.html"

    def get(self, request, *args, **kwargs):
        modules = user_modules(request.user)
        if not modules:
            return render(request, "auth/no_access.html", {"view_name": view_title("No access")}, status=403)
        return render(request, self.template_name, self.context(modules))

    def context(self, modules):
        now = timezone.localtime()
        today = now.date()
        week_ago = today - datetime.timedelta(days=7)
        month_start = today - datetime.timedelta(days=29)
        sees = lambda *names: bool(modules & set(names)) or ADMINISTRATION in modules
        context = {"view_name": view_title("Hospital overview"), "page_title": "Hospital overview", "now": now,
                   "greeting": "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 17 else "Good evening"}

        if sees(PATIENTS, DOCTOR):
            visits = metrics.visits_per_day(week_ago, today)
            previous = [value for _, value in visits[:-1]]
            columns = active_visits_by_stage()
            waiting = sum(len(column["visits"]) for column in columns if column["key"] != "done")
            open_er = ClinicalModels.EmergencyCase.objects.filter(status__in=ClinicalModels.EmergencyCase.OPEN_STATUSES)
            beds = metrics.occupancy()
            context["clinical"] = {
                "visits_today": visits[-1][1],
                "visits_delta": delta(visits[-1][1], sum(previous) / len(previous) if previous else None),
                "waiting": waiting,
                "er_open": open_er.count(),
                "er_red": open_er.filter(acuity__in=("red", "orange")).count(),
                "inpatients": beds["occupied"], "beds": beds["total"], "occupancy": beds["share"],
                "awaiting_beds": ClinicalModels.Admission.objects.filter(status="awaiting").count(),
                "appointments_left": ClinicalModels.Appointment.objects.filter(scheduled_for__date=today, status="booked").count(),
                "stages": metrics.bar_list([(column["label"], len(column["visits"])) for column in columns if column["visits"]]),
                "wards": beds["wards"],
                "visit_chart": metrics.column_chart(metrics.visits_per_day(month_start, today)),
                "diagnoses": metrics.bar_list(metrics.top_diagnoses(month_start, today), limit=6),
            }
        if sees(LABORATORY, PHARMACY, RADIOLOGY, CARDIOLOGY):
            context["departments"] = [
                {"label": "Lab requests waiting", "value": LabModels.Request.objects.filter(handled=False).count(),
                 "url": reverse("lab:lab-home"), "show": sees(LABORATORY)},
                {"label": "Samples in the lab", "value": LabModels.Sample.objects.filter(status__in=("collected", "received_in_lab", "in_analysis")).count(),
                 "url": reverse("lab:sample-tracking"), "show": sees(LABORATORY)},
                {"label": "Prescriptions to dispense", "value": DepartmentModels.Prescription.objects.filter(quantity_issued__lt=F("quantity")).count(),
                 "url": reverse("departments:departments-pharmacy"), "show": sees(PHARMACY)},
                {"label": "Imaging to report", "value": DepartmentModels.DepartmentRequest.objects.filter(status="pending", department="radiology").count(),
                 "url": reverse("departments:departments-radiology"), "show": sees(RADIOLOGY)},
                {"label": "Cardiology to report", "value": DepartmentModels.DepartmentRequest.objects.filter(status="pending", department="cardiology").count(),
                 "url": reverse("departments:departments-cardiology"), "show": sees(CARDIOLOGY)},
            ]
            context["departments"] = [item for item in context["departments"] if item["show"]]
        if sees(FINANCE):
            received = metrics.money_received_per_day(week_ago, today)
            previous = [value for _, value in received[:-1]]
            context["finance"] = {
                "received_today": received[-1][1],
                "received_delta": delta(received[-1][1], sum(previous, Decimal("0")) / len(previous) if previous else None),
                "outstanding": metrics.outstanding_on_invoices(),
                "pending_invoices": FinanceModels.Invoice.objects.filter(status="pending").count(),
                "claims_waiting": FinanceModels.InsuranceClaim.objects.filter(status="submitted").count(),
                "claims_ready": FinanceModels.Invoice.objects.filter(insurance_company__isnull=False, company_covered__gt=0, claim__isnull=True).exclude(status="cancelled").count(),
                "mpesa_unmatched": FinanceModels.MpesaTransaction.objects.filter(status="unmatched").count(),
                "money_chart": metrics.column_chart(metrics.money_received_per_day(month_start, today), money=True),
                "streams": metrics.bar_list(metrics.billed_by_stream(month_start, today), money=True),
                "payers": metrics.bar_list(metrics.payer_mix(month_start, today), money=True),
            }
        context["attention"] = self.attention(modules, sees)
        return context

    def attention(self, modules, sees):
        today = timezone.localdate()
        items = []

        def add(count, text, url, tone="warn"):
            """`text` is "singular|plural" when the wording changes with the count."""
            if count:
                one, _, many = text.partition("|")
                items.append({"count": count, "text": one if count == 1 or not many else many, "url": url, "tone": tone})

        if sees(PATIENTS, DOCTOR):
            overdue = [case for case in ClinicalModels.EmergencyCase.objects.filter(status="waiting") if case.overdue]
            add(len(overdue), "emergency patient waiting past their triage target|emergency patients waiting past their triage target", reverse("clinical:emergency-queue"), "bad")
            add(ClinicalModels.Admission.objects.filter(status="awaiting").count(), "patient waiting for a bed|patients waiting for a bed", reverse("clinical:awaiting-admission"))
            add(ClinicalModels.Bed.objects.filter(status="cleaning").count(), "bed waiting to be cleaned and released|beds waiting to be cleaned and released", reverse("clinical:wards"), "neutral")
        if sees(PHARMACY, INVENTORY):
            soon = DepartmentModels.StockBatch.objects.filter(quantity_remaining__gt=0, expiry_date__gte=today,
                                                               expiry_date__lte=today + datetime.timedelta(days=30)).count()
            expired = DepartmentModels.StockBatch.objects.filter(quantity_remaining__gt=0, expiry_date__lt=today).count()
            add(expired, "batch expired on the shelf|batches expired on the shelf", reverse("departments:short-expiry") + "?tab=expired_stock", "bad")
            add(soon, "batch expires within 30 days|batches expire within 30 days", reverse("departments:short-expiry") + "?days=30")
            out = [drug for drug in DepartmentModels.Drug.objects.filter(is_active=True) if drug.stock_available == 0]
            add(len(out), "active drug is out of stock|active drugs are out of stock", reverse("manager:manager-inventory"), "bad")
        if sees(INVENTORY):
            from apps.stores.models import PurchaseOrder, Requisition

            add(Requisition.objects.filter(status="pending").count(), "requisition waiting for the stores|requisitions waiting for the stores", reverse("stores:requisitions"))
            late = PurchaseOrder.objects.filter(status__in=("sent", "partial"), expected_on__lt=today).count()
            add(late, "purchase order is past its delivery date|purchase orders are past their delivery date", reverse("stores:purchase-orders"))
        if sees(LABORATORY):
            stale = LabModels.Request.objects.filter(handled=False, created_on__lt=timezone.now() - datetime.timedelta(hours=4)).count()
            add(stale, "lab request open for more than 4 hours|lab requests open for more than 4 hours", reverse("lab:lab-home"))
        if sees(FINANCE):
            add(FinanceModels.MpesaTransaction.objects.filter(status="unmatched").count(), "M-Pesa payment to match|M-Pesa payments to match", reverse("finance:mpesa"))
            add(FinanceModels.EtimsSubmission.objects.filter(status="failed").count(), "invoice failed eTIMS transmission|invoices failed eTIMS transmission", reverse("finance:etims") + "?tab=etims_failed", "bad")
            unsent = FinanceModels.Invoice.objects.filter(status="paid", etims__isnull=True).count()
            add(unsent, "paid invoice not yet transmitted to eTIMS|paid invoices not yet transmitted to eTIMS", reverse("finance:etims"), "neutral")
            add(FinanceModels.CashierShift.objects.filter(closed_on__isnull=True, opened_on__date__lt=today).count(),
                "cashier shift left open from an earlier day|cashier shifts left open from an earlier day", reverse("finance:shifts") + "?tab=open_shifts")
        order = {"bad": 0, "warn": 1, "neutral": 2}
        return sorted(items, key=lambda item: order[item["tone"]])


# ------------------------------------------------------------------ analytics

PERIODS = (("7", "Last 7 days"), ("30", "Last 30 days"), ("90", "Last 90 days"))


def period_from(params):
    today = timezone.localdate()
    start, end = parse_date(params.get("start", "") or ""), parse_date(params.get("end", "") or "")
    if start and end and start <= end:
        return start, min(end, today), "custom"
    days = params.get("period", "30")
    days = days if days in dict(PERIODS) else "30"
    return today - datetime.timedelta(days=int(days) - 1), today, days


class AnalyticsView(PageView):
    any_modules = (ADMINISTRATION, FINANCE)
    template_name = "reports/analytics.html"
    title = "Analytics dashboard"

    def get(self, request, *args, **kwargs):
        if request.GET.get("format") == "csv":
            return self.csv()
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        start, end, period = period_from(self.request.GET)
        span = (end - start).days + 1
        prior_start, prior_end = start - datetime.timedelta(days=span), start - datetime.timedelta(days=1)
        visits = metrics.visits_per_day(start, end)
        money = metrics.money_received_per_day(start, end)
        visit_total = sum(value for _, value in visits)
        prior_visits = sum(value for _, value in metrics.visits_per_day(prior_start, prior_end))
        money_total = sum((value for _, value in money), Decimal("0"))
        prior_money = sum((value for _, value in metrics.money_received_per_day(prior_start, prior_end)), Decimal("0"))
        billed = metrics.billed_by_stream(start, end)
        context.update({
            "start": start, "end": end, "period": period, "periods": PERIODS, "span": span,
            "summary": [
                {"label": "Visits", "value": f"{visit_total:,}", "change": self.change(visit_total, prior_visits)},
                {"label": "New patients registered", "value": f"{metrics.new_patients(start, end):,}",
                 "change": self.change(metrics.new_patients(start, end), metrics.new_patients(prior_start, prior_end))},
                {"label": f"Money received ({settings.CURRENCY})", "value": metrics.compact(money_total), "change": self.change(money_total, prior_money)},
                {"label": f"Billed ({settings.CURRENCY})", "value": metrics.compact(sum((value for _, value in billed), Decimal("0"))), "change": None},
                {"label": "Average emergency wait", "value": (f"{metrics.emergency_wait(start, end)} min" if metrics.emergency_wait(start, end) is not None else "No data"), "change": None},
            ],
            "visit_chart": metrics.column_chart(visits),
            "money_chart": metrics.column_chart(money, money=True),
            "streams": metrics.bar_list(billed, money=True),
            "payers": metrics.bar_list(metrics.payer_mix(start, end), money=True),
            "diagnoses": metrics.bar_list(metrics.top_diagnoses(start, end, limit=10)),
            "lab_tests": metrics.bar_list(metrics.top_lab_tests(start, end, limit=10)),
            "workload": metrics.bar_list(metrics.workload(start, end)),
            "age_gender": metrics.patients_by_age_and_gender(start, end),
            "prior_label": f"{prior_start:%d %b} to {prior_end:%d %b}",
        })
        return context

    @staticmethod
    def change(current, prior):
        current, prior = float(current), float(prior)
        if not prior:
            return None
        percent = round((current - prior) * 100 / prior)
        return {"text": f"{'+' if percent > 0 else ''}{percent}% on the previous period", "direction": "up" if percent > 0 else "down" if percent < 0 else "level"}

    def csv(self):
        start, end, _ = period_from(self.request.GET)
        visits = dict(metrics.visits_per_day(start, end))
        money = dict(metrics.money_received_per_day(start, end))
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="daily-figures-{start}-{end}.csv"'
        writer = csv.writer(response)
        writer.writerow(["Date", "Visits", f"Money received ({settings.CURRENCY})"])
        for day in metrics.day_range(start, end):
            writer.writerow([day.isoformat(), visits.get(day, 0), f"{money.get(day, 0):.2f}"])
        return response


class MohReturnsView(PageView):
    module = ADMINISTRATION
    template_name = "reports/moh.html"
    title = "MOH 705 and 717 returns"

    def month(self):
        today = timezone.localdate()
        value = self.request.GET.get("month", "")
        try:
            year, month = (int(part) for part in value.split("-"))
            return datetime.date(year, month, 1)
        except ValueError:
            return today.replace(day=1)

    def get(self, request, *args, **kwargs):
        report = request.GET.get("format")
        if report in ("705a", "705b", "717"):
            return self.csv(report)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        month = self.month()
        today = timezone.localdate()
        months = []
        cursor = today.replace(day=1)
        for _ in range(12):
            months.append(cursor)
            cursor = (cursor - datetime.timedelta(days=1)).replace(day=1)
        context.update({
            "month": month, "months": months,
            "under_five": moh.morbidity(month, under_five=True),
            "over_five": moh.morbidity(month, under_five=False),
            "workload": moh.workload_717(month),
        })
        return context

    def csv(self, report):
        month = self.month()
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="moh-{report}-{month:%Y-%m}.csv"'
        writer = csv.writer(response)
        if report == "717":
            writer.writerow(["MOH 717 service workload", f"{month:%B %Y}", settings.HOSPITAL_NAME])
            for section in moh.workload_717(month):
                writer.writerow([])
                writer.writerow([section["title"]])
                for label, value in section["rows"]:
                    writer.writerow([label, value])
            return response
        table = moh.morbidity(month, under_five=(report == "705a"))
        writer.writerow([f"MOH {report.upper()} outpatient morbidity summary", f"{month:%B %Y}", settings.HOSPITAL_NAME])
        writer.writerow(["Condition"] + [str(day) for day in table["days"]] + ["Total"])
        for row in table["rows"]:
            writer.writerow([row["condition"]] + row["counts"] + [row["total"]])
        writer.writerow(["Total"] + table["day_totals"] + [table["total"]])
        return response
