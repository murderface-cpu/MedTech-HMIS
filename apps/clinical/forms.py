from django import forms
from django.utils import timezone

from apps.clinical import models as ClinicalModels
from apps.departments.forms import DateTimeInput
from apps.doctor import models as DoctorModels
from apps.finance import models as FinanceModels
from apps.manager import models as ManagerModels
from apps.patients import models as PatientModels


class PatientChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, patient):
        return f"{patient.getFullName()} ({patient.patient_id})"


class VisitChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, visit):
        return f"{visit.patient.getFullName()} ({visit.visit_id})"


def patients():
    return PatientModels.Patient.objects.order_by("firstname", "lastname")


def active_doctors():
    return DoctorModels.Doctor.objects.exclude(staff__is_active=False).order_by("firstname")


def active_visits():
    return PatientModels.Visit.active.select_related("patient").order_by("-visit_date")


# ------------------------------------------------------------------ appointments

class AppointmentForm(forms.ModelForm):
    patient = PatientChoiceField(queryset=PatientModels.Patient.objects.none())

    class Meta:
        model = ClinicalModels.Appointment
        fields = ("patient", "category", "speciality", "doctor", "scheduled_for", "duration_minutes", "reason")
        widgets = {"scheduled_for": DateTimeInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["patient"].queryset = patients()
        self.fields["doctor"].queryset = active_doctors()
        self.fields["duration_minutes"].widget.attrs["min"] = 5
        self.fields["doctor"].help_text = "Leave empty to see whichever doctor is free."

    def clean_scheduled_for(self):
        value = self.cleaned_data["scheduled_for"]
        if value and not self.instance.pk and value < timezone.now() - timezone.timedelta(minutes=5):
            raise forms.ValidationError("Choose a time from now on.")
        return value

    def clean(self):
        cleaned = super().clean()
        doctor, start = cleaned.get("doctor"), cleaned.get("scheduled_for")
        if doctor and start:
            length = timezone.timedelta(minutes=cleaned.get("duration_minutes") or 15)
            clashes = ClinicalModels.Appointment.objects.filter(
                doctor=doctor, status="booked", scheduled_for__lt=start + length,
                scheduled_for__gt=start - timezone.timedelta(hours=4),
            ).exclude(pk=self.instance.pk)
            for other in clashes:
                if other.scheduled_for + timezone.timedelta(minutes=other.duration_minutes) > start:
                    self.add_error("scheduled_for", f"{doctor} already sees {other.patient} at "
                                                    f"{timezone.localtime(other.scheduled_for):%H:%M}.")
                    break
        return cleaned


class CheckInForm(forms.Form):
    """How an appointment's visit is paid for when the patient arrives."""
    billing_type = forms.ModelChoiceField(queryset=FinanceModels.BillingType.objects.filter(is_active=True), label="Paid by")
    insurance_company = forms.ModelChoiceField(queryset=FinanceModels.InsuranceCompany.objects.filter(is_active=True), required=False)
    account_company = forms.ModelChoiceField(queryset=FinanceModels.AccountCompany.objects.filter(is_active=True), required=False)

    def clean(self):
        cleaned = super().clean()
        billing_type = cleaned.get("billing_type")
        if billing_type and billing_type.kind == "insurance" and not cleaned.get("insurance_company"):
            self.add_error("insurance_company", "Select the insurance company.")
        if billing_type and billing_type.kind == "account" and not cleaned.get("account_company"):
            self.add_error("account_company", "Select the account company.")
        return cleaned


class NoteTemplateForm(forms.ModelForm):
    class Meta:
        model = ClinicalModels.NoteTemplate
        fields = ("name", "section", "body", "is_active")
        widgets = {"body": forms.Textarea(attrs={"rows": 6})}


# ------------------------------------------------------------------ emergency

class EmergencyCheckInForm(forms.ModelForm):
    patient = PatientChoiceField(queryset=PatientModels.Patient.objects.none(), required=False,
                                 help_text="Leave empty for an unidentified patient; register them below.")
    # an unidentified or new patient
    firstname = forms.CharField(required=False, label="First name")
    lastname = forms.CharField(required=False, label="Last name")
    gender = forms.ChoiceField(choices=(("", "---------"),) + ManagerModels.Person.GenderChoices, required=False)
    age = forms.IntegerField(required=False, min_value=0, max_value=120, label="Approximate age")
    telnumber = forms.CharField(required=False, label="Phone number (patient or companion)")

    class Meta:
        model = ClinicalModels.EmergencyCase
        fields = ("patient", "firstname", "lastname", "gender", "age", "telnumber",
                  "acuity", "arrival_mode", "chief_complaint", "attending", "notes")
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}
        labels = {"attending": "Attending doctor"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["patient"].queryset = patients()
        self.fields["attending"].queryset = active_doctors()

    def clean(self):
        cleaned = super().clean()
        patient = cleaned.get("patient")
        if patient is None:
            if not cleaned.get("gender"):
                self.add_error("gender", "Select the gender of the new patient.")
        elif PatientModels.Visit.active.filter(patient=patient, emergency_case__isnull=False).exists():
            self.add_error("patient", "This patient is already in the emergency department.")
        return cleaned

    def resolve_patient(self):
        """The selected patient, or a new record for an unidentified one (named Unknown until identified)."""
        if self.cleaned_data.get("patient"):
            return self.cleaned_data["patient"]
        return PatientModels.Patient.objects.create(
            firstname=self.cleaned_data.get("firstname") or "Unknown",
            lastname=self.cleaned_data.get("lastname") or "Patient",
            gender=self.cleaned_data["gender"],
            age=self.cleaned_data.get("age") or 0,
            telnumber=self.cleaned_data.get("telnumber") or "Not given",
        )


class EmergencyOutcomeForm(forms.Form):
    OUTCOMES = (
        ("discharged", "Discharge home"),
        ("transferred", "Transfer to another facility"),
        ("died", "Record a death"),
    )
    outcome = forms.ChoiceField(choices=OUTCOMES)
    outcome_notes = forms.CharField(required=False, max_length=256, label="Notes")


# ------------------------------------------------------------------ inpatient

class AdmissionRequestForm(forms.ModelForm):
    visit = VisitChoiceField(queryset=PatientModels.Visit.objects.none(), label="Patient visit")

    class Meta:
        model = ClinicalModels.Admission
        fields = ("visit", "requested_ward", "doctor", "reason")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["visit"].queryset = active_visits().exclude(admissions__status__in=("awaiting", "admitted"))
        self.fields["doctor"].queryset = active_doctors()
        self.fields["requested_ward"].queryset = ClinicalModels.Ward.objects.filter(is_active=True)


class BedChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, bed):
        return f"{bed.ward.name}, bed {bed.number}"


class AssignBedForm(forms.Form):
    bed = BedChoiceField(queryset=ClinicalModels.Bed.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bed"].queryset = ClinicalModels.Bed.objects.filter(
            status="available", ward__is_active=True).select_related("ward")


class DischargeForm(forms.ModelForm):
    class Meta:
        model = ClinicalModels.Admission
        fields = ("discharge_type", "discharge_summary")
        widgets = {"discharge_summary": forms.Textarea(attrs={"rows": 6})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["discharge_type"].required = True
        self.fields["discharge_summary"].required = True


class WardForm(forms.ModelForm):
    beds = forms.IntegerField(min_value=0, max_value=200, required=False, label="Number of beds",
                              help_text="Beds are numbered from 1. You can add more later.")

    class Meta:
        model = ClinicalModels.Ward
        fields = ("name", "kind", "daily_rate", "location", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            del self.fields["beds"]


class AddBedsForm(forms.Form):
    ward = forms.ModelChoiceField(queryset=ClinicalModels.Ward.objects.all())
    count = forms.IntegerField(min_value=1, max_value=100, label="Beds to add")
