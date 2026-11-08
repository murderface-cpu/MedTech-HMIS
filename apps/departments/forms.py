from django import forms
from django.utils import timezone

from apps.departments import models as DepartmentModels
from apps.finance import models as FinanceModels
from apps.manager import models as ManagerModels


class DateTimeInput(forms.DateTimeInput):
    input_type = "datetime-local"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%dT%H:%M", **kwargs)


class StaffChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, staff):
        return f"{staff.getFullName()} ({staff.title})"


def staff_of_kind(kind):
    return ManagerModels.Staff.objects.filter(is_active=True, title__kind=kind).select_related("title")


class IssueForm(forms.Form):
    prescription = forms.ModelChoiceField(queryset=DepartmentModels.Prescription.objects.select_related("drug"))
    quantity = forms.IntegerField(min_value=1)

    def clean(self):
        cleaned = super().clean()
        prescription, quantity = cleaned.get("prescription"), cleaned.get("quantity")
        if prescription and quantity and quantity > prescription.balance:
            raise forms.ValidationError(f"Only {prescription.balance} of {prescription.drug.name} remain to be issued.")
        return cleaned


class DepartmentReportForm(forms.ModelForm):
    class Meta:
        model = DepartmentModels.DepartmentRequest
        fields = ("result", "reference_range", "comments")
        labels = {"result": "Findings"}
        widgets = {"result": forms.Textarea(attrs={"rows": 6}), "comments": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["result"].required = True


class TheatreBookingForm(forms.ModelForm):
    surgeon = StaffChoiceField(queryset=staff_of_kind("doctor"), required=False)
    anaesthetist = StaffChoiceField(queryset=staff_of_kind("anaesthetist"), required=False)
    nurse_one = StaffChoiceField(queryset=staff_of_kind("nurse"), required=False, label="First nurse")
    nurse_two = StaffChoiceField(queryset=staff_of_kind("nurse"), required=False, label="Second nurse")

    class Meta:
        model = DepartmentModels.TheatreBooking
        fields = ("visit", "service", "surgery_type", "body_location", "considerations", "requirements",
                  "surgeon", "anaesthetist", "nurse_one", "nurse_two", "scheduled_for", "status")
        widgets = {"scheduled_for": DateTimeInput(), "requirements": forms.Textarea(attrs={"rows": 3})}
        labels = {"service": "Theatre service"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.patients.models import Visit

        visits = Visit.active.select_related("patient")
        if self.instance.pk:
            visits = Visit.objects.filter(pk=self.instance.visit_id) | visits
        self.fields["visit"].queryset = visits
        self.fields["service"].queryset = FinanceModels.Service.objects.filter(category="theatre", is_active=True)
        self.fields["scheduled_for"].input_formats = ["%Y-%m-%dT%H:%M"]
        if not self.instance.pk:
            self.fields.pop("status")

    def clean(self):
        cleaned = super().clean()
        nurses = [cleaned.get("nurse_one"), cleaned.get("nurse_two")]
        if all(nurses) and nurses[0] == nurses[1]:
            self.add_error("nurse_two", "Select two different nurses.")
        return cleaned


class DentalProcedureForm(forms.ModelForm):
    class Meta:
        model = DepartmentModels.DentalProcedure
        fields = ("tooth", "diagnosis", "procedure", "fee", "observations", "description", "performed_on")
        widgets = {"performed_on": DateTimeInput(), "observations": forms.Textarea(attrs={"rows": 2}),
                   "description": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["procedure"].queryset = FinanceModels.Service.objects.filter(category="dental", is_active=True)
        self.fields["fee"].required = False
        self.fields["fee"].help_text = "Leave empty to charge the procedure's standard fee."
        self.fields["performed_on"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["performed_on"].initial = timezone.localtime().strftime("%Y-%m-%dT%H:%M")

    def clean_fee(self):
        fee = self.cleaned_data.get("fee")
        if fee is not None and fee < 0:
            raise forms.ValidationError("Enter a fee of zero or more.")
        return fee


class ExamChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, request):
        return f"{request.visit.patient} - {request.service.name} ({request.created_on:%d %b %Y})"


class ExamImageForm(forms.ModelForm):
    ALLOWED = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".dcm", ".pdf")
    MAX_BYTES = 25 * 1024 * 1024

    request = ExamChoiceField(queryset=DepartmentModels.DepartmentRequest.objects.none(), label="Examination")

    class Meta:
        model = DepartmentModels.ExamImage
        fields = ("request", "file", "view", "caption")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["request"].queryset = DepartmentModels.DepartmentRequest.objects.filter(
            department="radiology").select_related("visit__patient", "service").order_by("-created_on")
        self.fields["file"].widget.attrs["accept"] = ",".join(self.ALLOWED)
        self.fields["file"].help_text = "PNG, JPEG, WebP, DICOM (.dcm) or PDF, up to 25 MB."

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if not upload.name.lower().endswith(self.ALLOWED):
            raise forms.ValidationError("Upload a PNG, JPEG, WebP, DICOM or PDF file.")
        if upload.size > self.MAX_BYTES:
            raise forms.ValidationError("The file is larger than 25 MB.")
        return upload
