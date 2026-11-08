"""Outpatient appointments and queue board, note templates, emergency care and inpatient wards."""
from collections import OrderedDict
from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Exists, F, OuterRef, Q
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone

from apps.clinical import forms as ClinicalForms
from apps.clinical import models as ClinicalModels
from apps.departments import models as DepartmentModels
from apps.finance import models as FinanceModels
from apps.lab import models as LabModels
from apps.manager import models as ManagerModels
from apps.manager.access import DOCTOR, FINANCE, PATIENTS
from apps.manager.pages import PageView
from apps.patients import models as PatientModels

CLINICAL = (PATIENTS, DOCTOR)


class ClinicalView(PageView):
    any_modules = CLINICAL

    def current_doctor(self):
        staff = getattr(self.request.user, "staff", None)
        return staff.doctor if staff is not None and staff.doctor_id else None


def visit_category(name):
    return ManagerModels.VisitCategory.objects.get_or_create(name=name)[0]


def open_visit(patient, category_name, doctor=None, billing=None):
    """The patient's active visit, or a new one. A patient has one active visit at a time."""
    visit = PatientModels.Visit.active.filter(patient=patient).first()
    if visit is None:
        visit = PatientModels.Visit.objects.create(
            patient=patient, category=visit_category(category_name), doctor=doctor, billing=billing)
    elif doctor and not visit.doctor_id:
        visit.doctor = doctor
        visit.save(update_fields=["doctor", "updated_on"])
    return visit


# ------------------------------------------------------------------ appointments

class AppointmentsView(ClinicalView):
    template_name = "clinical/appointments.html"
    title = "Appointments"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        appointments = ClinicalModels.Appointment.objects.select_related("patient", "doctor", "speciality", "category", "visit")
        initial = {"patient": self.request.GET.get("patient")}
        context.setdefault("appointment_form", ClinicalForms.AppointmentForm(prefix="appointment", initial=initial))
        context.setdefault("checkin_form", ClinicalForms.CheckInForm(prefix="checkin"))
        context.update({
            "today": appointments.filter(scheduled_for__date=today).exclude(status="cancelled"),
            "upcoming": appointments.filter(scheduled_for__date__gt=today, status="booked"),
            "history": appointments.filter(Q(scheduled_for__date__lt=today) | Q(status__in=("cancelled", "missed")))
                                   .order_by("-scheduled_for")[:300],
            "billing_kinds": {billing.pk: billing.kind for billing in FinanceModels.BillingType.objects.all()},
        })
        context["booked_today"] = sum(1 for appointment in context["today"] if appointment.status == "booked")
        return context

    def get_appointment(self):
        return get_object_or_404(ClinicalModels.Appointment.objects.select_related("patient"), pk=self.request.POST.get("appointment"))

    def post_book(self, request, *args, **kwargs):
        form = ClinicalForms.AppointmentForm(request.POST, prefix="appointment")
        if not form.is_valid():
            return self.render_invalid(appointment_form=form)
        appointment = form.save(commit=False)
        appointment.created_by = request.user
        appointment.save()
        when = timezone.localtime(appointment.scheduled_for)
        messages.success(request, f"{appointment.patient} is booked for {when:%A %d %B at %H:%M}.")
        tab = "today_appointments" if when.date() == timezone.localdate() else "upcoming_appointments"
        return self.redirect_back(tab=tab)

    def post_check_in(self, request, *args, **kwargs):
        appointment = self.get_appointment()
        if appointment.status != "booked":
            messages.error(request, f"This appointment is already {appointment.get_status_display().lower()}.")
            return self.redirect_back()
        form = ClinicalForms.CheckInForm(request.POST, prefix="checkin")
        if not form.is_valid():
            self.form_errors(form)
            return self.redirect_back()
        with transaction.atomic():
            data = form.cleaned_data
            billing = FinanceModels.Billing.objects.create(
                btype=data["billing_type"],
                insurance_company=data.get("insurance_company") if data["billing_type"].kind == "insurance" else None,
                account_company=data.get("account_company") if data["billing_type"].kind == "account" else None,
            )
            visit = PatientModels.Visit.active.filter(patient=appointment.patient).first()
            if visit is None:
                visit = PatientModels.Visit.objects.create(
                    patient=appointment.patient, category=appointment.category, doctor=appointment.doctor,
                    speciality=appointment.speciality, billing=billing)
            appointment.visit = visit
            appointment.status = "checked_in"
            appointment.save(update_fields=["visit", "status"])
        messages.success(request, f"{appointment.patient} is checked in on visit {visit.visit_id} and waits for triage.")
        return self.redirect_back()

    def post_set_status(self, request, *args, **kwargs):
        appointment = self.get_appointment()
        status = request.POST.get("status")
        if status not in ("missed", "cancelled") or appointment.status != "booked":
            messages.error(request, "Only a booked appointment can be cancelled or marked as missed.")
            return self.redirect_back()
        appointment.status = status
        appointment.save(update_fields=["status"])
        messages.success(request, f"The appointment for {appointment.patient} is marked {appointment.get_status_display().lower()}.")
        return self.redirect_back()


