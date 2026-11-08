"""Stores: stock adjustments, purchase orders from suppliers and requisitions from departments."""
from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.finance.models import MONEY
from apps.manager import utils


class StockAdjustment(models.Model):
    """A change to a batch's count that is not a sale: expiry, damage, a stock count or a return."""
    class Meta:
        ordering = ("-adjusted_on", "-id")

    ReasonChoices = (
        ("count", "Stock count correction"),
        ("expired", "Expired"),
        ("damaged", "Damaged or broken"),
        ("returned", "Returned to supplier"),
        ("lost", "Lost or stolen"),
        ("other", "Other"),
    )

    batch = models.ForeignKey(to="departments.StockBatch", on_delete=models.PROTECT, related_name="adjustments")
    quantity_before = models.PositiveIntegerField(_("Before"))
    quantity_change = models.IntegerField(_("Change"))
    reason = models.CharField(_("Reason"), max_length=32, choices=ReasonChoices)
    notes = models.CharField(_("Notes"), max_length=256, blank=True, default="")
    adjusted_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    adjusted_on = models.DateTimeField(_("When"), default=timezone.now)

    @property
    def quantity_after(self):
        return self.quantity_before + self.quantity_change

    @property
    def value(self):
        return self.batch.drug.unit_price * self.quantity_change

    @classmethod
    def apply(cls, batch, change, reason, user, notes=""):
        from apps.departments.models import StockBatch

        with transaction.atomic():
            batch = StockBatch.objects.select_for_update().get(pk=batch.pk)
            if batch.quantity_remaining + change < 0:
                raise ValueError(f"The batch holds only {batch.quantity_remaining} units.")
            adjustment = cls.objects.create(batch=batch, quantity_before=batch.quantity_remaining, quantity_change=change,
                                            reason=reason, notes=notes, adjusted_by=user)
            batch.quantity_remaining += change
            batch.save(update_fields=["quantity_remaining"])
        return adjustment


class PurchaseOrder(models.Model):
    class Meta:
        ordering = ("-created_on", "-id")

    StatusChoices = (
        ("draft", "Draft"),
        ("sent", "Sent to supplier"),
        ("partial", "Partly received"),
        ("received", "Received"),
        ("cancelled", "Cancelled"),
    )

    order_number = models.CharField(_("Order number"), max_length=64, unique=True, null=True, blank=True)
    supplier = models.ForeignKey(to="departments.Supplier", on_delete=models.PROTECT, related_name="purchase_orders")
    status = models.CharField(_("Status"), max_length=32, choices=StatusChoices, default="draft")
    expected_on = models.DateField(_("Expected delivery"), null=True, blank=True)
    notes = models.TextField(_("Notes"), blank=True, default="")
    created_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="purchase_orders")
    created_on = models.DateTimeField(_("Created on"), default=timezone.now)
    sent_on = models.DateTimeField(_("Sent"), null=True, blank=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        utils.assign_code(self, "order_number", "PO")

    @property
    def total(self):
        return sum((line.total for line in self.lines.all()), Decimal("0"))

    @property
    def is_open(self):
        return self.status in ("sent", "partial")

    def refresh_status(self):
        lines = list(self.lines.all())
        if self.status in ("draft", "cancelled") or not lines:
            return
        if all(line.quantity_received >= line.quantity_ordered for line in lines):
            status = "received"
        elif any(line.quantity_received for line in lines):
            status = "partial"
        else:
            status = "sent"
        if status != self.status:
            self.status = status
            self.save(update_fields=["status"])

    def __str__(self):
        return f"{self.order_number}"


class PurchaseOrderLine(models.Model):
    order = models.ForeignKey(to=PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    drug = models.ForeignKey(to="departments.Drug", on_delete=models.PROTECT)
    quantity_ordered = models.PositiveIntegerField(_("Quantity"))
    unit_cost = models.DecimalField(_("Unit cost"), **MONEY)
    quantity_received = models.PositiveIntegerField(_("Received"), default=0)

    @property
    def total(self):
        return self.unit_cost * self.quantity_ordered

    @property
    def outstanding(self):
        return max(self.quantity_ordered - self.quantity_received, 0)


class Requisition(models.Model):
    """A department asking the stores for stock it will use."""
    class Meta:
        ordering = ("-requested_on", "-id")

    DepartmentChoices = (
        ("pharmacy", "Pharmacy"),
        ("laboratory", "Laboratory"),
        ("wards", "Wards"),
        ("theatre", "Theatre"),
        ("emergency", "Emergency"),
        ("dental", "Dental"),
        ("outpatient", "Outpatient clinics"),
    )
    StatusChoices = (
        ("pending", "Pending"),
        ("issued", "Issued"),
        ("partial", "Partly issued"),
        ("rejected", "Rejected"),
    )

    requisition_number = models.CharField(_("Requisition number"), max_length=64, unique=True, null=True, blank=True)
    department = models.CharField(_("Requesting department"), max_length=32, choices=DepartmentChoices)
    status = models.CharField(_("Status"), max_length=32, choices=StatusChoices, default="pending")
    notes = models.CharField(_("Notes"), max_length=256, blank=True, default="")
    requested_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="requisitions")
    requested_on = models.DateTimeField(_("Requested"), default=timezone.now)
    handled_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="requisitions_handled")
    handled_on = models.DateTimeField(_("Handled"), null=True, blank=True)
    response = models.CharField(_("Store response"), max_length=256, blank=True, default="")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        utils.assign_code(self, "requisition_number", "REQ")

    def __str__(self):
        return f"{self.requisition_number}"


class RequisitionLine(models.Model):
    requisition = models.ForeignKey(to=Requisition, on_delete=models.CASCADE, related_name="lines")
    drug = models.ForeignKey(to="departments.Drug", on_delete=models.PROTECT)
    quantity_requested = models.PositiveIntegerField(_("Requested"))
    quantity_issued = models.PositiveIntegerField(_("Issued"), default=0)
