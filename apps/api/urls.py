from django.urls import path
from apps.api import views as ApiViews

app_name = "api"

urlpatterns = [
    path("", ApiViews.ApiRootView.as_view(), name="root"),

    path("patients/", ApiViews.PatientListView.as_view(), name='patient_list'),
    path("patients/create/", ApiViews.PatientCreateView.as_view(), name='patient_create'),
    path("patients/<str:patient_id>/", ApiViews.PatientRetrieveView.as_view(), name='patients_retrieve'),
    path("patients/<str:patient_id>/update/", ApiViews.PatientUpdateView.as_view(), name='patient_update'),

    path("nextOfKin/<int:pk>/", ApiViews.NextOfKinRetrieveView.as_view(), name='nok_list'),
    path("nextOfKin/<int:pk>/update/", ApiViews.NextOfKinUpdateView.as_view(), name='nok_update'),
    path("patients/create/nextOfKin/", ApiViews.PatientNokCreateView.as_view(), name='patient_create_nok'),
    
    path("visits/", ApiViews.VisitsListView.as_view(), name='visit_list'),
    path("visits/<int:pk>", ApiViews.VisitsRetrieveView.as_view(), name='visit_retrieve'),
    path("visits/<int:pk>/update", ApiViews.VisitsUpdateView.as_view(), name='visit_update'),
    path("visits/create/", ApiViews.VisitCreateView.as_view(), name='visit_create'),
    path("patients/<str:patient_id>/visit/", ApiViews.PatientVisitListView.as_view(), name='patients_visit_retrieve'),
    path("visit/<int:pk>/triage/", ApiViews.VisitTriageListView.as_view(), name='visit_triage_retrieve'),
    path("visit/<int:pk>/patient/", ApiViews.VisitPatientListView.as_view(), name='visit_patient_retrieve'),
    
    path("triage/", ApiViews.TriageListView.as_view(), name='triage_list'),
    path("triage/<int:pk>", ApiViews.TriageRetrieveView.as_view(), name='triage_retrieve'),
    path("triage/<int:pk>/update/", ApiViews.TriageUpdateView.as_view(), name='triage_update'),
    path("triage/create/", ApiViews.TriageCreateView.as_view(), name='triage_create'),
    path("triage/<str:patient_id>/patient/", ApiViews.PatientTriageListView.as_view(), name='patients_triage_list'),
    
    path("allergy/", ApiViews.AllergyListView.as_view(), name='allergy_list'),
    path("allergy/<int:pk>", ApiViews.AllergyRetrieveView.as_view(), name='allergy_retrieve'),
    path("allergy/<int:pk>/update/", ApiViews.AllergyUpdateView.as_view(), name='allergy_update'),
    path("allergy/create/", ApiViews.AllergyCreateView.as_view(), name='allergy_create'),
    path("allergy/<int:pk>/delete/", ApiViews.AllergyDeleteView.as_view(), name='allergy_delete'),
    path("allergy/<str:patient_id>/patient/", ApiViews.PatientAllergyListView.as_view(), name='patients_allergy_list'),
    
    path("generalfindings/", ApiViews.GeneralFindingsListView.as_view(), name='general_findings_list'),
    path("generalfindings/<int:pk>", ApiViews.GeneralFindingsRetrieveView.as_view(), name='general_findings_retrieve'),
    path("generalfindings/<int:pk>/update/", ApiViews.GeneralFindingsUpdateView.as_view(), name='general_findings_update'),
    path("generalfindings/create/", ApiViews.GeneralFindingsCreateView.as_view(), name='general_findings_create'),
    path("generalfindings/<str:patient_id>/patient/", ApiViews.PatientGeneralFindingsListView.as_view(), name='patients_general_findings_list'),
    path("generalfindings/<str:visit_id>/visit/", ApiViews.VisitGeneralFindingsListView.as_view(), name='visit_general_findings_list'),
    
    path("paedeatricnotes/", ApiViews.PaedeatricsNotesListView.as_view(), name='paedeatrics_list'),
    path("paedeatricnotes/<int:pk>", ApiViews.PaedeatricsNotesRetrieveView.as_view(), name='paedeatrics_retrieve'),
    path("paedeatricnotes/<int:pk>/update/", ApiViews.PaedeatricsNotesUpdateView.as_view(), name='paedeatrics_update'),
    path("paedeatricnotes/create/", ApiViews.PaedeatricsNotesCreateView.as_view(), name='paedeatrics_create'),
    path("paedeatricnotes/<str:patient_id>/patient/", ApiViews.PatientPaedeatricsNotesListView.as_view(), name='patients_paedeatrics_list'),
    path("paedeatricnotes/<str:visit_id>/visit/", ApiViews.VisitPaedeatricsNotesListView.as_view(), name='visit_paedeatrics_list'),
    
    path("gynnotes/", ApiViews.GynNotesListView.as_view(), name='gyn_notes_list'),
    path("gynnotes/<int:pk>", ApiViews.GynNotesRetrieveView.as_view(), name='gyn_notes_retrieve'),
    path("gynnotes/<int:pk>/update/", ApiViews.GynNotesUpdateView.as_view(), name='gyn_notes_update'),
    path("gynnotes/create/", ApiViews.GynNotesCreateView.as_view(), name='gyn_notes_create'),
    path("gynnotes/<str:patient_id>/patient/", ApiViews.PatientGynNotesListView.as_view(), name='patients_gyn_notes_list'),
    path("gynnotes/<str:visit_id>/visit/", ApiViews.VisitGynNotesListView.as_view(), name='visit_gyn_notes_list'),

    path("diagnosis/create/", ApiViews.DiagnosisCreateView.as_view(), name='diagnosis_create'),
    path("diagnosis/<int:pk>/delete/", ApiViews.DiagnosisDeleteView.as_view(), name='diagnosis_delete'),
    path("diagnosis/<str:visit_id>/visit/", ApiViews.VisitDiagnosisListView.as_view(), name='visit_diagnosis_list'),

    path("drugs/", ApiViews.DrugListView.as_view(), name='drug_list'),
    path("prescriptions/create/", ApiViews.PrescriptionCreateView.as_view(), name='prescription_create'),
    path("prescriptions/<int:pk>/delete/", ApiViews.PrescriptionDeleteView.as_view(), name='prescription_delete'),
    path("prescriptions/<str:visit_id>/visit/", ApiViews.VisitPrescriptionListView.as_view(), name='visit_prescription_list'),

    path("services/", ApiViews.ServiceListView.as_view(), name='service_list'),
    path("visitservices/create/", ApiViews.VisitServiceCreateView.as_view(), name='visit_service_create'),
    path("visitservices/<int:pk>/delete/", ApiViews.VisitServiceDeleteView.as_view(), name='visit_service_delete'),
    path("visitservices/<str:visit_id>/visit/", ApiViews.VisitVisitServiceListView.as_view(), name='visit_service_list'),

    path("departmentrequests/create/", ApiViews.DepartmentRequestCreateView.as_view(), name='department_request_create'),
    path("departmentrequests/<int:pk>/delete/", ApiViews.DepartmentRequestDeleteView.as_view(), name='department_request_delete'),
    path("departmentrequests/<str:visit_id>/visit/", ApiViews.VisitDepartmentRequestListView.as_view(), name='visit_department_request_list'),

    # lab    
    path("lab/requests/", ApiViews.LabRequestListView.as_view(), name='lab_requests_list'),
    path("lab/requests/<int:pk>", ApiViews.LabRequestRetrieveView.as_view(), name='lab_requests_retrieve'),
    path("lab/requests/<int:pk>/update/", ApiViews.LabRequestUpdateView.as_view(), name='lab_requests_update'),
    path("lab/requests/create/", ApiViews.LabRequestCreateView.as_view(), name='lab_requests_create'),
    path("lab/requests/<str:patient_id>/patient/", ApiViews.PatientLabRequestListView.as_view(), name='patient_lab_requests_list'),
    path("lab/requests/<int:pk>/visit/", ApiViews.VisitLabRequestListView.as_view(), name='visit_lab_requests_list'),
    path("lab/requests/<str:category>/category/", ApiViews.CategoryLabRequestListView.as_view(), name='category_lab_requests_list'),
    
    path("lab/tests/", ApiViews.LabTestListView.as_view(), name='lab_tests_list'),
    path("lab/tests/<int:pk>", ApiViews.LabTestRetrieveView.as_view(), name='lab_tests_retrieve'),
    path("lab/tests/<int:pk>/update/", ApiViews.LabTestUpdateView.as_view(), name='lab_tests_update'),
    path("lab/tests/create/", ApiViews.LabTestCreateView.as_view(), name='lab_tests_create'),
    path("lab/tests/<int:pk>/request/", ApiViews.RequestLabTestListView.as_view(), name='request_lab_tests_list'),
    path("lab/tests/<str:category>/", ApiViews.CategoryLabTestListView.as_view(), name='category_lab_tests_list'),
]