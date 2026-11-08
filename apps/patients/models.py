from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from django.conf import settings

from apps.manager import models as ManagerModels
from apps.manager import utils
from apps.doctor import models as DoctorModels
from apps.finance import models as FinanceModels

class Patient(ManagerModels.Person):
    patient_id = models.CharField(_("Patient ID"), max_length=256, null=True, blank=True, unique=True)

    def save(self, *args, **kwargs):
        super(Patient, self).save(*args, **kwargs)
        utils.assign_code(self, "patient_id", "P")

class NextOfKin(ManagerModels.Person):
    RelationshipChoices = (
        ("Husband", "Husband"),
        ("Wife", "Wife"),
        ("Father", "Father"),
        ("Mother", "Mother"),
        ("Brother", "Brother"),
        ("Sister", "Sister"),
        ("Son", "Son"),
        ("Daughter", "Daughter"),
        ("Guardian", "Guardian"),
        ("Other", "Other"),
    )
    relationship = models.CharField(_("relationship"), max_length=256, choices=RelationshipChoices, null=False, blank=False)
    patient = models.ForeignKey(to=Patient, on_delete=models.CASCADE, related_name="next_of_kin", null=True, blank=True)

class ActiveVisitManager(models.Manager):
    def get_queryset(self):
        # Override the default queryset to exclude inactive items
        return super().get_queryset().filter(complete=False)

class Visit(models.Model):
    objects = models.Manager()
    active = ActiveVisitManager()
    class Meta:
        ordering = ("-id","-updated_on")

    patient = models.ForeignKey(to=Patient, on_delete=models.CASCADE)
    visit_id = models.CharField(_("Visit Id"), max_length=256, null=True, blank=True, unique=True)
    doctor = models.ForeignKey(to=DoctorModels.Doctor, on_delete=models.SET_NULL, null=True)
    category = models.ForeignKey(to=ManagerModels.VisitCategory, on_delete=models.CASCADE)
    speciality = models.ForeignKey(to=DoctorModels.DoctorSpeciality, on_delete=models.SET_NULL, null=True)
    billing = models.OneToOneField(to=FinanceModels.Billing, on_delete=models.SET_NULL, null=True, blank=True)
    complete = models.BooleanField(_("Completed"), default=False)
    updated_on = models.DateTimeField(_("Updated on"), null=True, blank=True)
    created_on = models.DateTimeField(_("Created on"), default=timezone.now)
    visit_date = models.DateTimeField(_("Date"), default=timezone.now)

    def __str__(self) -> str:
        return f"{self.patient} - {self.visit_id}"


    def save(self, *args, **kwargs):
        self.updated_on = timezone.now()
        super().save(*args, **kwargs)
        utils.assign_code(self, "visit_id", "V")

class Triage(models.Model):
    class Meta:
        ordering = ("-id","-updated_on")
        
    visit = models.OneToOneField(to=Visit, on_delete=models.CASCADE)
    blood_pressure = models.CharField(_("Blood Pressure"), max_length=16, null=True, blank=True)
    heart_rate = models.DecimalField(_("Heart Rate"), decimal_places=2, max_digits=6, null=True, blank=True)
    respiratory_rate = models.DecimalField(_("Respiratory Rate"), decimal_places=2, max_digits=6, null=True, blank=True)
    temperature = models.DecimalField(_("Temperature"), decimal_places=2, max_digits=6, null=True, blank=True)
    weight = models.DecimalField(_("Weight"), decimal_places=2, max_digits=6, null=True, blank=True)
    height = models.DecimalField(_("Height"), decimal_places=2, max_digits=6, null=True, blank=True)
    oxygen_saturation = models.DecimalField(_("Oxygen Saturation"), decimal_places=2, max_digits=6, null=True, blank=True)
    MUAC = models.DecimalField(_("MUAC"), decimal_places=2, max_digits=6, null=True, blank=True)
    sign_symptoms = models.TextField(_("Signs and Symptoms"), null=True, blank=True) 
    injury_details = models.TextField(_("injury Details"), null=True, blank=True) 
    created_on = models.DateTimeField(_("Created on"), default=timezone.now)
    updated_on = models.DateTimeField(_("Updated on"), null=True, blank=True)

    def save(self, *args, **kwargs):
        self.updated_on = timezone.now()

        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.visit}"


