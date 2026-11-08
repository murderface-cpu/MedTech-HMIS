from django.conf import settings
from django.db import models, transaction
from django.db.models import Min, Q, Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.finance.models import MONEY
from apps.manager import utils


class DrugCategory(models.Model):
    class Meta:
        ordering = ("name",)

    name = models.CharField(_("Name"), max_length=256, unique=True)

    def __str__(self) -> str:
        return f"{self.name}"


class Supplier(models.Model):
    class Meta:
        ordering = ("name",)

    name = models.CharField(_("Supplier Name"), max_length=256, unique=True)
    telephone = models.CharField(_("Telephone"), max_length=64, null=True, blank=True)
    email = models.EmailField(_("Email"), null=True, blank=True)
    address = models.CharField(_("Address"), max_length=256, null=True, blank=True)
    created_on = models.DateTimeField(_("Created on"), default=timezone.now)

    def __str__(self) -> str:
        return f"{self.name}"


class InsufficientStock(Exception):
    pass


class Drug(models.Model):
    class Meta:
        ordering = ("name",)

    drug_number = models.CharField(_("Drug No"), max_length=64, unique=True, null=True, blank=True)
    name = models.CharField(_("Drug Name"), max_length=256, unique=True)
    category = models.ForeignKey(to=DrugCategory, on_delete=models.PROTECT, related_name="drugs")
    manufacturer = models.CharField(_("Manufacturer"), max_length=256, null=True, blank=True)
    supplier = models.ForeignKey(to=Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    unit_price = models.DecimalField(_("Unit Price"), **MONEY)
    is_active = models.BooleanField(_("Active"), default=True)
    created_on = models.DateTimeField(_("Created on"), default=timezone.now)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        utils.assign_code(self, "drug_number", "DRG")

    def usable_batches(self):
        today = timezone.localdate()
        return self.batches.filter(quantity_remaining__gt=0).filter(Q(expiry_date__isnull=True) | Q(expiry_date__gte=today))

    @property
    def stock_available(self):
        return self.usable_batches().aggregate(total=Sum("quantity_remaining"))["total"] or 0

    @property
    def stock_expired(self):
        return self.batches.filter(quantity_remaining__gt=0, expiry_date__lt=timezone.localdate()).aggregate(total=Sum("quantity_remaining"))["total"] or 0

    @property
    def stock_purchased(self):
        return self.batches.aggregate(total=Sum("quantity_received"))["total"] or 0

    @property
    def next_expiry(self):
        return self.usable_batches().aggregate(date=Min("expiry_date"))["date"]

    def issue(self, quantity):
        """Take `quantity` units from the batches that expire first."""
        with transaction.atomic():
            batches = list(self.usable_batches().select_for_update().order_by(models.F("expiry_date").asc(nulls_last=True), "id"))
            if sum(batch.quantity_remaining for batch in batches) < quantity:
                raise InsufficientStock(f"Only {self.stock_available} units of {self.name} are in stock.")
            for batch in batches:
                if quantity <= 0:
                    break
                taken = min(batch.quantity_remaining, quantity)
                batch.quantity_remaining -= taken
                batch.save(update_fields=["quantity_remaining"])
                quantity -= taken

    def __str__(self) -> str:
        return f"{self.name}"


class StockBatch(models.Model):
    class Meta:
        ordering = ("expiry_date", "id")

    drug = models.ForeignKey(to=Drug, on_delete=models.CASCADE, related_name="batches")
    supplier = models.ForeignKey(to=Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    quantity_received = models.PositiveIntegerField(_("Stock Purchased"))
    quantity_remaining = models.PositiveIntegerField(_("Stock Left"))
    expiry_date = models.DateField(_("Expiry Date"), null=True, blank=True)
    received_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    received_on = models.DateTimeField(_("Received on"), default=timezone.now)

    def save(self, *args, **kwargs):
        if self.quantity_remaining is None:
            self.quantity_remaining = self.quantity_received
        super().save(*args, **kwargs)


class Prescription(models.Model):
    class Meta:
        ordering = ("-id",)

    visit = models.ForeignKey(to="patients.Visit", on_delete=models.CASCADE, related_name="prescriptions")
    drug = models.ForeignKey(to=Drug, on_delete=models.PROTECT, related_name="prescriptions")
    dosage = models.CharField(_("Dosage"), max_length=128)
    duration = models.CharField(_("Duration"), max_length=128, null=True, blank=True)
    quantity = models.PositiveIntegerField(_("Prescribed Quantity"))
    notes = models.TextField(_("Notes"), null=True, blank=True)
    unit_price = models.DecimalField(_("Unit Price"), **MONEY)
    quantity_issued = models.PositiveIntegerField(_("Issued Quantity"), default=0)
    prescribed_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="prescriptions_written")
    issued_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="prescriptions_issued")
    issued_on = models.DateTimeField(_("Issued on"), null=True, blank=True)
    created_on = models.DateTimeField(_("Created on"), default=timezone.now)

    def save(self, *args, **kwargs):
        if self.unit_price is None:
            self.unit_price = self.drug.unit_price
        super().save(*args, **kwargs)

    @property
    def balance(self):
        return self.quantity - self.quantity_issued

    @property
    def amount(self):
        return self.unit_price * self.quantity

    @property
    def issued_amount(self):
        return self.unit_price * self.quantity_issued


