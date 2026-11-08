"""Appointments, note templates, emergency care and inpatient wards."""
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.finance.models import MONEY
from apps.manager import utils


# ------------------------------------------------------------------ outpatient

class Appointment(models.Model):
    class Meta:
        ordering = ("scheduled_for", "id")

    StatusChoices = (
        ("booked", "Booked"),
        ("checked_in", "Checked in"),
        ("missed", "Missed"),
        ("cancelled", "Cancelled"),
    )

    patient = models.ForeignKey(to="patients.Patient", on_delete=models.CASCADE, related_name="appointments")
    doctor = models.ForeignKey(to="doctor.Doctor", on_delete=models.SET_NULL, null=True, blank=True, related_name="appointments")
    speciality = models.ForeignKey(to="doctor.DoctorSpeciality", on_delete=models.SET_NULL, null=True, blank=True)
    category = models.ForeignKey(to="manager.VisitCategory", on_delete=models.PROTECT, verbose_name=_("Visit category"))
    scheduled_for = models.DateTimeField(_("Date and time"))
    duration_minutes = models.PositiveIntegerField(_("Length (minutes)"), default=15)
    reason = models.CharField(_("Reason"), max_length=256, blank=True, default="")
    status = models.CharField(_("Status"), max_length=32, choices=StatusChoices, default="booked")
    visit = models.ForeignKey(to="patients.Visit", on_delete=models.SET_NULL, null=True, blank=True, related_name="appointments")
    created_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_on = models.DateTimeField(_("Created on"), default=timezone.now)

    def __str__(self):
        return f"{self.patient} at {timezone.localtime(self.scheduled_for):%d %b %Y %H:%M}"


class NoteTemplate(models.Model):
    """Reusable wording a doctor drops into a part of the clinical notes."""
    class Meta:
        ordering = ("section", "name")
        unique_together = ("section", "name")

    SectionChoices = (
        ("presenting_complaints", "Presenting complaints"),
        ("clinical_notes", "Clinical notes"),
        ("general_appearance", "General appearance"),
        ("cvs", "Cardiovascular"),
        ("respiratory", "Respiratory"),
        ("abdomen_and_Gut", "Abdomen"),
        ("cns", "Central nervous system"),
        ("treatment_plan", "Treatment plan"),
        ("discharge_summary", "Discharge summary"),
    )

    name = models.CharField(_("Name"), max_length=128)
    section = models.CharField(_("Part of the notes"), max_length=64, choices=SectionChoices)
    body = models.TextField(_("Wording"))
    is_active = models.BooleanField(_("In use"), default=True)
    created_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_on = models.DateTimeField(_("Created on"), default=timezone.now)
    updated_on = models.DateTimeField(_("Updated on"), auto_now=True)

    def __str__(self):
        return self.name


# ------------------------------------------------------------------ emergency