class Allergy(models.Model):
    class Meta:
        ordering = ("-id","-updated_on")
        
    patient = models.ForeignKey(to=Patient, on_delete=models.CASCADE)
    name = models.CharField(_("Name"), max_length=256, null=True, blank=True)
    comment = models.TextField(_("Doctor's Comments"), null=True, blank=True)
    created_on = models.DateTimeField(_("Created on"), default=timezone.now)
    updated_on = models.DateTimeField(_("Updated on"), null=True, blank=True)
    
    def save(self, *args, **kwargs):
        self.updated_on = timezone.now()

        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name}"

class GeneralFinding(models.Model):
    class Meta:
        ordering = ("-id","-updated_on")
        
    visit = models.ForeignKey(to=Visit, on_delete=models.CASCADE)
    presenting_complaints = models.CharField(_("presenting complaints"), max_length=256, null=True, blank=True)
    clinical_notes = models.CharField(_("clinical notes"), max_length=256, null=True, blank=True)
    rohs = models.CharField(_("rohs"), max_length=256, null=True, blank=True)
    psh = models.CharField(_("psh"), max_length=256, null=True, blank=True)
    poh = models.CharField(_("poh"), max_length=256, null=True, blank=True)
    cvs = models.CharField(_("cvs"), max_length=256, null=True, blank=True)
    general_appearance = models.CharField(_("general appearance"), max_length=256, null=True, blank=True)
    respiratory = models.CharField(_("respiratory"), max_length=256, null=True, blank=True)
    ent = models.CharField(_("ent"), max_length=256, null=True, blank=True)
    abdomen_and_Gut = models.CharField(_("abdomen and Gut"), max_length=256, null=True, blank=True)
    cns = models.CharField(_("cns"), max_length=256, null=True, blank=True)
    eye = models.CharField(_("eye"), max_length=256, null=True, blank=True)
    muscular_skeletal = models.CharField(_("muscular skeletal"), max_length=256, null=True, blank=True)
    skin = models.CharField(_("skin"), max_length=256, null=True, blank=True)
    pv_pr = models.CharField(_("pv/pr"), max_length=256, null=True, blank=True)
    psychological_status = models.CharField(_("psychological status"), max_length=256, null=True, blank=True)
    provisional_status = models.CharField(_("provisional status"), max_length=256, null=True, blank=True)
    treatment_plan = models.CharField(_("treatment plan"), max_length=256, null=True, blank=True)
    created_on = models.DateTimeField(_("Created on"), default=timezone.now)
    updated_on = models.DateTimeField(_("Updated on"), null=True, blank=True)
    
    def save(self, *args, **kwargs):
        self.updated_on = timezone.now()

        super().save(*args, **kwargs)

class PaedeatricNote(models.Model):
    class Meta:
        ordering = ("-id","-updated_on")
        
    visit = models.ForeignKey(to=Visit, on_delete=models.CASCADE)
    notes = models.CharField(_("notes"), max_length=256, null=True, blank=True)
    created_on = models.DateTimeField(_("Created on"), default=timezone.now)
    updated_on = models.DateTimeField(_("Updated on"), null=True, blank=True)

    def save(self, *args, **kwargs):
        self.updated_on = timezone.now()

        super().save(*args, **kwargs)

class GynNote(models.Model):
    class Meta:
        ordering = ("-id","-updated_on")
        
    visit = models.ForeignKey(to=Visit, on_delete=models.CASCADE)
    notes = models.CharField(_("notes"), max_length=256, null=True, blank=True)
    created_on = models.DateTimeField(_("Created on"), default=timezone.now)
    updated_on = models.DateTimeField(_("Updated on"), null=True, blank=True)

    def save(self, *args, **kwargs):
        self.updated_on = timezone.now()

        super().save(*args, **kwargs)

class Diagnosis(models.Model):
    class Meta:
        ordering = ("-id",)

    visit = models.ForeignKey(to=Visit, on_delete=models.CASCADE)
    diagnosis = models.CharField(_("Diagnosis"), max_length=256)
    notes = models.TextField(_("Notes"), null=True, blank=True)
    created_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_on = models.DateTimeField(_("Created on"), default=timezone.now)

    def __str__(self) -> str:
        return f"{self.diagnosis}"
