from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as AuthViews
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View

from apps.manager import forms as ManagerForms
from apps.manager import models as ManagerModels
from apps.manager.access import ADMINISTRATION, INVENTORY, user_modules
from apps.manager.navigation import first_page_url
from apps.manager.pages import PageView
from apps.doctor import models as DoctorModels
from apps.departments import models as DepartmentModels


def page_title(title):
    return f"{settings.APPLICATION_NAME} - {title}"


class HomeView(LoginRequiredMixin, View):
    """Opens the first module the signed-in user may use."""

    def get(self, request, *args, **kwargs):
        url = first_page_url(request.user)
        if url:
            return redirect(url)
        return render(request, "auth/no_access.html", {"view_name": page_title("No access")}, status=403)


class LoginView(AuthViews.LoginView):
    template_name = "auth/index.html"
    redirect_authenticated_user = True
    extra_context = {"view_name": page_title("Sign in")}


class LogoutView(AuthViews.LogoutView):
    pass


class PasswordChangeView(AuthViews.PasswordChangeView):
    template_name = "auth/password_change.html"
    success_url = reverse_lazy("manager:home")
    extra_context = {"view_name": page_title("Change password")}

    def form_valid(self, form):
        messages.success(self.request, "Your password has been changed.")
        return super().form_valid(form)


# ------------------------------------------------------------------ administration

class AdminModuleView(PageView):
    module = ADMINISTRATION

    def check_can_manage(self, staff):
        """Only superusers may change the account of another superuser."""
        user = staff.user if staff is not None else None
        if user is not None and user.is_superuser and not self.request.user.is_superuser:
            raise PermissionDenied

    def save_staff(self, staff_form, account_form):
        with transaction.atomic():
            staff = staff_form.save()
            account_form.save(staff)
            # a deactivated staff member cannot sign in
            if staff.user_id and not staff.is_active and staff.user.is_active:
                staff.user.is_active = False
                staff.user.save(update_fields=["is_active"])
        return staff


class AdminView(AdminModuleView):
    template_name = "administration/index.html"
    title = "Admin"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("staff_form", ManagerForms.StaffForm())
        context.setdefault("account_form", ManagerForms.StaffAccountForm(prefix="account"))
        context.setdefault("title_form", ManagerForms.StaffTitleForm(prefix="title"))
        context.setdefault("speciality_form", ManagerForms.DoctorSpecialityForm(prefix="speciality"))
        context.setdefault("category_form", ManagerForms.VisitCategoryForm(prefix="category"))
        context.update({
            "staff_members": [
                {"staff": staff, "modules": sorted(user_modules(staff.user)) if staff.user else []}
                for staff in ManagerModels.Staff.objects.select_related("title", "speciality", "user")
            ],
            "staff_titles": ManagerModels.StaffTitle.objects.all(),
            "specialities": DoctorModels.DoctorSpeciality.objects.order_by("name"),
            "visit_categories": ManagerModels.VisitCategory.objects.order_by("name"),
        })
        return context

    def post_register_staff(self, request, *args, **kwargs):
        staff_form = ManagerForms.StaffForm(request.POST)
        account_form = ManagerForms.StaffAccountForm(request.POST, prefix="account")
        if staff_form.is_valid() and account_form.is_valid():
            staff = self.save_staff(staff_form, account_form)
            messages.success(request, f"{staff.getFullName()} has been registered as {staff.staff_number}.")
            return redirect("manager:manager-staff", pk=staff.pk)
        return self.render_invalid(staff_form=staff_form, account_form=account_form)

    def add_lookup(self, request, form_class, prefix, context_name, label):
        form = form_class(request.POST, prefix=prefix)
        if form.is_valid():
            form.save()
            messages.success(request, f"{label} '{form.instance}' has been added.")
            return self.redirect_back()
        return self.render_invalid(**{context_name: form})

    def post_add_title(self, request, *args, **kwargs):
        return self.add_lookup(request, ManagerForms.StaffTitleForm, "title", "title_form", "Staff title")

    def post_add_speciality(self, request, *args, **kwargs):
        return self.add_lookup(request, ManagerForms.DoctorSpecialityForm, "speciality", "speciality_form", "Speciality")

    def post_add_category(self, request, *args, **kwargs):
        return self.add_lookup(request, ManagerForms.VisitCategoryForm, "category", "category_form", "Visit category")


class StaffDetailView(AdminModuleView):
    template_name = "administration/staff.html"
    title = "Staff"

    def get_staff(self):
        staff = get_object_or_404(ManagerModels.Staff.objects.select_related("user", "title"), pk=self.kwargs["pk"])
        self.check_can_manage(staff)
        return staff

    def get_context_data(self, **kwargs):
        staff = self.get_staff()
        context = super().get_context_data(**kwargs)
        context.setdefault("staff_form", ManagerForms.StaffForm(instance=staff))
        context.setdefault("account_form", ManagerForms.StaffAccountForm(staff=staff, prefix="account"))
        context["staff"] = staff
        return context

    def post_update_staff(self, request, *args, **kwargs):
        staff = self.get_staff()
        staff_form = ManagerForms.StaffForm(request.POST, instance=staff)
        account_form = ManagerForms.StaffAccountForm(request.POST, staff=staff, prefix="account")
        if staff_form.is_valid() and account_form.is_valid():
            self.save_staff(staff_form, account_form)
            messages.success(request, f"{staff.getFullName()} has been updated.")
            return self.redirect_back()
        return self.render_invalid(staff_form=staff_form, account_form=account_form)


