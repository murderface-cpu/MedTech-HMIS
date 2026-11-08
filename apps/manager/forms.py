from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone

from datetime import datetime, time

from apps.manager import models as ManagerModels
from apps.manager.access import MODULES
from apps.doctor import models as DoctorModels
from apps.departments import models as DepartmentModels

User = get_user_model()


class DateInput(forms.DateInput):
    input_type = "date"


class StaffForm(forms.ModelForm):
    date_of_birth = forms.DateField(label="Date of Birth", required=False, widget=DateInput)

    class Meta:
        model = ManagerModels.Staff
        fields = ("firstname", "middlename", "lastname", "gender", "date_of_birth", "nin", "telnumber",
                  "alttelnumber", "email", "address", "title", "speciality", "location", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["speciality"].help_text = "Doctors are listed under this speciality when visits are created."
        if self.instance.pk and self.instance.date_of_birth:
            self.initial["date_of_birth"] = self.instance.date_of_birth.date()

    def clean_date_of_birth(self):
        value = self.cleaned_data["date_of_birth"]
        return timezone.make_aware(datetime.combine(value, time())) if value else None

    def clean(self):
        cleaned = super().clean()
        title = cleaned.get("title")
        if title and title.kind == "doctor" and not cleaned.get("speciality"):
            self.add_error("speciality", "Select the doctor's speciality.")
        return cleaned


class StaffAccountForm(forms.Form):
    """The sign-in account of a staff member and the modules it may open."""
    username = forms.CharField(max_length=150, required=False,
                               help_text="Leave empty if this staff member does not sign in.")
    password = forms.CharField(widget=forms.PasswordInput(render_value=False), required=False, strip=False,
                               help_text="Required for a new account. Leave empty to keep the current password.")
    modules = forms.MultipleChoiceField(choices=[(module, module) for module in MODULES], required=False,
                                        widget=forms.CheckboxSelectMultiple, label="Modules")
    can_sign_in = forms.BooleanField(required=False, initial=True, label="Account can sign in")

    def __init__(self, *args, staff=None, **kwargs):
        self.user = staff.user if staff is not None else None
        super().__init__(*args, **kwargs)
        if self.user is not None:
            self.initial.update({
                "username": self.user.get_username(),
                "modules": list(self.user.groups.filter(name__in=MODULES).values_list("name", flat=True)),
                "can_sign_in": self.user.is_active,
            })

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if not username:
            if self.user is not None:
                raise forms.ValidationError("An existing account keeps its username; untick 'Account can sign in' to disable it.")
            return username
        taken = User.objects.filter(username__iexact=username)
        if self.user is not None:
            taken = taken.exclude(pk=self.user.pk)
        if taken.exists():
            raise forms.ValidationError("This username is already in use.")
        return username

    def clean(self):
        cleaned = super().clean()
        username = cleaned.get("username")
        password = cleaned.get("password")
        if username and self.user is None and not password:
            self.add_error("password", "Set a password for the new account.")
        if password:
            try:
                validate_password(password, self.user)
            except forms.ValidationError as error:
                self.add_error("password", error)
        return cleaned

    @transaction.atomic
    def save(self, staff):
        username = self.cleaned_data.get("username")
        if not username:
            return None
        user = self.user or User(username=username)
        user.username = username
        user.first_name = staff.firstname
        user.last_name = staff.lastname
        user.email = staff.email or ""
        user.is_active = self.cleaned_data["can_sign_in"] and staff.is_active
        if self.cleaned_data.get("password"):
            user.set_password(self.cleaned_data["password"])
        user.save()

        # only module groups are managed here; other groups the user belongs to stay
        selected = set(self.cleaned_data["modules"])
        for module in MODULES:
            group, _ = Group.objects.get_or_create(name=module)
            if module in selected:
                user.groups.add(group)
            else:
                user.groups.remove(group)

        if staff.user_id != user.pk:
            staff.user = user
            staff.save()
        return user


class StaffTitleForm(forms.ModelForm):
    class Meta:
        model = ManagerModels.StaffTitle
        fields = ("name", "kind")


class DoctorSpecialityForm(forms.ModelForm):
    class Meta:
        model = DoctorModels.DoctorSpeciality
        fields = ("name",)


class VisitCategoryForm(forms.ModelForm):
    class Meta:
        model = ManagerModels.VisitCategory
        fields = ("name",)


# ------------------------------------------------------------------ inventory

class DrugForm(forms.ModelForm):
    class Meta:
        model = DepartmentModels.Drug
        fields = ("name", "category", "manufacturer", "supplier", "unit_price", "is_active")


class NewDrugForm(DrugForm):
    opening_stock = forms.IntegerField(min_value=0, required=False, label="Opening stock",
                                       help_text="Units in store now, recorded as the first batch.")
    opening_expiry = forms.DateField(required=False, widget=DateInput, label="Opening stock expiry")


class StockBatchForm(forms.ModelForm):
    class Meta:
        model = DepartmentModels.StockBatch
        fields = ("drug", "supplier", "quantity_received", "expiry_date")
        widgets = {"expiry_date": DateInput}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["drug"].queryset = DepartmentModels.Drug.objects.filter(is_active=True)
        self.fields["quantity_received"].min_value = 1
        self.fields["quantity_received"].widget.attrs["min"] = 1


class SupplierForm(forms.ModelForm):
    class Meta:
        model = DepartmentModels.Supplier
        fields = ("name", "telephone", "email", "address")


class DrugCategoryForm(forms.ModelForm):
    class Meta:
        model = DepartmentModels.DrugCategory
        fields = ("name",)


# ------------------------------------------------------------------ configuration

class LocationForm(forms.ModelForm):
    class Meta:
        model = ManagerModels.Location
        fields = ("name", "code", "kind", "parent", "description", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        parents = ManagerModels.Location.objects.filter(is_active=True)
        if self.instance.pk:
            parents = parents.exclude(pk=self.instance.pk)
        self.fields["parent"].queryset = parents
        self.fields["code"].help_text = "A short unique code, such as OPD-1 or MAIN-STORE."

    def clean_parent(self):
        parent = self.cleaned_data.get("parent")
        node = parent
        while node is not None and self.instance.pk:
            if node.pk == self.instance.pk:
                raise forms.ValidationError("A location cannot sit inside itself.")
            node = node.parent
        return parent
