from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.manager import models as ManagerModels

class DoctorSpeciality(models.Model):
    name = models.CharField(_("Name"), max_length=256, null=False, blank=False)
    def __str__(self) -> str:
        return f"{self.name}"

class Doctor(ManagerModels.Person):
    speciality = models.ManyToManyField(to=DoctorSpeciality, related_name="doctor_speciality")

    def __str__(self) -> str:
        return f"Dr. {self.getFullName()}"
    