# ------------------------------------------------------------------ queue board

STAGES = OrderedDict((
    ("triage", "Waiting for triage"),
    ("doctor", "Waiting for the doctor"),
    ("lab", "In the laboratory"),
    ("imaging", "In imaging"),
    ("pharmacy", "At the pharmacy"),
    ("cashier", "At the cashier"),
    ("done", "Ready to close"),
))


def active_visits_by_stage():
    """Every open visit placed in the first step of the journey it has not finished."""
    visits = (
        PatientModels.Visit.active.select_related("patient", "doctor", "category")
        .annotate(
            triaged=Exists(PatientModels.Triage.objects.filter(visit=OuterRef("pk"))),
            consulted=Exists(PatientModels.Diagnosis.objects.filter(visit=OuterRef("pk")))
            | Exists(PatientModels.GeneralFinding.objects.filter(visit=OuterRef("pk"))),
            lab_pending=Exists(LabModels.Request.objects.filter(visit=OuterRef("pk"), handled=False)),
            imaging_pending=Exists(DepartmentModels.DepartmentRequest.objects.filter(visit=OuterRef("pk"), status="pending")),
            pharmacy_pending=Exists(DepartmentModels.Prescription.objects.filter(visit=OuterRef("pk"), quantity_issued__lt=F("quantity"))),
            invoice_pending=Exists(FinanceModels.Invoice.objects.filter(visit=OuterRef("pk"), status="pending")),
        )
        # inpatients, patients waiting for a bed and open emergency cases are followed on their own boards
        .exclude(admissions__status__in=("admitted", "awaiting"))
        .exclude(emergency_case__status__in=ClinicalModels.EmergencyCase.OPEN_STATUSES)
        .order_by("visit_date")
    )
    columns = OrderedDict((key, {"key": key, "label": label, "visits": []}) for key, label in STAGES.items())
    now = timezone.now()
    for visit in visits:
        if not visit.triaged:
            stage = "triage"
        elif not visit.consulted:
            stage = "doctor"
        elif visit.lab_pending:
            stage = "lab"
        elif visit.imaging_pending:
            stage = "imaging"
        elif visit.pharmacy_pending:
            stage = "pharmacy"
        elif visit.invoice_pending:
            stage = "cashier"
        else:
            stage = "done"
        visit.waiting_minutes = max(int((now - visit.updated_on).total_seconds() // 60), 0) if visit.updated_on else 0
        visit.in_visit_minutes = max(int((now - visit.visit_date).total_seconds() // 60), 0)
        columns[stage]["visits"].append(visit)
    return list(columns.values())


class QueueBoardView(ClinicalView):
    template_name = "clinical/queue.html"
    title = "Queue board"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        columns = active_visits_by_stage()
        context.update({"columns": columns, "total_active": sum(len(column["visits"]) for column in columns),
                        "refreshed_on": timezone.localtime()})
        return context


# ------------------------------------------------------------------ note templates

class NoteTemplatesView(PageView):
    module = DOCTOR
    template_name = "clinical/note_templates.html"
    title = "Clinical note templates"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("template_form", ClinicalForms.NoteTemplateForm(prefix="template"))
        context["note_templates"] = ClinicalModels.NoteTemplate.objects.select_related("created_by")
        return context

    def post_add_template(self, request, *args, **kwargs):
        form = ClinicalForms.NoteTemplateForm(request.POST, prefix="template")
        if not form.is_valid():
            return self.render_invalid(template_form=form)
        note_template = form.save(commit=False)
        note_template.created_by = request.user
        note_template.save()
        messages.success(request, f"The template '{note_template.name}' is ready to use in consultations.")
        return self.redirect_back(tab="template_list")


class NoteTemplateDetailView(PageView):
    module = DOCTOR
    template_name = "clinical/note_template.html"
    title = "Note template"

    def get_object(self):
        return get_object_or_404(ClinicalModels.NoteTemplate, pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        note_template = self.get_object()
        context = super().get_context_data(**kwargs)
        context.setdefault("template_form", ClinicalForms.NoteTemplateForm(instance=note_template))
        context["note_template"] = note_template
        return context

    def post_update(self, request, *args, **kwargs):
        form = ClinicalForms.NoteTemplateForm(request.POST, instance=self.get_object())
        if not form.is_valid():
            return self.render_invalid(template_form=form)
        form.save()
        messages.success(request, "The template has been saved.")
        return redirect("clinical:note-templates")

    def post_delete(self, request, *args, **kwargs):
        note_template = self.get_object()
        note_template.delete()
        messages.success(request, f"The template '{note_template.name}' has been deleted.")
        return redirect("clinical:note-templates")


# ------------------------------------------------------------------ emergency

class EmergencyCheckInView(ClinicalView):
    template_name = "clinical/emergency_checkin.html"
    title = "Emergency check-in"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("case_form", ClinicalForms.EmergencyCheckInForm(prefix="case"))
        today = timezone.localdate()
        context["arrivals_today"] = ClinicalModels.EmergencyCase.objects.filter(arrived_on__date=today).select_related("patient").order_by("-arrived_on")
        return context

    def post_check_in(self, request, *args, **kwargs):
        form = ClinicalForms.EmergencyCheckInForm(request.POST, prefix="case")
        if not form.is_valid():
            return self.render_invalid(case_form=form)
        with transaction.atomic():
            patient = form.resolve_patient()
            case = form.save(commit=False)
            case.patient = patient
            case.created_by = request.user
            visit = open_visit(patient, "Emergency", doctor=case.attending)
            # a visit carries one emergency case; a returning patient on an old case gets a fresh link
            case.visit = None if ClinicalModels.EmergencyCase.objects.filter(visit=visit).exists() else visit
            case.save()
        messages.success(request, f"{patient} is checked in as {case.case_number}, {case.get_acuity_display().lower()}.")
        return redirect("clinical:emergency-queue")


class EmergencyQueueView(ClinicalView):
    template_name = "clinical/emergency_queue.html"
    title = "Emergency queue"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cases = ClinicalModels.EmergencyCase.objects.select_related("patient", "attending", "visit")
        open_cases = list(cases.filter(status__in=ClinicalModels.EmergencyCase.OPEN_STATUSES))
        context.setdefault("outcome_form", ClinicalForms.EmergencyOutcomeForm())
        context.update({
            "waiting": [case for case in open_cases if case.status == "waiting"],
            "in_treatment": [case for case in open_cases if case.status == "in_treatment"],
            "awaiting_admission": [case for case in open_cases if case.status == "awaiting"],
            "closed": cases.exclude(status__in=ClinicalModels.EmergencyCase.OPEN_STATUSES).order_by("-closed_on")[:200],
            "doctors": ClinicalForms.active_doctors(),
            "wards": ClinicalModels.Ward.objects.filter(is_active=True),
            "acuity_counts": {acuity: sum(1 for case in open_cases if case.acuity == acuity)
                              for acuity, _ in ClinicalModels.EmergencyCase.AcuityChoices},
        })
        return context

    def get_case(self):
        return get_object_or_404(ClinicalModels.EmergencyCase.objects.select_related("patient"), pk=self.request.POST.get("case"))

    def post_start(self, request, *args, **kwargs):
        case = self.get_case()
        if case.status != "waiting":
            messages.error(request, "This patient is already being seen.")
            return self.redirect_back()
        doctor_id = request.POST.get("attending")
        case.attending_id = int(doctor_id) if doctor_id and doctor_id.isdigit() else (case.attending_id or getattr(self.current_doctor(), "pk", None))
        case.status = "in_treatment"
        case.seen_on = timezone.now()
        case.save(update_fields=["attending", "status", "seen_on"])
        if case.visit_id and case.attending_id and not case.visit.doctor_id:
            case.visit.doctor_id = case.attending_id
            case.visit.save(update_fields=["doctor", "updated_on"])
        messages.success(request, f"{case.patient} is now in treatment, seen after {case.waiting_minutes} minutes.")
        return self.redirect_back(tab="in_treatment")

    def post_request_admission(self, request, *args, **kwargs):
        case = self.get_case()
        if not case.is_open:
            messages.error(request, "This case is closed.")
            return self.redirect_back()
        reason = request.POST.get("reason", "").strip() or case.chief_complaint
        ward_id = request.POST.get("ward")
        with transaction.atomic():
            visit = case.visit or open_visit(case.patient, "Emergency", doctor=case.attending)
            ClinicalModels.Admission.objects.create(
                patient=case.patient, visit=visit, emergency_case=case, doctor=case.attending, reason=reason,
                requested_ward_id=int(ward_id) if ward_id and ward_id.isdigit() else None, requested_by=request.user)
            case.status = "awaiting"
            case.save(update_fields=["status"])
        messages.success(request, f"Admission requested for {case.patient}. The ward assigns a bed from Awaiting admission.")
        return self.redirect_back(tab="awaiting_admission")

    def post_close(self, request, *args, **kwargs):
        case = self.get_case()
        form = ClinicalForms.EmergencyOutcomeForm(request.POST)
        if not form.is_valid() or not case.is_open:
            messages.error(request, "Choose how the case ends.")
            return self.redirect_back()
        case.status = form.cleaned_data["outcome"]
        case.outcome_notes = form.cleaned_data["outcome_notes"]
        case.closed_on = timezone.now()
        case.seen_on = case.seen_on or case.closed_on
        case.save(update_fields=["status", "outcome_notes", "closed_on", "seen_on"])
        ClinicalModels.Admission.objects.filter(emergency_case=case, status="awaiting").update(status="cancelled")
        messages.success(request, f"{case.case_number} is closed: {case.get_status_display().lower()}.")
        return self.redirect_back(tab="closed_cases")


# ------------------------------------------------------------------ inpatient

def current_inpatients():
    return ClinicalModels.Admission.objects.filter(status="admitted").select_related(
        "patient", "bed__ward", "doctor", "visit").order_by("bed__ward__name", "bed__number")


def admit(admission, bed, user=None):
    with transaction.atomic():
        bed = ClinicalModels.Bed.objects.select_for_update().get(pk=bed.pk)
        if bed.status != "available":
            raise ValueError(f"{bed} is no longer available.")
        admission.bed = bed
        admission.status = "admitted"
        admission.admitted_on = timezone.now()
        admission.save(update_fields=["bed", "status", "admitted_on"])
        bed.status = "occupied"
        bed.save(update_fields=["status"])
        if admission.emergency_case_id:
            ClinicalModels.EmergencyCase.objects.filter(pk=admission.emergency_case_id).update(
                status="admitted", closed_on=admission.admitted_on)


def post_bed_charges(admissions, until=None):
    """Create the missing daily bed charges of each admission up to `until` (today). Returns (count, amount)."""
    until = until or timezone.localdate()
    count, amount = 0, Decimal("0")
    for admission in admissions:
        if not admission.bed_id:
            continue
        charged = set(admission.bed_charges.values_list("charge_date", flat=True))
        for day in admission.charge_days():
            if day > until or day in charged:
                continue
            ward = admission.bed.ward
            ClinicalModels.BedCharge.objects.create(admission=admission, ward=ward, charge_date=day, amount=ward.daily_rate)
            count += 1
            amount += ward.daily_rate
    return count, amount


class InpatientView(ClinicalView):
    def get_admission(self, pk=None):
        return get_object_or_404(ClinicalModels.Admission.objects.select_related("patient", "bed__ward", "visit", "doctor"),
                                 pk=pk or self.request.POST.get("admission"))


class AdmissionsView(InpatientView):
    template_name = "clinical/admissions.html"
    title = "Admissions"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("admission_form", ClinicalForms.AdmissionRequestForm(prefix="admission"))
        context["inpatients"] = current_inpatients()
        beds = ClinicalModels.Bed.objects.filter(ward__is_active=True)
        context["beds_total"] = beds.count()
        context["beds_free"] = beds.filter(status="available").count()
        context["awaiting_count"] = ClinicalModels.Admission.objects.filter(status="awaiting").count()
        return context

    def post_request(self, request, *args, **kwargs):
        form = ClinicalForms.AdmissionRequestForm(request.POST, prefix="admission")
        if not form.is_valid():
            return self.render_invalid(admission_form=form)
        admission = form.save(commit=False)
        admission.patient = admission.visit.patient
        admission.requested_by = request.user
        admission.save()
        messages.success(request, f"Admission requested for {admission.patient}. Assign a bed from Awaiting admission.")
        return redirect("clinical:awaiting-admission")


class AwaitingAdmissionView(InpatientView):
    template_name = "clinical/awaiting_admission.html"
    title = "Awaiting admission"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        free_beds = list(ClinicalModels.Bed.objects.filter(status="available", ward__is_active=True).select_related("ward"))
        awaiting = ClinicalModels.Admission.objects.filter(status="awaiting").select_related(
            "patient", "requested_ward", "doctor", "emergency_case").order_by("requested_on")
        context.update({"awaiting": awaiting, "free_beds": free_beds})
        return context

    def post_assign(self, request, *args, **kwargs):
        admission = self.get_admission()
        form = ClinicalForms.AssignBedForm(request.POST)
        if admission.status != "awaiting" or not form.is_valid():
            messages.error(request, "Choose an available bed.")
            return self.redirect_back()
        try:
            admit(admission, form.cleaned_data["bed"], request.user)
        except ValueError as error:
            messages.error(request, str(error))
            return self.redirect_back()
        messages.success(request, f"{admission.patient} is admitted to {admission.bed}.")
        return redirect("clinical:admission", pk=admission.pk)

    def post_cancel(self, request, *args, **kwargs):
        admission = self.get_admission()
        if admission.status == "awaiting":
            admission.status = "cancelled"
            admission.save(update_fields=["status"])
            if admission.emergency_case_id:
                ClinicalModels.EmergencyCase.objects.filter(pk=admission.emergency_case_id, status="awaiting").update(status="in_treatment")
            messages.success(request, f"The admission request for {admission.patient} is cancelled.")
        return self.redirect_back()


class AdmissionDetailView(InpatientView):
    template_name = "clinical/admission.html"
    title = "Admission"

    def get_context_data(self, **kwargs):
        admission = self.get_admission(self.kwargs["pk"])
        context = super().get_context_data(**kwargs)
        context.setdefault("discharge_form", ClinicalForms.DischargeForm(instance=admission))
        context.update({
            "admission": admission,
            "bed_form": ClinicalForms.AssignBedForm(),
            "charges": admission.bed_charges.select_related("ward"),
            "discharge_templates": ClinicalModels.NoteTemplate.objects.filter(section="discharge_summary", is_active=True),
            "diagnoses": PatientModels.Diagnosis.objects.filter(visit=admission.visit) if admission.visit_id else [],
        })
        context["charges_total"] = sum((charge.amount for charge in context["charges"]), Decimal("0"))
        return context

    def post_transfer(self, request, *args, **kwargs):
        admission = self.get_admission(self.kwargs["pk"])
        form = ClinicalForms.AssignBedForm(request.POST)
        if admission.status != "admitted" or not form.is_valid():
            messages.error(request, "Choose an available bed.")
            return self.redirect_back()
        with transaction.atomic():
            post_bed_charges([admission])
            old_bed = admission.bed
            new_bed = form.cleaned_data["bed"]
            admission.bed = new_bed
            admission.save(update_fields=["bed"])
            new_bed.status = "occupied"
            new_bed.save(update_fields=["status"])
            if old_bed:
                old_bed.status = "cleaning"
                old_bed.save(update_fields=["status"])
        messages.success(request, f"{admission.patient} has moved to {new_bed}.")
        return self.redirect_back()

    def post_discharge(self, request, *args, **kwargs):
        admission = self.get_admission(self.kwargs["pk"])
        if admission.status != "admitted":
            messages.error(request, "Only an admitted patient can be discharged.")
            return self.redirect_back()
        form = ClinicalForms.DischargeForm(request.POST, instance=admission)
        if not form.is_valid():
            return self.render_invalid(discharge_form=form)
        with transaction.atomic():
            admission = form.save(commit=False)
            admission.status = "discharged"
            admission.discharged_on = timezone.now()
            admission.discharged_by = request.user
            admission.save()
            count, amount = post_bed_charges([admission])
            if admission.bed_id:
                ClinicalModels.Bed.objects.filter(pk=admission.bed_id).update(status="cleaning")
        messages.success(request, f"{admission.patient} is discharged after {admission.days_admitted} days. "
                                  f"Bed charges are ready to invoice at the cashier.")
        return redirect("clinical:discharges")


class DischargesView(InpatientView):
    template_name = "clinical/discharges.html"
    title = "Discharges"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "inpatients": current_inpatients(),
            "discharged": ClinicalModels.Admission.objects.filter(status="discharged").select_related(
                "patient", "bed__ward", "discharged_by").order_by("-discharged_on")[:300],
        })
        return context


class WardBoardView(InpatientView):
    template_name = "clinical/wards.html"
    title = "Ward board"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        occupants = {admission.bed_id: admission for admission in current_inpatients()}
        wards = []
        for ward in ClinicalModels.Ward.objects.prefetch_related("beds").select_related("location"):
            beds = [{"bed": bed, "admission": occupants.get(bed.pk)} for bed in ward.beds.all()]
            occupied = sum(1 for bed in beds if bed["bed"].status == "occupied")
            wards.append({"ward": ward, "beds": beds, "occupied": occupied, "total": len(beds),
                          "available": sum(1 for bed in beds if bed["bed"].status == "available")})
        context.setdefault("ward_form", ClinicalForms.WardForm(prefix="ward"))
        context.setdefault("beds_form", ClinicalForms.AddBedsForm(prefix="beds"))
        context["wards"] = wards
        return context

    def post_add_ward(self, request, *args, **kwargs):
        form = ClinicalForms.WardForm(request.POST, prefix="ward")
        if not form.is_valid():
            return self.render_invalid(ward_form=form)
        with transaction.atomic():
            ward = form.save()
            for number in range(1, (form.cleaned_data.get("beds") or 0) + 1):
                ClinicalModels.Bed.objects.create(ward=ward, number=str(number))
        messages.success(request, f"{ward.name} has been added with {ward.beds.count()} beds.")
        return self.redirect_back(tab="ward_board")

    def post_add_beds(self, request, *args, **kwargs):
        form = ClinicalForms.AddBedsForm(request.POST, prefix="beds")
        if not form.is_valid():
            return self.render_invalid(beds_form=form)
        ward, count = form.cleaned_data["ward"], form.cleaned_data["count"]
        numbers = [int(number) for number in ward.beds.values_list("number", flat=True) if number.isdigit()]
        start = max(numbers, default=0) + 1
        for number in range(start, start + count):
            ClinicalModels.Bed.objects.create(ward=ward, number=str(number))
        messages.success(request, f"Added beds {start} to {start + count - 1} to {ward.name}.")
        return self.redirect_back(tab="ward_board")

    def post_bed_status(self, request, *args, **kwargs):
        bed = get_object_or_404(ClinicalModels.Bed, pk=request.POST.get("bed"))
        status = request.POST.get("status")
        if bed.status == "occupied" or status not in ("available", "cleaning", "out_of_service"):
            messages.error(request, "An occupied bed changes when its patient is moved or discharged.")
            return self.redirect_back()
        bed.status = status
        bed.save(update_fields=["status"])
        messages.success(request, f"{bed} is now {bed.get_status_display().lower()}.")
        return self.redirect_back()


class BedChargesView(InpatientView):
    any_modules = CLINICAL + (FINANCE,)
    template_name = "clinical/bed_charges.html"
    title = "Bed charges"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        rows = []
        admissions = ClinicalModels.Admission.objects.filter(status__in=("admitted", "discharged"), bed__isnull=False).select_related(
            "patient", "bed__ward", "visit").annotate(charged=Count("bed_charges")).order_by("-admitted_on")
        for admission in admissions:
            due = [day for day in admission.charge_days() if day <= today]
            missing = len(due) - admission.charged
            if missing > 0:
                rows.append({"admission": admission, "days": missing, "amount": admission.bed.ward.daily_rate * missing})
        posted = ClinicalModels.BedCharge.objects.select_related("admission__patient", "ward").order_by("-charge_date")[:400]
        from apps.finance.billing import billed_sources_for

        billed = billed_sources_for([charge.source for charge in posted])
        context.update({
            "to_post": rows,
            "to_post_total": sum((row["amount"] for row in rows), Decimal("0")),
            "posted": [{"charge": charge, "billed": charge.source in billed} for charge in posted],
        })
        return context

    def post_post_charges(self, request, *args, **kwargs):
        admissions = ClinicalModels.Admission.objects.filter(status__in=("admitted", "discharged"), bed__isnull=False).select_related("bed__ward")
        with transaction.atomic():
            count, amount = post_bed_charges(admissions)
        if count:
            messages.success(request, f"Posted {count} bed days worth {amount:,.2f}. They appear on each visit's next invoice.")
        else:
            messages.success(request, "Every bed day is already posted.")
        return self.redirect_back(tab="posted_charges")
