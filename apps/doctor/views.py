from apps.manager.access import DOCTOR
from apps.manager.pages import PageView

from apps.finance import models as FinanceModels
from apps.departments import models as DepartmentModels
from apps.lab import models as LabModels
from apps.clinical.models import NoteTemplate

# Service categories the doctor orders directly for a visit, each shown in its own tab.
# Dental work is recorded (and billed) by the dental clinic; cardiology and radiology are requests.
ORDERED_SERVICE_CATEGORIES = ("consultation", "procedure", "theatre", "eye")


class DoctorHomeView(PageView):
    module = DOCTOR
    template_name = "doctor/index.html"
    title = "Doctor"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        labels = dict(FinanceModels.Service.CategoryChoices)
        staff = getattr(self.request.user, "staff", None)
        context.update({
            "service_tabs": [{"category": category, "label": labels[category]} for category in ORDERED_SERVICE_CATEGORIES],
            "department_tabs": [
                {"department": value, "label": label} for value, label in DepartmentModels.DepartmentRequest.DepartmentChoices
            ],
            "is_doctor": bool(staff and staff.doctor_id),
            "lab_request_category": LabModels.LABORATORY_REQUEST_CATEGORY,
            "note_templates": note_templates_by_section(),
        })
        return context


def note_templates_by_section():
    grouped = {}
    for item in NoteTemplate.objects.filter(is_active=True).only("name", "section", "body"):
        grouped.setdefault(item.section, []).append(item)
    return grouped
