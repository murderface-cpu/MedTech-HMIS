from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings

from apps.patients import models as PatientModals
from apps.manager import models as ManagerModels
from apps.doctor import models as DoctorModels

def default_currency():
    return settings.CURRENCY


class TestCategory(models.Model):
    name = models.CharField(_("Name"), max_length=256, null=False, blank=False)
    
    def __str__(self) -> str:
        return f"{self.name}"

class LabTest(models.Model):
    class Meta:
        ordering = ("-id","-updated_on")

    name = models.CharField(_("Name"), max_length=256, null=False, blank=False)
    description = models.TextField(_("Description"), null=True, blank=True)
    dafault_range = models.TextField(_("Default Range"), null=True, blank=True)
    category = models.ForeignKey(to=TestCategory, on_delete=models.CASCADE, related_name="test_category")
    price = models.DecimalField(_("Price"), decimal_places=3, max_digits=9, null=True, blank=True)
    currency = models.CharField(_("Currency"), max_length=5, default=default_currency)
    created_on = models.DateTimeField(_("Created on"), default=timezone.now)
    updated_on = models.DateTimeField(_("Updated on"), null=True, blank=True)
    has_subtest = models.BooleanField(_("Has Sub Test"), default=False)

    def __str__(self) -> str:
        return f"{self.name}"

    def save(self, *args, **kwargs):
        self.updated_on = timezone.now()
        super().save(*args, **kwargs)

class SubTest(models.Model):
    """A parameter measured by a lab test, e.g. Haemoglobin within a CBC."""
    test = models.ForeignKey(to=LabTest, on_delete=models.CASCADE, related_name="parameters")
    name = models.CharField(_("Name"), max_length=256, null=False, blank=False)
    dafault_range = models.TextField(_("Default Range"), null=True, blank=True)
    lower_limit = models.DecimalField(_("Lower limit"), decimal_places=3, max_digits=12, null=True, blank=True)
    upper_limit = models.DecimalField(_("Upper limit"), decimal_places=3, max_digits=12, null=True, blank=True)
    normal_result = models.CharField(_("Normal Result"), max_length=256, null=True, blank=True)
    units = models.CharField(_("Units"), max_length=64, null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.name}"

# Category of the requests the doctor sends to the laboratory (created by migration 0010)
LABORATORY_REQUEST_CATEGORY = "Laboratory"


class RequestCategory(models.Model):
    name = models.CharField(_("Name"), max_length=256, null=False, blank=False)
    
    def __str__(self) -> str:
        return f"{self.name}"

class Request(models.Model):
    class Meta:
        ordering = ("-id","-updated_on")

    visit = models.ForeignKey(to=PatientModals.Visit, on_delete=models.CASCADE, null=True, blank=True)
    category = models.ForeignKey(to=RequestCategory, on_delete=models.CASCADE, related_name="request_category", null=True, blank=True)
    doctor = models.ForeignKey(to=DoctorModels.Doctor, on_delete=models.CASCADE, related_name="doctor", null=True, blank=True)
    attendant = models.ForeignKey(to=DoctorModels.Doctor, on_delete=models.CASCADE, related_name="attendant", null=True, blank=True)
    created_on = models.DateTimeField(_("Created on"), default=timezone.now)
    updated_on = models.DateTimeField(_("Updated on"), null=True, blank=True)
    handled = models.BooleanField(_("Handled"), default=False)
    
    def __str__(self) -> str:
        return f"{self.visit}"

    def save(self, *args, **kwargs):
        self.updated_on = timezone.now()
        super().save(*args, **kwargs)

class AssignedTest(models.Model):
    class Meta:
        ordering = ("-id","-updated_on")

    request = models.ForeignKey(to=Request, on_delete=models.CASCADE, null=True)
    test = models.ForeignKey(to=LabTest, on_delete=models.CASCADE)
    price = models.DecimalField(_("Price"), decimal_places=3, max_digits=9, null=True, blank=True)
    naration = models.TextField(_("Naration"), null=True, blank=True)
    updated_on = models.DateTimeField(_("Updated on"), null=True, blank=True)
        
    def save(self, *args, **kwargs):
        self.updated_on = timezone.now()
    
        if self.price is None:
            self.price = self.test.price
        super().save(*args, **kwargs)