class EmergencyCase(models.Model):
    """A patient brought to the emergency department, triaged by acuity."""
    class Meta:
        ordering = ("acuity_rank", "arrived_on")

    AcuityChoices = (
        ("red", "Emergency (red)"),
        ("orange", "Very urgent (orange)"),
        ("yellow", "Urgent (yellow)"),
        ("green", "Routine (green)"),
    )
    ACUITY_RANK = {"red": 1, "orange": 2, "yellow": 3, "green": 4}
    # target minutes to be seen, from the South African Triage Scale used in Kenyan emergency departments
    ACUITY_TARGET = {"red": 0, "orange": 10, "yellow": 60, "green": 240}

    ArrivalChoices = (
        ("walk_in", "Walked in"),
        ("ambulance", "Ambulance"),
        ("referral", "Referred from another facility"),
        ("police", "Brought by police"),
        ("other", "Other"),
    )
    StatusChoices = (
        ("waiting", "Waiting"),
        ("in_treatment", "In treatment"),
        ("awaiting", "Awaiting admission"),
        ("admitted", "Admitted"),
        ("discharged", "Discharged"),
        ("transferred", "Transferred"),
        ("died", "Died"),
    )
    OPEN_STATUSES = ("waiting", "in_treatment", "awaiting")

    case_number = models.CharField(_("Case number"), max_length=64, unique=True, null=True, blank=True)
    patient = models.ForeignKey(to="patients.Patient", on_delete=models.PROTECT, related_name="emergency_cases")
    visit = models.OneToOneField(to="patients.Visit", on_delete=models.SET_NULL, null=True, blank=True, related_name="emergency_case")
    acuity = models.CharField(_("Triage category"), max_length=16, choices=AcuityChoices)
    acuity_rank = models.PositiveSmallIntegerField(default=4, editable=False)
    arrival_mode = models.CharField(_("Arrived by"), max_length=32, choices=ArrivalChoices, default="walk_in")
    chief_complaint = models.CharField(_("Chief complaint"), max_length=256)
    notes = models.TextField(_("Notes"), blank=True, default="")
    status = models.CharField(_("Status"), max_length=32, choices=StatusChoices, default="waiting")
    attending = models.ForeignKey(to="doctor.Doctor", on_delete=models.SET_NULL, null=True, blank=True, related_name="emergency_cases")
    arrived_on = models.DateTimeField(_("Arrived"), default=timezone.now)
    seen_on = models.DateTimeField(_("Seen"), null=True, blank=True)
    closed_on = models.DateTimeField(_("Closed"), null=True, blank=True)
    outcome_notes = models.CharField(_("Outcome notes"), max_length=256, blank=True, default="")
    created_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def save(self, *args, **kwargs):
        self.acuity_rank = self.ACUITY_RANK.get(self.acuity, 4)
        super().save(*args, **kwargs)
        utils.assign_code(self, "case_number", "ER")

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def waiting_minutes(self):
        end = self.seen_on or self.closed_on or timezone.now()
        return max(int((end - self.arrived_on).total_seconds() // 60), 0)

    @property
    def target_minutes(self):
        return self.ACUITY_TARGET.get(self.acuity, 240)

    @property
    def overdue(self):
        return self.status == "waiting" and self.waiting_minutes > self.target_minutes

    def __str__(self):
        return f"{self.case_number} {self.patient}"


# ------------------------------------------------------------------ inpatient

class Ward(models.Model):
    class Meta:
        ordering = ("name",)

    KindChoices = (
        ("general_male", "General (male)"),
        ("general_female", "General (female)"),
        ("paediatric", "Paediatric"),
        ("maternity", "Maternity"),
        ("icu", "Intensive care"),
        ("private", "Private"),
    )

    name = models.CharField(_("Ward name"), max_length=128, unique=True)
    kind = models.CharField(_("Kind"), max_length=32, choices=KindChoices, default="general_male")
    daily_rate = models.DecimalField(_("Bed charge per day"), **MONEY)
    location = models.ForeignKey(to="manager.Location", on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(_("Open"), default=True)

    def __str__(self):
        return self.name


class Bed(models.Model):
    class Meta:
        ordering = ("ward__name", "number")
        unique_together = ("ward", "number")

    StatusChoices = (
        ("available", "Available"),
        ("occupied", "Occupied"),
        ("cleaning", "Being cleaned"),
        ("out_of_service", "Out of service"),
    )

    ward = models.ForeignKey(to=Ward, on_delete=models.CASCADE, related_name="beds")
    number = models.CharField(_("Bed number"), max_length=16)
    status = models.CharField(_("Status"), max_length=32, choices=StatusChoices, default="available")

    def __str__(self):
        return f"{self.ward.name}, bed {self.number}"


class Admission(models.Model):
    class Meta:
        ordering = ("-requested_on", "-id")

    StatusChoices = (
        ("awaiting", "Awaiting a bed"),
        ("admitted", "Admitted"),
        ("discharged", "Discharged"),
        ("cancelled", "Cancelled"),
    )
    DischargeChoices = (
        ("home", "Discharged home"),
        ("referred", "Referred to another facility"),
        ("absconded", "Left against advice"),
        ("died", "Died"),
    )

    admission_number = models.CharField(_("Admission number"), max_length=64, unique=True, null=True, blank=True)
    patient = models.ForeignKey(to="patients.Patient", on_delete=models.PROTECT, related_name="admissions")
    visit = models.ForeignKey(to="patients.Visit", on_delete=models.SET_NULL, null=True, blank=True, related_name="admissions")
    emergency_case = models.ForeignKey(to=EmergencyCase, on_delete=models.SET_NULL, null=True, blank=True, related_name="admissions")
    requested_ward = models.ForeignKey(to=Ward, on_delete=models.SET_NULL, null=True, blank=True, related_name="requests", verbose_name=_("Ward requested"))
    bed = models.ForeignKey(to=Bed, on_delete=models.SET_NULL, null=True, blank=True, related_name="admissions")
    doctor = models.ForeignKey(to="doctor.Doctor", on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Admitting doctor"))
    reason = models.CharField(_("Reason for admission"), max_length=256)
    status = models.CharField(_("Status"), max_length=32, choices=StatusChoices, default="awaiting")
    requested_on = models.DateTimeField(_("Requested"), default=timezone.now)
    admitted_on = models.DateTimeField(_("Admitted"), null=True, blank=True)
    discharged_on = models.DateTimeField(_("Discharged"), null=True, blank=True)
    discharge_type = models.CharField(_("Outcome"), max_length=32, choices=DischargeChoices, blank=True, default="")
    discharge_summary = models.TextField(_("Discharge summary"), blank=True, default="")
    requested_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="admissions_requested")
    discharged_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="discharges")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        utils.assign_code(self, "admission_number", "IP")

    @property
    def ward(self):
        return self.bed.ward if self.bed_id else self.requested_ward

    def charge_days(self):
        """Every day the patient held a bed, the day of admission included."""
        if not self.admitted_on:
            return []
        import datetime

        start = timezone.localtime(self.admitted_on).date()
        end = timezone.localtime(self.discharged_on or timezone.now()).date()
        return [start + datetime.timedelta(days=offset) for offset in range((end - start).days + 1)]

    @property
    def days_admitted(self):
        return len(self.charge_days())

    def __str__(self):
        return f"{self.admission_number} {self.patient}"


class BedCharge(models.Model):
    """One day in a bed, charged at the ward's rate for that day."""
    class Meta:
        ordering = ("-charge_date", "-id")
        unique_together = ("admission", "charge_date")

    admission = models.ForeignKey(to=Admission, on_delete=models.CASCADE, related_name="bed_charges")
    ward = models.ForeignKey(to=Ward, on_delete=models.PROTECT)
    charge_date = models.DateField(_("Day"))
    amount = models.DecimalField(_("Amount"), **MONEY)
    created_on = models.DateTimeField(default=timezone.now)

    @property
    def source(self):
        return f"bedcharge:{self.pk}"
