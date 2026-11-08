from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify

# python
import uuid

from apps.manager import utils


class Person(models.Model):
    class Meta:
        abstract = True
        ordering = ("-id","-updated_on")

    GenderChoices = (
        ("Male", "Male"),
        ("Female", "Female")
    )

    firstname = models.CharField(_("First Name"), max_length=256, null=False, blank=False)
    middlename = models.CharField(_("Middle Name"), max_length=256, null=True, blank=True)
    lastname = models.CharField(_("Last Name"), max_length=256, null=False, blank=False)
    age = models.IntegerField(_("Age"), default=0, null=True, blank=True)
    date_of_birth = models.DateTimeField(_("Date of Birth"), null=True, blank=True)
    nin = models.CharField(_("National Identification Number"), max_length=256, null=True, blank=True, unique=True)
    gender = models.CharField(_("Gender"), max_length=256, choices=GenderChoices, null=False, blank=False)
    telnumber = models.CharField(_("Phone Number"), max_length=256, null=False, blank=False)
    alttelnumber = models.CharField(_("Alternative Phone Number"), max_length=256, null=True, blank=True)
    email = models.EmailField(_("Email"), null=True, blank=True)
    address = models.CharField(_("Address"), max_length=256, null=True, blank=True)
    slug = models.SlugField(
        _("Safe Url"), unique=True, blank=True, null=True, max_length=200
    )

    created_on = models.DateTimeField(_("Created on"), default=timezone.now)
    updated_on = models.DateTimeField(_("Updated on"), null=True, blank=True)

    def save(self, *args, **kwargs):
        self.updated_on = timezone.now()
        if not self.slug:
            self.slug = slugify(f"{self.getFullName()}{uuid.uuid4()}")[:200]
        # empty strings would violate the unique constraint on nin
        if not self.nin:
            self.nin = None

        if self.date_of_birth:
            self.age = utils.age_from_date_of_birth(self.date_of_birth)
        elif self.age:
            self.date_of_birth = utils.date_of_birth_from_age(self.age)

        super().save(*args, **kwargs)

    def getFullName(self):
        if self.middlename:
            return f"{self.firstname} {self.middlename} {self.lastname}"
        return f"{self.firstname} {self.lastname}"

    def __str__(self) -> str:
        return f"{self.getFullName()}"

class VisitCategory(models.Model):
    name = models.CharField(_("Name"), max_length=256, null=False, blank=False)
    created_on = models.DateTimeField(_("Created on"), default=timezone.now)
    updated_on = models.DateTimeField(_("Updated on"), null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.name}"

    def save(self, *args, **kwargs):
        self.updated_on = timezone.now()
        super().save(*args, **kwargs)


class StaffTitle(models.Model):
    class Meta:
        ordering = ("name",)

    KindChoices = (
        ("doctor", "Doctor"),
        ("anaesthetist", "Anaesthetist"),
        ("nurse", "Nurse"),
        ("other", "Other"),
    )

    name = models.CharField(_("Name"), max_length=256, unique=True)
    kind = models.CharField(_("Kind"), max_length=32, choices=KindChoices, default="other")

    def __str__(self) -> str:
        return f"{self.name}"


class Staff(Person):
    staff_number = models.CharField(_("Staff Number"), max_length=64, unique=True, null=True, blank=True)
    title = models.ForeignKey(to=StaffTitle, on_delete=models.PROTECT, related_name="staff")
    speciality = models.ForeignKey(to="doctor.DoctorSpeciality", on_delete=models.SET_NULL, null=True, blank=True)
    location = models.CharField(_("Location"), max_length=256, null=True, blank=True)
    user = models.OneToOneField(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="staff")
    doctor = models.OneToOneField(to="doctor.Doctor", on_delete=models.SET_NULL, null=True, blank=True, related_name="staff")
    is_active = models.BooleanField(_("Active"), default=True)

    # copied to the doctor record of staff whose title is a doctor title
    DOCTOR_FIELDS = ("firstname", "middlename", "lastname", "age", "date_of_birth", "gender",
                     "telnumber", "alttelnumber", "email", "address")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        utils.assign_code(self, "staff_number", "S")
        self.sync_doctor()

    def sync_doctor(self):
        """Doctors are assigned to visits through their doctor record; keep it in step with the staff record."""
        if self.title.kind != "doctor":
            return
        from apps.doctor.models import Doctor

        doctor = self.doctor or Doctor()
        for field in self.DOCTOR_FIELDS:
            setattr(doctor, field, getattr(self, field))
        doctor.save()
        if self.speciality_id:
            doctor.speciality.set([self.speciality_id])
        if self.doctor_id != doctor.pk:
            self.doctor = doctor
            Staff.objects.filter(pk=self.pk).update(doctor=doctor)


class Location(models.Model):
    """A place in the facility: building, floor, department, ward, room, clinic or store."""
    class Meta:
        ordering = ("name",)

    KindChoices = (
        ("building", "Building"),
        ("floor", "Floor"),
        ("department", "Department"),
        ("ward", "Ward"),
        ("clinic", "Clinic room"),
        ("theatre", "Theatre"),
        ("store", "Store"),
        ("office", "Office"),
    )

    name = models.CharField(_("Name"), max_length=128)
    code = models.CharField(_("Code"), max_length=32, unique=True)
    kind = models.CharField(_("Kind"), max_length=32, choices=KindChoices)
    parent = models.ForeignKey(to="self", on_delete=models.PROTECT, null=True, blank=True, related_name="children", verbose_name=_("Inside"))
    description = models.CharField(_("Description"), max_length=256, blank=True, default="")
    is_active = models.BooleanField(_("In use"), default=True)

    def __str__(self):
        return self.name

    @property
    def path(self):
        parts, node, seen = [], self, set()
        while node is not None and node.pk not in seen:
            seen.add(node.pk)
            parts.append(node.name)
            node = node.parent
        return " / ".join(reversed(parts))


class AuditEntry(models.Model):
    """Who changed what, and when. Written by apps.manager.audit; never edited."""
    class Meta:
        ordering = ("-created_on", "-id")
        verbose_name_plural = "audit entries"
        indexes = [models.Index(fields=["model", "object_id"]), models.Index(fields=["created_on"])]

    ActionChoices = (
        ("create", "Created"),
        ("update", "Changed"),
        ("delete", "Deleted"),
        ("sign_in", "Signed in"),
        ("sign_out", "Signed out"),
        ("sign_in_failed", "Sign-in failed"),
    )

    user = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_entries")
    username = models.CharField(_("Username"), max_length=150, blank=True, default="")
    action = models.CharField(_("Action"), max_length=32, choices=ActionChoices)
    model = models.CharField(_("Record type"), max_length=128, blank=True, default="")
    object_id = models.CharField(_("Record"), max_length=64, blank=True, default="")
    summary = models.CharField(_("Summary"), max_length=256, blank=True, default="")
    changes = models.JSONField(_("Changes"), default=dict, blank=True)
    ip_address = models.GenericIPAddressField(_("IP address"), null=True, blank=True)
    created_on = models.DateTimeField(_("When"), default=timezone.now, db_index=True)

    def __str__(self):
        return f"{self.username} {self.action} {self.model} {self.object_id}"
