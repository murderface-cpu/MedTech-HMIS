"""Shared fixtures for the test suites of the apps."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from apps.manager import models as ManagerModels
from apps.patients import models as PatientModels
from apps.finance import models as FinanceModels
from apps.departments import models as DepartmentModels

PASSWORD = "Test-Pass-4821"


def make_user(username="staff", modules=(), **extra):
    user = get_user_model().objects.create_user(username=username, password=PASSWORD, **extra)
    for module in modules:
        user.groups.add(Group.objects.get_or_create(name=module)[0])
    return user


def make_patient(**overrides):
    data = {"firstname": "Mark", "middlename": "Alex", "lastname": "Peter", "gender": "Male",
            "telnumber": "+256786273721", "age": 22}
    data.update(overrides)
    return PatientModels.Patient.objects.create(**data)


def make_visit(patient=None, billing_kind=None, **overrides):
    category, _ = ManagerModels.VisitCategory.objects.get_or_create(name="Outpatient")
    visit = PatientModels.Visit.objects.create(patient=patient or make_patient(), category=category, **overrides)
    if billing_kind:
        billing_type = FinanceModels.BillingType.objects.filter(kind=billing_kind).first()
        billing = FinanceModels.Billing.objects.create(btype=billing_type)
        if billing_kind == "insurance":
            billing.insurance_company = FinanceModels.InsuranceCompany.objects.create(name="Test Insurer")
            billing.save()
        visit.billing = billing
        visit.save()
    return visit


def make_service(name="Wound dressing", category="procedure", fee="15000"):
    return FinanceModels.Service.objects.create(name=name, category=category, fee=Decimal(fee))


def make_drug(name="Paracetamol", price="500", stock=None, expiry=None):
    drug = DepartmentModels.Drug.objects.create(
        name=name, category=DepartmentModels.DrugCategory.objects.get_or_create(name="Tablet")[0], unit_price=Decimal(price))
    if stock:
        DepartmentModels.StockBatch.objects.create(drug=drug, quantity_received=stock, expiry_date=expiry)
    return drug
