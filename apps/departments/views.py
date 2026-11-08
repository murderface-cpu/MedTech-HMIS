from django.contrib import messages
from django.db import transaction
from django.db.models import F, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone

from apps.manager.access import CARDIOLOGY, DENTAL, INVENTORY, PHARMACY, RADIOLOGY, THEATRE, has_module_access
from apps.manager.pages import PageView

from apps.departments import forms as DepartmentForms
from apps.departments import models as DepartmentModels
from apps.finance import models as FinanceModels
from apps.finance.billing import is_billed
from apps.patients import models as PatientModals


# ------------------------------------------------------------------ pharmacy

class PharmacyView(PageView):
    module = PHARMACY
    template_name = "departments/pharmacy.html"
    title = "Pharmacy"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        prescriptions = DepartmentModels.Prescription.objects.select_related("visit__patient", "drug", "prescribed_by", "issued_by")
        context.update({
            "pending": prescriptions.filter(quantity_issued__lt=F("quantity")),
            "issued": prescriptions.filter(quantity_issued__gt=0).order_by("-issued_on")[:300],
            "drugs": DepartmentModels.Drug.objects.filter(is_active=True).select_related("category"),
        })
        return context

    def post_issue(self, request, *args, **kwargs):
        form = DepartmentForms.IssueForm(request.POST)
        if not form.is_valid():
            self.form_errors(form)
            return self.redirect_back()
        prescription, quantity = form.cleaned_data["prescription"], form.cleaned_data["quantity"]
        try:
            with transaction.atomic():
                prescription.drug.issue(quantity)
                prescription.quantity_issued = F("quantity_issued") + quantity
                prescription.issued_by = request.user
                prescription.issued_on = timezone.now()
                prescription.save(update_fields=["quantity_issued", "issued_by", "issued_on"])
        except DepartmentModels.InsufficientStock as error:
            messages.error(request, str(error))
            return self.redirect_back()
        messages.success(request, f"Issued {quantity} of {prescription.drug.name} to {prescription.visit.patient}.")
        return self.redirect_back()


# ------------------------------------------------------------------ cardiology and radiology

class DepartmentRequestsMixin:
    department = None

    def department_label(self):
        return dict(DepartmentModels.DepartmentRequest.DepartmentChoices)[self.department]

    def requests(self):
        return DepartmentModels.DepartmentRequest.objects.filter(department=self.department).select_related(
            "visit__patient", "service", "requested_by", "reported_by")


class DepartmentView(DepartmentRequestsMixin, PageView):
    template_name = "departments/department.html"

    @property
    def title(self):
        return self.department_label()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        requests = self.requests()
        context.update({
            "department": self.department,
            "department_label": self.department_label(),
            "pending": requests.filter(status="pending"),
            "completed": requests.filter(status="completed").order_by("-reported_on")[:300],
            "services": FinanceModels.Service.objects.filter(category=self.department),
        })
        return context


class CardiologyView(DepartmentView):
    module = CARDIOLOGY
    department = "cardiology"


class RadiologyView(DepartmentView):
    module = RADIOLOGY
    department = "radiology"