# ------------------------------------------------------------------ inventory

class InventoryModuleView(PageView):
    module = INVENTORY


class InventoryView(InventoryModuleView):
    template_name = "inventory/index.html"
    title = "Inventory"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("drug_form", ManagerForms.NewDrugForm(prefix="drug"))
        context.setdefault("stock_form", ManagerForms.StockBatchForm(prefix="stock", initial={"drug": self.request.GET.get("drug")}))
        context.setdefault("supplier_form", ManagerForms.SupplierForm(prefix="supplier"))
        context.setdefault("category_form", ManagerForms.DrugCategoryForm(prefix="category"))
        context.update({
            "drugs": DepartmentModels.Drug.objects.select_related("category", "supplier"),
            "batches": DepartmentModels.StockBatch.objects.select_related("drug", "supplier", "received_by").order_by("-received_on")[:200],
            "suppliers": DepartmentModels.Supplier.objects.all(),
            "drug_categories": DepartmentModels.DrugCategory.objects.all(),
        })
        return context

    def post_add_drug(self, request, *args, **kwargs):
        form = ManagerForms.NewDrugForm(request.POST, prefix="drug")
        if not form.is_valid():
            return self.render_invalid(drug_form=form)
        with transaction.atomic():
            drug = form.save()
            opening_stock = form.cleaned_data.get("opening_stock")
            if opening_stock:
                DepartmentModels.StockBatch.objects.create(
                    drug=drug, supplier=drug.supplier, quantity_received=opening_stock,
                    expiry_date=form.cleaned_data.get("opening_expiry"), received_by=request.user,
                )
        messages.success(request, f"{drug.name} has been added as {drug.drug_number}.")
        return self.redirect_back()

    def post_receive_stock(self, request, *args, **kwargs):
        form = ManagerForms.StockBatchForm(request.POST, prefix="stock")
        if not form.is_valid():
            return self.render_invalid(stock_form=form)
        batch = form.save(commit=False)
        batch.received_by = request.user
        batch.save()
        messages.success(request, f"Received {batch.quantity_received} units of {batch.drug.name}.")
        return self.redirect_back()

    def post_add_supplier(self, request, *args, **kwargs):
        form = ManagerForms.SupplierForm(request.POST, prefix="supplier")
        if not form.is_valid():
            return self.render_invalid(supplier_form=form)
        form.save()
        messages.success(request, f"Supplier {form.instance.name} has been added.")
        return self.redirect_back()

    def post_add_category(self, request, *args, **kwargs):
        form = ManagerForms.DrugCategoryForm(request.POST, prefix="category")
        if not form.is_valid():
            return self.render_invalid(category_form=form)
        form.save()
        messages.success(request, f"Drug category {form.instance.name} has been added.")
        return self.redirect_back()


