from django.urls import path
from apps.lab import views as LabViews

app_name = "lab"

urlpatterns = [
    path("laboratory/", LabViews.LaboratoryView.as_view(), name="lab-home"),
    path("laboratory/requests/<int:pk>/", LabViews.LabRequestView.as_view(), name="lab-request"),
    path("laboratory/tests/<int:pk>/", LabViews.LabTestView.as_view(), name="lab-test"),
    path("laboratory/samples/collect/", LabViews.SampleCollectionView.as_view(), name="sample-collection"),
    path("laboratory/samples/", LabViews.SampleTrackingView.as_view(), name="sample-tracking"),
]
