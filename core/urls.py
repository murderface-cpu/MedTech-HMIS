from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', include("apps.patients.urls", namespace="patients")),
    path('api/v1/', include("apps.api.urls", namespace="api")),
    path('outpatient/consultation/', include("apps.doctor.urls", namespace="doctor")),
    path('', include("apps.finance.urls", namespace="finance")),
    path('', include("apps.manager.urls", namespace="manager")),
    path('', include("apps.lab.urls", namespace="lab")),
    path('', include("apps.departments.urls", namespace="departments")),
    path('', include("apps.clinical.urls", namespace="clinical")),
    path('', include("apps.stores.urls", namespace="stores")),
    path('', include("apps.reports.urls", namespace="reports")),
    path('dashboard/', admin.site.urls),
]


def moved(old, pattern_name):
    """Permanent redirect from a pre-2026-10 path, keeping the query string, so bookmarks keep working."""
    return path(old, RedirectView.as_view(pattern_name=pattern_name, permanent=True, query_string=True))


urlpatterns += [
    moved("patients/", "patients:patients-home"),
    moved("visits/", "patients:patients-visits"),
    moved("triage/", "patients:patients-triage"),
    moved("doctor/", "doctor:doctor-home"),
    moved("cashier/", "finance:finance-cashier"),
    moved("invoices/", "finance:finance-invoices"),
    moved("invoices/<int:pk>/", "finance:finance-invoice"),
    moved("finances/", "finance:finance-finances"),
    moved("insurance/", "finance:finance-insurance"),
    moved("insurance/<str:kind>/<int:pk>/", "finance:finance-company"),
    moved("pricing/", "finance:finance-pricing"),
    moved("cardiology/", "departments:departments-cardiology"),
    moved("radiology/", "departments:departments-radiology"),
    moved("departments/<str:department>/requests/<int:pk>/", "departments:departments-report"),
    moved("theatre/", "departments:departments-theatre"),
    moved("theatre/bookings/<int:pk>/", "departments:departments-theatre-booking"),
    moved("dental/", "departments:departments-dental"),
    moved("app-admin/", "manager:manager-admin"),
    moved("app-admin/staff/<int:pk>/", "manager:manager-staff"),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