class DepartmentRequest(models.Model):
    """A cardiology or radiology examination requested for a visit, and its report."""
    class Meta:
        ordering = ("-id",)

    DepartmentChoices = (
        ("cardiology", "Cardiology"),
        ("radiology", "Radiology"),
    )
    StatusChoices = (
        ("pending", "Pending"),
        ("completed", "Completed"),
    )

    department = models.CharField(_("Department"), max_length=32, choices=DepartmentChoices)
    visit = models.ForeignKey(to="patients.Visit", on_delete=models.CASCADE, related_name="department_requests")
    service = models.ForeignKey(to="finance.Service", on_delete=models.PROTECT)
    price = models.DecimalField(_("Price"), **MONEY)
    narration = models.TextField(_("Narration"), null=True, blank=True)
    status = models.CharField(_("Status"), max_length=32, choices=StatusChoices, default="pending")
    requested_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="department_requests")
    created_on = models.DateTimeField(_("Created on"), default=timezone.now)
    # report
    result = models.TextField(_("Result"), null=True, blank=True)
    reference_range = models.CharField(_("Reference Range"), max_length=256, null=True, blank=True)
    comments = models.TextField(_("Comments"), null=True, blank=True)
    reported_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="department_reports")
    reported_on = models.DateTimeField(_("Reported on"), null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.price is None:
            self.price = self.service.fee
        super().save(*args, **kwargs)


class TheatreBooking(models.Model):
    class Meta:
        ordering = ("-scheduled_for", "-id")

    StatusChoices = (
        ("scheduled", "Scheduled"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    )

    visit = models.ForeignKey(to="patients.Visit", on_delete=models.CASCADE, related_name="theatre_bookings")
    service = models.ForeignKey(to="finance.Service", on_delete=models.PROTECT, null=True, blank=True)
    surgery_type = models.CharField(_("Type of surgery"), max_length=256)
    body_location = models.CharField(_("Location on body"), max_length=256, null=True, blank=True)
    considerations = models.CharField(_("Considerations"), max_length=256, null=True, blank=True)
    requirements = models.TextField(_("Requirements"), null=True, blank=True)
    surgeon = models.ForeignKey(to="manager.Staff", on_delete=models.SET_NULL, null=True, blank=True, related_name="surgeries")
    anaesthetist = models.ForeignKey(to="manager.Staff", on_delete=models.SET_NULL, null=True, blank=True, related_name="anaesthesia")
    nurse_one = models.ForeignKey(to="manager.Staff", on_delete=models.SET_NULL, null=True, blank=True, related_name="theatre_nursing_one")
    nurse_two = models.ForeignKey(to="manager.Staff", on_delete=models.SET_NULL, null=True, blank=True, related_name="theatre_nursing_two")
    scheduled_for = models.DateTimeField(_("Date and time"))
    status = models.CharField(_("Status"), max_length=32, choices=StatusChoices, default="scheduled")
    created_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_on = models.DateTimeField(_("Created on"), default=timezone.now)


class DentalProcedure(models.Model):
    class Meta:
        ordering = ("-performed_on", "-id")

    ToothChoices = (
        ("Incisor", "Incisor"),
        ("Canine", "Canine"),
        ("Pre-molar", "Pre-molar"),
        ("Molar", "Molar"),
    )

    visit = models.ForeignKey(to="patients.Visit", on_delete=models.CASCADE, related_name="dental_procedures")
    tooth = models.CharField(_("Tooth name"), max_length=32, choices=ToothChoices)
    diagnosis = models.CharField(_("Diagnosis"), max_length=256)
    procedure = models.ForeignKey(to="finance.Service", on_delete=models.PROTECT)
    fee = models.DecimalField(_("Fee"), **MONEY)
    observations = models.TextField(_("Observation notes"), null=True, blank=True)
    description = models.TextField(_("Description notes"), null=True, blank=True)
    performed_on = models.DateTimeField(_("Date and time"), default=timezone.now)
    created_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.fee is None:
            self.fee = self.procedure.fee
        super().save(*args, **kwargs)


def exam_image_path(instance, filename):
    return f"imaging/{instance.request.department}/{instance.request_id}/{filename}"


class ExamImage(models.Model):
    """An image or DICOM file taken for an imaging examination."""
    class Meta:
        ordering = ("-uploaded_on", "-id")

    ViewChoices = (
        ("", "Not stated"),
        ("pa", "PA"),
        ("ap", "AP"),
        ("lateral", "Lateral"),
        ("oblique", "Oblique"),
        ("axial", "Axial"),
        ("other", "Other"),
    )

    request = models.ForeignKey(to=DepartmentRequest, on_delete=models.CASCADE, related_name="images")
    file = models.FileField(_("Image file"), upload_to=exam_image_path)
    view = models.CharField(_("View"), max_length=16, choices=ViewChoices, blank=True, default="")
    caption = models.CharField(_("Caption"), max_length=256, blank=True, default="")
    uploaded_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_on = models.DateTimeField(_("Uploaded"), default=timezone.now)

    IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp")

    @property
    def is_previewable(self):
        return self.file.name.lower().endswith(self.IMAGE_EXTENSIONS)

    @property
    def filename(self):
        return self.file.name.rsplit("/", 1)[-1]

    def __str__(self) -> str:
        return self.caption or self.filename
