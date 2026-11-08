from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import DecimalField, F, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.manager import utils

MONEY = dict(max_digits=14, decimal_places=2)


class BillingType(models.Model):
    KindChoices = (
        ("cash", "Paid by the patient"),
        ("insurance", "Insurance company"),
        ("account", "Account company"),
    )

    name = models.CharField(_("Name"), max_length=256, null=False, blank=False)
    kind = models.CharField(_("Kind"), max_length=32, choices=KindChoices, default="cash")
    is_active = models.BooleanField(_("Type is active"), default=True)

    def __str__(self) -> str:
        return f"{self.name}"


class Company(models.Model):
    class Meta:
        abstract = True
        ordering = ("name",)

    code_prefix = ""

    code = models.CharField(_("Code"), max_length=64, unique=True, null=True, blank=True)
    name = models.CharField(_("Company Name"), max_length=256, unique=True)
    email = models.EmailField(_("Company Email"), null=True, blank=True)
    telephone = models.CharField(_("Telephone"), max_length=64, null=True, blank=True)
    website = models.URLField(_("Website URL"), null=True, blank=True)
    physical_address = models.CharField(_("Physical Address"), max_length=256, null=True, blank=True)
    po_box = models.CharField(_("P.O. Box"), max_length=64, null=True, blank=True)
    contact_person = models.CharField(_("Contact Person"), max_length=256, null=True, blank=True)
    contact_phone = models.CharField(_("Contact Phone Number"), max_length=64, null=True, blank=True)
    contact_alt_phone = models.CharField(_("Contact Alternative Number"), max_length=64, null=True, blank=True)
    contact_email = models.EmailField(_("Contact Email"), null=True, blank=True)
    location = models.CharField(_("Location"), max_length=256, null=True, blank=True)
    is_active = models.BooleanField(_("Active"), default=True)
    created_on = models.DateTimeField(_("Created on"), default=timezone.now)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        utils.assign_code(self, "code", self.code_prefix)

    def __str__(self) -> str:
        return f"{self.name}"


class InsuranceCompany(Company):
    code_prefix = "INS"


class AccountCompany(Company):
    code_prefix = "CO"