class DrugDetailView(InventoryModuleView):
    template_name = "inventory/drug.html"
    title = "Drug"

    def get_drug(self):
        return get_object_or_404(DepartmentModels.Drug, pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        drug = self.get_drug()
        context = super().get_context_data(**kwargs)
        context.setdefault("drug_form", ManagerForms.DrugForm(instance=drug))
        context.update({
            "drug": drug,
            "batches": drug.batches.select_related("supplier", "received_by").order_by("-received_on"),
        })
        return context

    def post_update_drug(self, request, *args, **kwargs):
        drug = self.get_drug()
        form = ManagerForms.DrugForm(request.POST, instance=drug)
        if not form.is_valid():
            return self.render_invalid(drug_form=form)
        form.save()
        messages.success(request, f"{drug.name} has been updated.")
        return self.redirect_back()


# ------------------------------------------------------------------ roles, audit and locations

def module_pages():
    """For each module, the pages it opens, from the application menu."""
    from apps.manager.access import MODULES
    from apps.manager.navigation import WORKSPACES

    pages = {module: [] for module in MODULES}
    for workspace in WORKSPACES:
        if workspace.label == "Home":
            continue
        for section in workspace.sections:
            for page in section.pages:
                for module in page.modules:
                    if module in pages:
                        pages[module].append(f"{workspace.label}: {page.label}")
    return pages


class RolesView(AdminModuleView):
    template_name = "administration/roles.html"
    title = "Roles and permissions"

    def rows(self):
        from django.contrib.auth import get_user_model
        from apps.manager.access import MODULES

        rows = []
        accounts = get_user_model().objects.order_by("-is_active", "username").prefetch_related("groups")
        staff_by_user = {staff.user_id: staff for staff in ManagerModels.Staff.objects.filter(user__isnull=False).select_related("title")}
        for account in accounts:
            held = set(MODULES) if account.is_superuser else {group.name for group in account.groups.all()} & set(MODULES)
            rows.append({"account": account, "staff": staff_by_user.get(account.pk), "held": held,
                         "locked": account.is_superuser})
        return rows

    def get_context_data(self, **kwargs):
        from apps.manager.access import MODULES

        context = super().get_context_data(**kwargs)
        pages = module_pages()
        rows = self.rows()
        context.update({
            "modules": [{"name": module, "pages": pages[module],
                         "members": sum(1 for row in rows if module in row["held"] and row["account"].is_active)}
                        for module in MODULES],
            "module_names": MODULES,
            "rows": rows,
        })
        return context

    def post_save_matrix(self, request, *args, **kwargs):
        from django.contrib.auth.models import Group
        from apps.manager import audit
        from apps.manager.access import MODULES

        groups = {module: Group.objects.get_or_create(name=module)[0] for module in MODULES}
        changed = 0
        with transaction.atomic():
            for row in self.rows():
                account = row["account"]
                if row["locked"]:
                    continue
                wanted = set(request.POST.getlist(f"modules_{account.pk}")) & set(MODULES)
                current = row["held"]
                if wanted == current:
                    continue
                for module in wanted - current:
                    account.groups.add(groups[module])
                for module in current - wanted:
                    account.groups.remove(groups[module])
                changed += 1
                audit.write("update", model="Module access", object_id=account.pk, summary=account.get_username(),
                            changes={"changed": {"Modules": [sorted(current), sorted(wanted)]}})
        if changed:
            messages.success(request, f"Module access saved for {changed} account{'' if changed == 1 else 's'}.")
        else:
            messages.success(request, "Nothing changed.")
        return self.redirect_back(tab="access_matrix")


class AuditLogView(AdminModuleView):
    template_name = "administration/audit_log.html"
    title = "Audit log"
    page_size = 100

    def get_context_data(self, **kwargs):
        from django.core.paginator import Paginator
        from django.utils.dateparse import parse_date

        context = super().get_context_data(**kwargs)
        params = self.request.GET
        entries = ManagerModels.AuditEntry.objects.all()
        filters = {key: params.get(key, "").strip() for key in ("user", "action", "model", "q", "start", "end")}
        if filters["user"]:
            entries = entries.filter(username=filters["user"])
        if filters["action"]:
            entries = entries.filter(action=filters["action"])
        if filters["model"]:
            entries = entries.filter(model=filters["model"])
        if filters["q"]:
            entries = entries.filter(summary__icontains=filters["q"])
        if parse_date(filters["start"]):
            entries = entries.filter(created_on__date__gte=parse_date(filters["start"]))
        if parse_date(filters["end"]):
            entries = entries.filter(created_on__date__lte=parse_date(filters["end"]))
        page = Paginator(entries, self.page_size).get_page(params.get("page"))
        query = params.copy()
        query.pop("page", None)
        context.update({
            "page": page,
            "filters": filters,
            "query": query.urlencode(),
            "action_choices": ManagerModels.AuditEntry.ActionChoices,
            "usernames": ManagerModels.AuditEntry.objects.exclude(username="").order_by("username").values_list("username", flat=True).distinct(),
            "record_types": ManagerModels.AuditEntry.objects.exclude(model="").order_by("model").values_list("model", flat=True).distinct(),
        })
        return context


class LocationsView(AdminModuleView):
    template_name = "administration/locations.html"
    title = "Facility locations"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("location_form", ManagerForms.LocationForm(prefix="location"))
        locations = list(ManagerModels.Location.objects.select_related("parent"))
        by_parent = {}
        for location in locations:
            by_parent.setdefault(location.parent_id, []).append(location)

        def walk(parent_id, depth):
            for location in sorted(by_parent.get(parent_id, []), key=lambda item: item.name):
                yield {"location": location, "depth": depth, "children": len(by_parent.get(location.pk, []))}
                yield from walk(location.pk, depth + 1)

        context["tree"] = list(walk(None, 0))
        return context

    def post_add_location(self, request, *args, **kwargs):
        form = ManagerForms.LocationForm(request.POST, prefix="location")
        if not form.is_valid():
            return self.render_invalid(location_form=form)
        location = form.save()
        messages.success(request, f"{location.name} has been added.")
        return self.redirect_back(tab="location_list")


class LocationDetailView(AdminModuleView):
    template_name = "administration/location.html"
    title = "Location"

    def get_location(self):
        return get_object_or_404(ManagerModels.Location, pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        location = self.get_location()
        context = super().get_context_data(**kwargs)
        context.setdefault("location_form", ManagerForms.LocationForm(instance=location))
        context["location"] = location
        return context

    def post_update(self, request, *args, **kwargs):
        form = ManagerForms.LocationForm(request.POST, instance=self.get_location())
        if not form.is_valid():
            return self.render_invalid(location_form=form)
        form.save()
        messages.success(request, "The location has been saved.")
        return redirect("manager:locations")