class TestResult(models.Model):
    class Meta:
        ordering = ("-id","-updated_on")

    test = models.ForeignKey(to=AssignedTest, on_delete=models.CASCADE)
    results = models.TextField(_("Test Results"), null=True, blank=True)
    created_on = models.DateTimeField(_("Created on"), default=timezone.now)
    updated_on = models.DateTimeField(_("Updated on"), null=True, blank=True)
        
    def save(self, *args, **kwargs):
        self.updated_on = timezone.now()
        super().save(*args, **kwargs)
    
    def __str__(self) -> str:
        return f"{self.test.test.name}"

class SubTestResult(models.Model):
    class Meta:
        ordering = ("-id","-updated_on")

    assigned_test = models.ForeignKey(to=AssignedTest, on_delete=models.CASCADE, null=True, related_name="parameter_results")
    subtest = models.ForeignKey(to=SubTest, on_delete=models.CASCADE)
    results = models.DecimalField(_("Result"), decimal_places=3, max_digits=12, null=True, blank=True)
    created_on = models.DateTimeField(_("Created on"), default=timezone.now)
    updated_on = models.DateTimeField(_("Updated on"), null=True, blank=True)
        
    def save(self, *args, **kwargs):
        self.updated_on = timezone.now()
        super().save(*args, **kwargs)
    
    def __str__(self) -> str:
        return f"{self.subtest.name}"


class Sample(models.Model):
    """A specimen taken for one or more tests of a lab request, tracked until it is analysed."""
    class Meta:
        ordering = ("-collected_on", "-id")

    SpecimenChoices = (
        ("whole_blood", "Whole blood (EDTA)"),
        ("serum", "Serum"),
        ("plasma", "Plasma"),
        ("urine", "Urine"),
        ("stool", "Stool"),
        ("sputum", "Sputum"),
        ("swab", "Swab"),
        ("csf", "Cerebrospinal fluid"),
        ("tissue", "Tissue"),
        ("other", "Other"),
    )
    StatusChoices = (
        ("collected", "Collected"),
        ("received_in_lab", "Received in lab"),
        ("in_analysis", "In analysis"),
        ("completed", "Completed"),
        ("rejected", "Rejected"),
    )
    NEXT_STATUS = {"collected": "received_in_lab", "received_in_lab": "in_analysis", "in_analysis": "completed"}

    accession_number = models.CharField(_("Accession number"), max_length=64, unique=True, null=True, blank=True)
    request = models.ForeignKey(to=Request, on_delete=models.CASCADE, related_name="samples")
    tests = models.ManyToManyField(to=AssignedTest, related_name="samples", verbose_name=_("Tests"))
    specimen = models.CharField(_("Specimen"), max_length=32, choices=SpecimenChoices)
    status = models.CharField(_("Status"), max_length=32, choices=StatusChoices, default="collected")
    notes = models.CharField(_("Notes"), max_length=256, blank=True, default="")
    rejection_reason = models.CharField(_("Reason for rejection"), max_length=256, blank=True, default="")
    collected_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="samples_collected")
    collected_on = models.DateTimeField(_("Collected"), default=timezone.now)
    received_on = models.DateTimeField(_("Received in lab"), null=True, blank=True)
    completed_on = models.DateTimeField(_("Completed"), null=True, blank=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from apps.manager import utils

        utils.assign_code(self, "accession_number", "LAB")

    @property
    def next_status(self):
        return self.NEXT_STATUS.get(self.status)

    @property
    def next_status_label(self):
        return {"received_in_lab": "Receive in lab", "in_analysis": "Start analysis", "completed": "Mark complete"}.get(self.next_status, "")

    @property
    def turnaround_minutes(self):
        end = self.completed_on or timezone.now()
        return max(int((end - self.collected_on).total_seconds() // 60), 0)

    def __str__(self) -> str:
        return f"{self.accession_number}"