class Billing(models.Model):
    btype = models.ForeignKey(to=BillingType, on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(_("Amount"), decimal_places=3, max_digits=10, default=0)
    paid = models.BooleanField(_("Paid"), default=False)
    insurance_company = models.ForeignKey(to=InsuranceCompany, on_delete=models.SET_NULL, null=True, blank=True)
    account_company = models.ForeignKey(to=AccountCompany, on_delete=models.SET_NULL, null=True, blank=True)

    @property
    def company(self):
        return self.insurance_company or self.account_company

    def __str__(self) -> str:
        return f"{self.btype} {self.company or ''}".strip()


class Service(models.Model):
    """Priced services offered by the hospital (lab tests and drugs keep their own prices)."""
    class Meta:
        ordering = ("category", "name")
        unique_together = ("category", "name")

    CategoryChoices = (
        ("consultation", "Consultations"),
        ("procedure", "Procedures"),
        ("dental", "Dental"),
        ("cardiology", "Cardiology"),
        ("radiology", "Radiology"),
        ("theatre", "Theatre"),
        ("eye", "Eye"),
        ("other", "Others"),
    )

    code = models.CharField(_("Code"), max_length=64, unique=True, null=True, blank=True)
    name = models.CharField(_("Service Name"), max_length=256)
    category = models.CharField(_("Category"), max_length=32, choices=CategoryChoices)
    fee = models.DecimalField(_("Fee"), **MONEY)
    is_active = models.BooleanField(_("Active"), default=True)
    created_on = models.DateTimeField(_("Created on"), default=timezone.now)
    updated_on = models.DateTimeField(_("Updated on"), null=True, blank=True)

    def save(self, *args, **kwargs):
        self.updated_on = timezone.now()
        super().save(*args, **kwargs)
        utils.assign_code(self, "code", "SER")

    def __str__(self) -> str:
        return f"{self.name}"


class VisitService(models.Model):
    """A priced service ordered for a visit (procedures, consultations, theatre, eye ...)."""
    class Meta:
        ordering = ("-id",)

    visit = models.ForeignKey(to="patients.Visit", on_delete=models.CASCADE, related_name="services")
    service = models.ForeignKey(to=Service, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(_("Quantity"), default=1)
    price = models.DecimalField(_("Price"), **MONEY)
    notes = models.TextField(_("Notes"), null=True, blank=True)
    ordered_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_on = models.DateTimeField(_("Created on"), default=timezone.now)

    @property
    def total(self):
        return self.price * self.quantity

    def save(self, *args, **kwargs):
        if self.price is None:
            self.price = self.service.fee
        super().save(*args, **kwargs)


class InvoiceQuerySet(models.QuerySet):
    def with_totals(self):
        """Annotate the line total, payments and refunds, so listing many invoices costs one query."""
        money = DecimalField(max_digits=16, decimal_places=2)

        def summed(model, expression):
            rows = (model.objects.filter(invoice=OuterRef("pk")).order_by().values("invoice")
                    .annotate(total=Sum(expression, output_field=money)).values("total"))
            return Coalesce(Subquery(rows, output_field=money), Value(Decimal("0")), output_field=money)

        return self.annotate(
            items_total=summed(InvoiceItem, F("unit_price") * F("quantity")),
            paid_total=summed(Payment, F("amount")),
            refunded_total=summed(Refund, F("amount")),
        )


class Invoice(models.Model):
    class Meta:
        ordering = ("-id",)

    StatusChoices = (
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("cancelled", "Cancelled"),
    )

    invoice_number = models.CharField(_("Invoice Number"), max_length=64, unique=True, null=True, blank=True)
    patient = models.ForeignKey(to="patients.Patient", on_delete=models.PROTECT, related_name="invoices")
    visit = models.ForeignKey(to="patients.Visit", on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    billing_type = models.ForeignKey(to=BillingType, on_delete=models.SET_NULL, null=True, blank=True)
    insurance_company = models.ForeignKey(to=InsuranceCompany, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    account_company = models.ForeignKey(to=AccountCompany, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    company_covered = models.DecimalField(_("Fees covered by Company"), default=0, **MONEY)
    status = models.CharField(_("Payment Status"), max_length=32, choices=StatusChoices, default="pending")
    issued_on = models.DateField(_("Date of Issue"), default=timezone.localdate)
    notes = models.TextField(_("Notes"), null=True, blank=True)
    created_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_on = models.DateTimeField(_("Created on"), default=timezone.now)

    objects = InvoiceQuerySet.as_manager()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        utils.assign_code(self, "invoice_number", "INV")

    @property
    def company(self):
        return self.insurance_company or self.account_company

    @property
    def total(self):
        if "items_total" in self.__dict__:
            return self.items_total
        return sum((item.total for item in self.items.all()), Decimal("0"))

    @property
    def patient_payable(self):
        return max(self.total - self.company_covered, Decimal("0"))

    @property
    def amount_paid(self):
        if "paid_total" in self.__dict__:
            return self.paid_total
        return self.payments.aggregate(total=Sum("amount"))["total"] or Decimal("0")

    @property
    def amount_refunded(self):
        if "refunded_total" in self.__dict__:
            return self.refunded_total
        return self.refunds.aggregate(total=Sum("amount"))["total"] or Decimal("0")

    @property
    def balance(self):
        return self.patient_payable - self.amount_paid + self.amount_refunded

    @property
    def services(self):
        return ", ".join(item.description for item in self.items.all())

    def forget_totals(self):
        """Drop annotated totals so the next read counts payments made since the invoice was loaded."""
        for name in ("items_total", "paid_total", "refunded_total"):
            self.__dict__.pop(name, None)

    def refresh_status(self):
        self.forget_totals()
        if self.status == "cancelled":
            return
        status = "paid" if self.items.exists() and self.balance <= 0 else "pending"
        if status != self.status:
            self.status = status
            self.save(update_fields=["status"])

    def __str__(self) -> str:
        return f"{self.invoice_number}"


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(to=Invoice, on_delete=models.CASCADE, related_name="items")
    description = models.CharField(_("Name of service"), max_length=256)
    quantity = models.PositiveIntegerField(_("Quantity"), default=1)
    unit_price = models.DecimalField(_("Unit Price"), **MONEY)
    # identifies the order this line was billed from, e.g. "visitservice:4", so it is billed once
    source = models.CharField(_("Source"), max_length=64, null=True, blank=True, db_index=True)

    @property
    def total(self):
        return self.unit_price * self.quantity

    def __str__(self) -> str:
        return f"{self.description}"


class Payment(models.Model):
    class Meta:
        ordering = ("-id",)

    MethodChoices = (
        ("cash", "Cash"),
        ("mpesa", "M-Pesa"),
        ("card", "Card"),
        ("bank", "Bank transfer"),
        ("cheque", "Cheque"),
    )

    invoice = models.ForeignKey(to=Invoice, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(_("Amount"), **MONEY)
    method = models.CharField(_("Paid by"), max_length=16, choices=MethodChoices, default="cash")
    narration = models.CharField(_("Narration"), max_length=256, null=True, blank=True)
    received_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    received_on = models.DateTimeField(_("Received on"), default=timezone.now)


class CompanyPayment(models.Model):
    """Money received from an insurance or account company."""
    class Meta:
        ordering = ("-id",)

    insurance_company = models.ForeignKey(to=InsuranceCompany, on_delete=models.PROTECT, null=True, blank=True, related_name="payments")
    account_company = models.ForeignKey(to=AccountCompany, on_delete=models.PROTECT, null=True, blank=True, related_name="payments")
    amount = models.DecimalField(_("Amount"), **MONEY)
    narration = models.CharField(_("Narration"), max_length=256, null=True, blank=True)
    received_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    received_on = models.DateTimeField(_("Received on"), default=timezone.now)

    @property
    def company(self):
        return self.insurance_company or self.account_company


class ExpenseCategory(models.Model):
    class Meta:
        ordering = ("name",)

    name = models.CharField(_("Name"), max_length=256, unique=True)

    def __str__(self) -> str:
        return f"{self.name}"


class Expenditure(models.Model):
    class Meta:
        ordering = ("-spent_on", "-id")

    category = models.ForeignKey(to=ExpenseCategory, on_delete=models.PROTECT)
    amount = models.DecimalField(_("Amount"), **MONEY)
    narration = models.CharField(_("Narration"), max_length=256, null=True, blank=True)
    spent_on = models.DateField(_("Date"), default=timezone.localdate)
    recorded_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_on = models.DateTimeField(_("Created on"), default=timezone.now)


class Refund(models.Model):
    class Meta:
        ordering = ("-id",)

    invoice = models.ForeignKey(to=Invoice, on_delete=models.PROTECT, related_name="refunds")
    amount = models.DecimalField(_("Amount"), **MONEY)
    narration = models.CharField(_("Narration"), max_length=256, null=True, blank=True)
    refunded_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_on = models.DateTimeField(_("Created on"), default=timezone.now)


# ------------------------------------------------------------------ M-Pesa, shifts, claims and eTIMS

class MpesaTransaction(models.Model):
    """A customer payment received on the hospital's paybill or till, matched to an invoice."""
    class Meta:
        ordering = ("-transacted_on", "-id")

    StatusChoices = (
        ("unmatched", "Unmatched"),
        ("matched", "Matched"),
        ("rejected", "Not for this hospital"),
    )

    receipt_number = models.CharField(_("M-Pesa receipt"), max_length=32, unique=True)
    phone = models.CharField(_("Phone number"), max_length=32)
    payer_name = models.CharField(_("Payer name"), max_length=128, blank=True, default="")
    account_reference = models.CharField(_("Account reference"), max_length=64, blank=True, default="",
                                         help_text=_("What the payer typed as the account, often the invoice or patient number."))
    amount = models.DecimalField(_("Amount"), **MONEY)
    transacted_on = models.DateTimeField(_("Paid at"), default=timezone.now)
    status = models.CharField(_("Status"), max_length=16, choices=StatusChoices, default="unmatched")
    payment = models.OneToOneField(to=Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name="mpesa")
    recorded_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="mpesa_recorded")
    matched_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="mpesa_matched")
    matched_on = models.DateTimeField(_("Matched"), null=True, blank=True)

    def save(self, *args, **kwargs):
        self.receipt_number = (self.receipt_number or "").strip().upper()
        super().save(*args, **kwargs)

    def suggested_invoices(self):
        """Pending invoices whose number or patient matches the account reference or phone."""
        reference = (self.account_reference or "").strip()
        invoices = Invoice.objects.filter(status="pending").select_related("patient").with_totals()
        found = []
        if reference:
            found += list(invoices.filter(invoice_number__iexact=reference))
            found += list(invoices.filter(patient__patient_id__iexact=reference))
        digits = "".join(character for character in self.phone if character.isdigit())[-9:]
        if digits:
            found += list(invoices.filter(patient__telnumber__endswith=digits))
        unique = []
        for invoice in found:
            if invoice not in unique:
                unique.append(invoice)
        return unique[:5]

    def __str__(self):
        return self.receipt_number


class CashierShift(models.Model):
    class Meta:
        ordering = ("-opened_on", "-id")

    cashier = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cashier_shifts")
    opened_on = models.DateTimeField(_("Opened"), default=timezone.now)
    opening_float = models.DecimalField(_("Opening float"), default=0, **MONEY)
    closed_on = models.DateTimeField(_("Closed"), null=True, blank=True)
    counted_cash = models.DecimalField(_("Cash counted"), null=True, blank=True, **MONEY)
    notes = models.CharField(_("Notes"), max_length=256, blank=True, default="")

    @property
    def is_open(self):
        return self.closed_on is None

    def window(self):
        return Payment.objects.filter(received_by=self.cashier, received_on__gte=self.opened_on,
                                      **({"received_on__lte": self.closed_on} if self.closed_on else {}))

    def takings(self):
        totals = {method: 0 for method, _ in Payment.MethodChoices}
        for method, amount in self.window().values_list("method", "amount"):
            totals[method] = totals.get(method, 0) + amount
        return totals

    @property
    def refunds_paid(self):
        refunds = Refund.objects.filter(refunded_by=self.cashier, created_on__gte=self.opened_on)
        if self.closed_on:
            refunds = refunds.filter(created_on__lte=self.closed_on)
        return refunds.aggregate(total=Sum("amount"))["total"] or Decimal("0")

    @property
    def expected_cash(self):
        return self.opening_float + Decimal(self.takings().get("cash", 0)) - self.refunds_paid

    @property
    def variance(self):
        if self.counted_cash is None:
            return None
        return self.counted_cash - self.expected_cash


class InsuranceClaim(models.Model):
    """A claim to an insurer (SHA or a private scheme) for the part of an invoice it covers."""
    class Meta:
        ordering = ("-created_on", "-id")

    StatusChoices = (
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("partial", "Partly approved"),
        ("rejected", "Rejected"),
        ("paid", "Paid"),
    )

    claim_number = models.CharField(_("Claim number"), max_length=64, unique=True, null=True, blank=True)
    invoice = models.OneToOneField(to=Invoice, on_delete=models.PROTECT, related_name="claim")
    insurer = models.ForeignKey(to=InsuranceCompany, on_delete=models.PROTECT, related_name="claims")
    member_number = models.CharField(_("Member number"), max_length=64, help_text=_("The patient's SHA or scheme membership number."))
    preauthorisation = models.CharField(_("Pre-authorisation code"), max_length=64, blank=True, default="")
    amount_claimed = models.DecimalField(_("Amount claimed"), **MONEY)
    amount_approved = models.DecimalField(_("Amount approved"), null=True, blank=True, **MONEY)
    status = models.CharField(_("Status"), max_length=16, choices=StatusChoices, default="draft")
    insurer_reference = models.CharField(_("Insurer reference"), max_length=64, blank=True, default="")
    rejection_reason = models.CharField(_("Reason given"), max_length=256, blank=True, default="")
    submitted_on = models.DateTimeField(_("Submitted"), null=True, blank=True)
    decided_on = models.DateTimeField(_("Decided"), null=True, blank=True)
    created_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_on = models.DateTimeField(_("Created on"), default=timezone.now)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        utils.assign_code(self, "claim_number", "CLM")

    @property
    def is_sha(self):
        return "sha" in self.insurer.name.lower() or "social health" in self.insurer.name.lower()

    def __str__(self):
        return f"{self.claim_number}"


class EtimsSubmission(models.Model):
    """The KRA eTIMS record of an invoice: the control unit number once it is transmitted."""
    class Meta:
        ordering = ("-created_on", "-id")

    StatusChoices = (
        ("submitted", "Accepted by KRA"),
        ("failed", "Failed"),
    )

    invoice = models.OneToOneField(to=Invoice, on_delete=models.PROTECT, related_name="etims")
    status = models.CharField(_("Status"), max_length=16, choices=StatusChoices)
    cu_invoice_number = models.CharField(_("Control unit invoice number"), max_length=64, blank=True, default="")
    receipt_signature = models.CharField(_("Receipt signature"), max_length=128, blank=True, default="")
    error_message = models.CharField(_("Error"), max_length=256, blank=True, default="")
    submitted_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_on = models.DateTimeField(_("Recorded"), default=timezone.now)


# ------------------------------------------------------------------ ledger

class LedgerAccount(models.Model):
    class Meta:
        ordering = ("code",)

    TypeChoices = (
        ("asset", "Asset"),
        ("liability", "Liability"),
        ("equity", "Equity"),
        ("income", "Income"),
        ("expense", "Expense"),
    )
    # the first digit of a code tells the type, as in most charts of accounts
    TYPE_PREFIX = {"asset": "1", "liability": "2", "equity": "3", "income": "4", "expense": "5"}

    code = models.CharField(_("Code"), max_length=16, unique=True)
    name = models.CharField(_("Account name"), max_length=128)
    account_type = models.CharField(_("Type"), max_length=16, choices=TypeChoices)
    parent = models.ForeignKey(to="self", on_delete=models.PROTECT, null=True, blank=True, related_name="children", verbose_name=_("Parent account"))
    description = models.CharField(_("Description"), max_length=256, blank=True, default="")
    is_active = models.BooleanField(_("In use"), default=True)

    def __str__(self):
        return f"{self.code} {self.name}"


class BankAccount(models.Model):
    class Meta:
        ordering = ("bank_name", "account_name")

    bank_name = models.CharField(_("Bank"), max_length=128)
    branch = models.CharField(_("Branch"), max_length=128, blank=True, default="")
    account_name = models.CharField(_("Account name"), max_length=128)
    account_number = models.CharField(_("Account number"), max_length=64, unique=True)
    currency = models.CharField(_("Currency"), max_length=8, default="KES")
    ledger_account = models.ForeignKey(to=LedgerAccount, on_delete=models.SET_NULL, null=True, blank=True,
                                       limit_choices_to={"account_type": "asset"}, verbose_name=_("Ledger account"))
    opening_balance = models.DecimalField(_("Opening balance"), default=0, **MONEY)
    opened_on = models.DateField(_("Balance as of"), default=timezone.localdate)
    is_active = models.BooleanField(_("In use"), default=True)

    @property
    def balance(self):
        totals = dict(self.transactions.values_list("kind").annotate(total=Sum("amount")))
        return self.opening_balance + (totals.get("deposit") or 0) - (totals.get("withdrawal") or 0)

    @property
    def masked_number(self):
        number = self.account_number
        return f"{'*' * max(len(number) - 4, 0)}{number[-4:]}"

    def __str__(self):
        return f"{self.bank_name} {self.masked_number}"


class BankTransaction(models.Model):
    class Meta:
        ordering = ("-transacted_on", "-id")

    KindChoices = (
        ("deposit", "Deposit"),
        ("withdrawal", "Withdrawal"),
    )

    account = models.ForeignKey(to=BankAccount, on_delete=models.PROTECT, related_name="transactions")
    kind = models.CharField(_("Kind"), max_length=16, choices=KindChoices)
    amount = models.DecimalField(_("Amount"), **MONEY)
    reference = models.CharField(_("Reference"), max_length=64, help_text=_("Deposit slip, cheque or transfer reference."))
    narration = models.CharField(_("Narration"), max_length=256, blank=True, default="")
    transacted_on = models.DateField(_("Date"), default=timezone.localdate)
    recorded_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_on = models.DateTimeField(default=timezone.now)
