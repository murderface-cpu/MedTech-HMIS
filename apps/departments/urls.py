from django.urls import path
from apps.departments import views as DepartmentsViews

app_name = "departments"

urlpatterns = [
    path("pharmacy/", DepartmentsViews.PharmacyView.as_view(), name="departments-pharmacy"),
    path("diagnostics/cardiology/", DepartmentsViews.CardiologyView.as_view(), name="departments-cardiology"),
    path("diagnostics/radiology/", DepartmentsViews.RadiologyView.as_view(), name="departments-radiology"),
    path("diagnostics/radiology/images/", DepartmentsViews.ImageArchiveView.as_view(), name="image-archive"),
    path("pharmacy/short-expiry/", DepartmentsViews.ShortExpiryView.as_view(), name="short-expiry"),
    path("diagnostics/<str:department>/requests/<int:pk>/", DepartmentsViews.DepartmentReportView.as_view(), name="departments-report"),
    path("procedures/theatre/", DepartmentsViews.TheatreView.as_view(), name="departments-theatre"),
    path("procedures/theatre/bookings/<int:pk>/", DepartmentsViews.TheatreBookingView.as_view(), name="departments-theatre-booking"),
    path("procedures/dental/", DepartmentsViews.DentalView.as_view(), name="departments-dental"),
]
