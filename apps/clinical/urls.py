from django.urls import path

from apps.clinical import views

app_name = "clinical"

urlpatterns = [
    path("outpatient/appointments/", views.AppointmentsView.as_view(), name="appointments"),
    path("outpatient/queue/", views.QueueBoardView.as_view(), name="queue"),
    path("outpatient/note-templates/", views.NoteTemplatesView.as_view(), name="note-templates"),
    path("outpatient/note-templates/<int:pk>/", views.NoteTemplateDetailView.as_view(), name="note-template"),
    path("emergency/check-in/", views.EmergencyCheckInView.as_view(), name="emergency-check-in"),
    path("emergency/queue/", views.EmergencyQueueView.as_view(), name="emergency-queue"),
    path("inpatient/admissions/", views.AdmissionsView.as_view(), name="admissions"),
    path("inpatient/admissions/<int:pk>/", views.AdmissionDetailView.as_view(), name="admission"),
    path("inpatient/awaiting-admission/", views.AwaitingAdmissionView.as_view(), name="awaiting-admission"),
    path("inpatient/discharges/", views.DischargesView.as_view(), name="discharges"),
    path("inpatient/wards/", views.WardBoardView.as_view(), name="wards"),
    path("inpatient/bed-charges/", views.BedChargesView.as_view(), name="bed-charges"),
]
