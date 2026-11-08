from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

# Each module is unlocked by membership of the Django group with the same name.
PATIENTS = "Patients"
DOCTOR = "Doctor"
LABORATORY = "Laboratory"
CARDIOLOGY = "Cardiology"
RADIOLOGY = "Radiology"
PHARMACY = "Pharmacy"
INVENTORY = "Inventory"
THEATRE = "Theatre"
DENTAL = "Dental"
FINANCE = "Finance"
ADMINISTRATION = "Administration"

MODULES = [PATIENTS, DOCTOR, LABORATORY, CARDIOLOGY, RADIOLOGY, PHARMACY, INVENTORY, THEATRE, DENTAL, FINANCE, ADMINISTRATION]

def user_modules(user):
    if not user.is_authenticated or not user.is_active:
        return set()
    if user.is_superuser:
        return set(MODULES)
    cache = getattr(user, "_module_cache", None)
    if cache is None:
        cache = set(user.groups.filter(name__in=MODULES).values_list("name", flat=True))
        user._module_cache = cache
    return cache


def has_module_access(user, module):
    return module in user_modules(user)


class ModuleAccessMixin(LoginRequiredMixin):
    """Requires sign-in, then membership of the view's module group (superusers pass).

    A page shared by several modules lists them in `any_modules`; holding one of them is enough.
    """
    module = None
    any_modules = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        allowed = self.any_modules or (self.module,)
        if not any(has_module_access(request.user, module) for module in allowed):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class HasAnyModuleAccess(BasePermission):
    """API access for signed-in staff that belong to at least one module."""

    def has_permission(self, request, view):
        return bool(user_modules(request.user))
