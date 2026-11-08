from django.urls import path
from apps.manager import views as ManagerViews
from apps.reports.views import OverviewView

app_name = "manager"

urlpatterns = [
    path("", OverviewView.as_view(), name="home"),
    path("login/", ManagerViews.LoginView.as_view(), name="login"),
    path("logout/", ManagerViews.LogoutView.as_view(), name="logout"),
    path("password/", ManagerViews.PasswordChangeView.as_view(), name="password-change"),
    path("admin/", ManagerViews.AdminView.as_view(), name="manager-admin"),
    path("admin/staff/<int:pk>/", ManagerViews.StaffDetailView.as_view(), name="manager-staff"),
    path("admin/roles/", ManagerViews.RolesView.as_view(), name="roles"),
    path("admin/audit-log/", ManagerViews.AuditLogView.as_view(), name="audit-log"),
    path("admin/locations/", ManagerViews.LocationsView.as_view(), name="locations"),
    path("admin/locations/<int:pk>/", ManagerViews.LocationDetailView.as_view(), name="location"),
    path("inventory/", ManagerViews.InventoryView.as_view(), name="manager-inventory"),
    path("inventory/drugs/<int:pk>/", ManagerViews.DrugDetailView.as_view(), name="manager-drug"),
]