class DepartmentReportView(DepartmentRequestsMixin, PageView):
    template_name = "departments/report.html"
    title = "Report"
    modules = {"cardiology": CARDIOLOGY, "radiology": RADIOLOGY}

    def dispatch(self, request, *args, **kwargs):
        self.department = kwargs["department"]
        if self.department not in self.modules:
            raise Http404
        self.module = self.modules[self.department]
        return super().dispatch(request, *args, **kwargs)

    def get_request(self):
        return get_object_or_404(self.requests(), pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        department_request = self.get_request()
        context = super().get_context_data(**kwargs)
        context.setdefault("report_form", DepartmentForms.DepartmentReportForm(instance=department_request))
        context.update({
            "department_request": department_request,
            "department_label": self.department_label(),
            "list_url_name": f"departments:departments-{self.department}",
        })
        return context

    def post_report(self, request, *args, **kwargs):
        department_request = self.get_request()
        form = DepartmentForms.DepartmentReportForm(request.POST, instance=department_request)
        if not form.is_valid():
            return self.render_invalid(report_form=form)
        report = form.save(commit=False)
        report.status = "completed"
        report.reported_by = request.user
        report.reported_on = timezone.now()
        report.save()
        messages.success(request, "The report has been saved; the doctor can now see it.")
        return redirect(f"departments:departments-{self.department}")


# ------------------------------------------------------------------ theatre

class TheatreView(PageView):
    module = THEATRE
    template_name = "departments/theatre.html"
    title = "Theatre"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        bookings = DepartmentModels.TheatreBooking.objects.select_related(
            "visit__patient", "service", "surgeon", "anaesthetist", "nurse_one", "nurse_two")
        booked = set(bookings.exclude(status="cancelled").values_list("visit_id", "service_id"))
        orders = FinanceModels.VisitService.objects.filter(service__category="theatre", visit__complete=False).select_related(
            "visit__patient", "service", "ordered_by")
        initial = {"visit": self.request.GET.get("visit"), "service": self.request.GET.get("service")}
        context.setdefault("booking_form", DepartmentForms.TheatreBookingForm(initial=initial))
        context.update({
            "orders": [order for order in orders if (order.visit_id, order.service_id) not in booked],
            "scheduled": bookings.filter(status="scheduled").order_by("scheduled_for"),
            "history": bookings.exclude(status="scheduled")[:300],
        })
        return context

    def post_book(self, request, *args, **kwargs):
        form = DepartmentForms.TheatreBookingForm(request.POST)
        if not form.is_valid():
            return self.render_invalid(booking_form=form)
        booking = form.save(commit=False)
        booking.created_by = request.user
        booking.save()
        messages.success(request, f"{booking.surgery_type} for {booking.visit.patient} has been booked.")
        return self.redirect_back(tab="scheduled_bookings")


class TheatreBookingView(PageView):
    module = THEATRE
    template_name = "departments/theatre_booking.html"
    title = "Theatre Booking"

    def get_booking(self):
        return get_object_or_404(DepartmentModels.TheatreBooking.objects.select_related("visit__patient"), pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        booking = self.get_booking()
        context = super().get_context_data(**kwargs)
        context.setdefault("booking_form", DepartmentForms.TheatreBookingForm(instance=booking))
        context["booking"] = booking
        return context

    def post_update(self, request, *args, **kwargs):
        booking = self.get_booking()
        form = DepartmentForms.TheatreBookingForm(request.POST, instance=booking)
        if not form.is_valid():
            return self.render_invalid(booking_form=form)
        form.save()
        messages.success(request, "The booking has been updated.")
        return redirect("departments:departments-theatre")


# ------------------------------------------------------------------ dental

class DentalView(PageView):
    module = DENTAL
    template_name = "departments/dental.html"
    title = "Dental"

    def selected_visit(self, value):
        if value and str(value).isdigit():
            return PatientModals.Visit.objects.select_related("patient").filter(pk=value).first()
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        visit = kwargs.get("visit") or self.selected_visit(self.request.GET.get("visit"))
        procedures = DepartmentModels.DentalProcedure.objects.select_related("visit__patient", "procedure", "created_by")
        context.setdefault("procedure_form", DepartmentForms.DentalProcedureForm())
        context.update({
            "visits": PatientModals.Visit.active.select_related("patient"),
            "visit": visit,
            "visit_procedures": [
                {"procedure": procedure, "billed": is_billed(f"dental:{procedure.pk}")}
                for procedure in procedures.filter(visit=visit)
            ] if visit else [],
            "recent": procedures[:300],
        })
        return context

    def post_record(self, request, *args, **kwargs):
        visit = self.selected_visit(request.POST.get("visit"))
        if visit is None:
            messages.error(request, "Select the patient's visit first.")
            return self.redirect_back()
        form = DepartmentForms.DentalProcedureForm(request.POST)
        if not form.is_valid():
            return self.render_invalid(procedure_form=form, visit=visit)
        procedure = form.save(commit=False)
        procedure.visit = visit
        procedure.created_by = request.user
        procedure.save()
        messages.success(request, f"{procedure.procedure.name} has been recorded for {visit.patient}.")
        return self.redirect_back(visit=visit.pk)

    def post_remove(self, request, *args, **kwargs):
        procedure = get_object_or_404(DepartmentModels.DentalProcedure, pk=request.POST.get("procedure"))
        if is_billed(f"dental:{procedure.pk}"):
            messages.error(request, "This procedure has already been invoiced and cannot be removed.")
        else:
            procedure.delete()
            messages.success(request, "The procedure has been removed.")
        return self.redirect_back(visit=procedure.visit_id)


# ------------------------------------------------------------------ radiology image archive

class ImageArchiveView(PageView):
    module = RADIOLOGY
    template_name = "departments/image_archive.html"
    title = "Image archive"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        initial = {"request": self.request.GET.get("request")}
        context.setdefault("image_form", DepartmentForms.ExamImageForm(initial=initial))
        query = self.request.GET.get("q", "").strip()
        exams = (DepartmentModels.DepartmentRequest.objects.filter(department="radiology", images__isnull=False)
                 .select_related("visit__patient", "service").prefetch_related("images").distinct().order_by("-created_on"))
        if query:
            exams = exams.filter(Q(visit__patient__firstname__icontains=query) | Q(visit__patient__lastname__icontains=query)
                                 | Q(visit__patient__patient_id__icontains=query) | Q(service__name__icontains=query))
        context.update({"exams": exams[:60], "query": query,
                        "image_count": DepartmentModels.ExamImage.objects.filter(request__department="radiology").count()})
        return context

    def post_upload(self, request, *args, **kwargs):
        form = DepartmentForms.ExamImageForm(request.POST, request.FILES)
        if not form.is_valid():
            return self.render_invalid(image_form=form)
        image = form.save(commit=False)
        image.uploaded_by = request.user
        image.save()
        messages.success(request, f"{image.filename} is filed under {image.request.service.name} for {image.request.visit.patient}.")
        return self.redirect_back(tab="archive")

    def post_delete(self, request, *args, **kwargs):
        image = get_object_or_404(DepartmentModels.ExamImage, pk=request.POST.get("image"))
        if image.request.status == "completed":
            messages.error(request, "Images of a reported examination are part of the record and cannot be deleted.")
            return self.redirect_back()
        image.file.delete(save=False)
        image.delete()
        messages.success(request, "The image has been deleted.")
        return self.redirect_back()


# ------------------------------------------------------------------ short-expiry drugs

class ShortExpiryView(PageView):
    any_modules = (PHARMACY, INVENTORY)
    template_name = "departments/short_expiry.html"
    title = "Short-expiry drugs"
    WINDOWS = (30, 60, 90, 180)

    def get_context_data(self, **kwargs):
        import datetime

        context = super().get_context_data(**kwargs)
        try:
            days = int(self.request.GET.get("days", 90))
        except ValueError:
            days = 90
        days = days if days in self.WINDOWS else 90
        today = timezone.localdate()
        batches = DepartmentModels.StockBatch.objects.filter(quantity_remaining__gt=0, expiry_date__isnull=False).select_related("drug", "supplier")
        expiring = []
        for batch in batches.filter(expiry_date__gte=today, expiry_date__lte=today + datetime.timedelta(days=days)).order_by("expiry_date"):
            batch.days_left = (batch.expiry_date - today).days
            batch.value = batch.quantity_remaining * batch.drug.unit_price
            expiring.append(batch)
        expired = []
        for batch in batches.filter(expiry_date__lt=today).order_by("expiry_date"):
            batch.days_ago = (today - batch.expiry_date).days
            batch.value = batch.quantity_remaining * batch.drug.unit_price
            expired.append(batch)
        context.update({
            "days": days, "windows": self.WINDOWS, "expiring": expiring, "expired": expired,
            "expiring_value": sum((batch.value for batch in expiring), 0),
            "expired_value": sum((batch.value for batch in expired), 0),
            "can_write_off": has_module_access(self.request.user, INVENTORY),
        })
        return context

    def post_write_off(self, request, *args, **kwargs):
        from apps.stores.models import StockAdjustment

        if not has_module_access(request.user, INVENTORY):
            messages.error(request, "Writing off stock needs the Inventory module.")
            return self.redirect_back()
        batch = get_object_or_404(DepartmentModels.StockBatch.objects.select_related("drug"), pk=request.POST.get("batch"))
        if batch.quantity_remaining <= 0 or not batch.expiry_date or batch.expiry_date >= timezone.localdate():
            messages.error(request, "Only expired stock still on the shelf can be written off here.")
            return self.redirect_back()
        quantity = batch.quantity_remaining
        StockAdjustment.apply(batch, -quantity, "expired", request.user, notes=f"Expired {batch.expiry_date:%d %b %Y}")
        messages.success(request, f"Wrote off {quantity} expired units of {batch.drug.name}.")
        return self.redirect_back(tab="expired_stock")
