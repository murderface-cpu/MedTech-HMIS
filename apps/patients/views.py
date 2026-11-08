from apps.manager.access import PATIENTS
from apps.manager.pages import PageView

from apps.patients import models as PatientModals
from apps.manager import models as ManagerModels
from apps.doctor import models as DoctorModels
from apps.finance import models as FinanceModels


class PatientsModuleView(PageView):
    module = PATIENTS

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "gender_choices": ManagerModels.Person.GenderChoices,
            "relationship_choices": PatientModals.NextOfKin.RelationshipChoices,
            "doctor_specialities": DoctorModels.DoctorSpeciality.objects.all(),
            "visit_categories": ManagerModels.VisitCategory.objects.all(),
            "doctors": [
                {
                    "doctor" : doctor,
                    "specialities" : [speciality.name for speciality in doctor.speciality.all()]
                } for doctor in DoctorModels.Doctor.objects.exclude(staff__is_active=False).prefetch_related("speciality")
            ],
            "billing_types": FinanceModels.BillingType.objects.filter(is_active=True),
            "insurance_companies": FinanceModels.InsuranceCompany.objects.filter(is_active=True),
            "account_companies": FinanceModels.AccountCompany.objects.filter(is_active=True),
        })
        return context


class PatientView(PatientsModuleView):
    template_name = "patients/index.html"
    title = "Patients"

class VisitsView(PatientsModuleView):
    template_name = "patients/visits.html"
    title = "Visits"

class TriageView(PatientsModuleView):
    template_name = "patients/triage.html"
    title = "Triage"
