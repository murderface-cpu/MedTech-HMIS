from django.urls import path
from apps.patients import views as PatientViews

app_name = "patients"

urlpatterns = [
    path("outpatient/patients/", PatientViews.PatientView.as_view(), name="patients-home"),
    path("outpatient/visits/", PatientViews.VisitsView.as_view(), name="patients-visits"),
    path("outpatient/triage/", PatientViews.TriageView.as_view(), name="patients-triage"),
]