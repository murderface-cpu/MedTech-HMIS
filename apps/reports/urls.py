from django.urls import path

from apps.reports import views

app_name = "reports"

urlpatterns = [
    path("reports/", views.AnalyticsView.as_view(), name="analytics"),
    path("reports/moh/", views.MohReturnsView.as_view(), name="moh"),
]
