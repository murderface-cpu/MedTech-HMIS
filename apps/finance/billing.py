"""What a visit owes: every priced order, as invoice lines that have not been billed yet."""
from decimal import Decimal

from apps.finance import models as FinanceModels

CENTS = Decimal("0.01")


def billable_items(visit):
    """All priced orders of the visit as {source, description, quantity, unit_price, kind}."""
    from apps.lab.models import AssignedTest
    from apps.departments.models import DentalProcedure, DepartmentRequest, Prescription
    from apps.clinical.models import BedCharge

    items = []
    for order in FinanceModels.VisitService.objects.filter(visit=visit).select_related("service"):
        items.append({"source": f"visitservice:{order.pk}", "description": order.service.name,
                      "quantity": order.quantity, "unit_price": order.price, "kind": order.service.get_category_display()})
    for assigned in AssignedTest.objects.filter(request__visit=visit).select_related("test"):
        price = assigned.price if assigned.price is not None else assigned.test.price
        items.append({"source": f"labtest:{assigned.pk}", "description": assigned.test.name,
                      "quantity": 1, "unit_price": (price or Decimal("0")).quantize(CENTS), "kind": "Laboratory"})
    for prescription in Prescription.objects.filter(visit=visit).select_related("drug"):
        items.append({"source": f"prescription:{prescription.pk}", "description": prescription.drug.name,
                      "quantity": prescription.quantity, "unit_price": prescription.unit_price, "kind": "Pharmacy"})
    for request in DepartmentRequest.objects.filter(visit=visit).select_related("service"):
        items.append({"source": f"deptrequest:{request.pk}", "description": request.service.name,
                      "quantity": 1, "unit_price": request.price, "kind": request.get_department_display()})
    for procedure in DentalProcedure.objects.filter(visit=visit).select_related("procedure"):
        items.append({"source": f"dental:{procedure.pk}", "description": f"{procedure.procedure.name} ({procedure.tooth})",
                      "quantity": 1, "unit_price": procedure.fee, "kind": "Dental"})
    for charge in BedCharge.objects.filter(admission__visit=visit).select_related("ward"):
        items.append({"source": charge.source, "description": f"Bed day, {charge.ward.name} ({charge.charge_date:%d %b %Y})",
                      "quantity": 1, "unit_price": charge.amount, "kind": "Inpatient"})
    for item in items:
        item["total"] = item["unit_price"] * item["quantity"]
    return items


def billed_sources(visit):
    """Sources already on an invoice of the visit that has not been cancelled."""
    return set(
        FinanceModels.InvoiceItem.objects
        .filter(invoice__visit=visit, source__isnull=False)
        .exclude(invoice__status="cancelled")
        .values_list("source", flat=True)
    )


def unbilled_items(visit):
    billed = billed_sources(visit)
    return [item for item in billable_items(visit) if item["source"] not in billed]


def is_billed(source):
    return FinanceModels.InvoiceItem.objects.filter(source=source).exclude(invoice__status="cancelled").exists()


def billed_sources_for(sources):
    """Which of `sources` are on an invoice that has not been cancelled."""
    return set(
        FinanceModels.InvoiceItem.objects.filter(source__in=list(sources))
        .exclude(invoice__status="cancelled").values_list("source", flat=True)
    )
