from decimal import Decimal

from django import forms

from apps.finance import models as FinanceModels


class DateInput(forms.DateInput):
    input_type = "date"


def invoice_label(invoice):
    return f"{invoice.invoice_number} - {invoice.patient} (balance {invoice.balance})"


class InvoiceChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, invoice):
        return invoice_label(invoice)


def positive_amount(form):
    amount = form.cleaned_data["amount"]
    if amount is None or amount <= 0:
        raise forms.ValidationError("Enter an amount greater than zero.")
    return amount


class PaymentForm(forms.ModelForm):
    invoice = InvoiceChoiceField(queryset=FinanceModels.Invoice.objects.none())

    class Meta:
        model = FinanceModels.Payment
        fields = ("invoice", "amount", "method", "narration")

    def __init__(self, *args, invoice=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["method"].required = False
        self.fields["method"].help_text = "M-Pesa paybill payments are matched from M-Pesa payments instead."
        self.fields["invoice"].queryset = FinanceModels.Invoice.objects.filter(status="pending").select_related("patient").with_totals()
        if invoice is not None:
            self.fields["invoice"].initial = invoice.pk
            self.fields["invoice"].widget = forms.HiddenInput()

    clean_amount = positive_amount

    def clean_method(self):
        return self.cleaned_data.get("method") or "cash"

    def clean(self):
        cleaned = super().clean()
        invoice, amount = cleaned.get("invoice"), cleaned.get("amount")
        if invoice and amount and amount > invoice.balance:
            self.add_error("amount", f"The balance on {invoice.invoice_number} is {invoice.balance}.")
        return cleaned


class RefundForm(forms.ModelForm):
    invoice = InvoiceChoiceField(queryset=FinanceModels.Invoice.objects.none())

    class Meta:
        model = FinanceModels.Refund
        fields = ("invoice", "amount", "narration")

    def __init__(self, *args, invoice=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["invoice"].queryset = (
            FinanceModels.Invoice.objects.filter(pk__in=FinanceModels.Payment.objects.values("invoice")).select_related("patient").with_totals()
        )
        self.fields["narration"].required = True
        self.fields["narration"].label = "Reason"
        if invoice is not None:
            self.fields["invoice"].initial = invoice.pk
            self.fields["invoice"].widget = forms.HiddenInput()

    clean_amount = positive_amount

    def clean(self):
        cleaned = super().clean()
        invoice, amount = cleaned.get("invoice"), cleaned.get("amount")
        if invoice and amount:
            refundable = invoice.amount_paid - invoice.amount_refunded
            if amount > refundable:
                self.add_error("amount", f"At most {refundable} can be refunded on {invoice.invoice_number}.")
        return cleaned


class CompanyPaymentForm(forms.ModelForm):
    class Meta:
        model = FinanceModels.CompanyPayment
        fields = ("insurance_company", "account_company", "amount", "narration")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["insurance_company"].help_text = "Select either an insurance company or an account company."

    clean_amount = positive_amount

    def clean(self):
        cleaned = super().clean()
        if bool(cleaned.get("insurance_company")) == bool(cleaned.get("account_company")):
            raise forms.ValidationError("Select either an insurance company or an account company.")
        return cleaned


class ExpenditureForm(forms.ModelForm):
    class Meta:
        model = FinanceModels.Expenditure
        fields = ("category", "amount", "narration", "spent_on")
        widgets = {"spent_on": DateInput}

    clean_amount = positive_amount


class ExpenseCategoryForm(forms.ModelForm):
    class Meta:
        model = FinanceModels.ExpenseCategory
        fields = ("name",)


class InvoiceUpdateForm(forms.ModelForm):
    class Meta:
        model = FinanceModels.Invoice
        fields = ("billing_type", "insurance_company", "account_company", "company_covered", "issued_on", "notes")
        widgets = {"issued_on": DateInput, "notes": forms.Textarea(attrs={"rows": 2})}

    def clean(self):
        cleaned = super().clean()
        billing_type = cleaned.get("billing_type")
        kind = billing_type.kind if billing_type else "cash"
        if kind == "insurance" and not cleaned.get("insurance_company"):
            self.add_error("insurance_company", "Select the insurance company.")
        if kind == "account" and not cleaned.get("account_company"):
            self.add_error("account_company", "Select the account company.")
        if kind != "insurance":
            cleaned["insurance_company"] = None
        if kind != "account":
            cleaned["account_company"] = None
        covered = cleaned.get("company_covered") or Decimal("0")
        if kind == "cash":
            covered = Decimal("0")
        if covered < 0:
            self.add_error("company_covered", "The amount covered cannot be negative.")
        elif self.instance.pk and covered > self.instance.total:
            self.add_error("company_covered", f"The invoice total is {self.instance.total}.")
        cleaned["company_covered"] = covered
        return cleaned


class InvoiceItemForm(forms.ModelForm):
    class Meta:
        model = FinanceModels.InvoiceItem
        fields = ("description", "quantity", "unit_price")

    def clean_quantity(self):
        quantity = self.cleaned_data["quantity"]
        if not quantity:
            raise forms.ValidationError("Enter a quantity of at least 1.")
        return quantity

    def clean_unit_price(self):
        price = self.cleaned_data["unit_price"]
        if price is None or price < 0:
            raise forms.ValidationError("Enter a price of zero or more.")
        return price


class CompanyForm(forms.ModelForm):
    class Meta:
        fields = ("name", "email", "telephone", "website", "physical_address", "po_box", "contact_person",
                  "contact_phone", "contact_alt_phone", "contact_email", "location", "is_active")


class InsuranceCompanyForm(CompanyForm):
    class Meta(CompanyForm.Meta):
        model = FinanceModels.InsuranceCompany


class AccountCompanyForm(CompanyForm):
    class Meta(CompanyForm.Meta):
        model = FinanceModels.AccountCompany


class BillingTypeForm(forms.ModelForm):
    class Meta:
        model = FinanceModels.BillingType
        fields = ("name", "kind", "is_active")


class ServiceForm(forms.ModelForm):
    class Meta:
        model = FinanceModels.Service
        fields = ("name", "category", "fee", "is_active")

    def clean_fee(self):
        fee = self.cleaned_data["fee"]
        if fee is None or fee < 0:
            raise forms.ValidationError("Enter a fee of zero or more.")
        return fee


class PriceForm(forms.Form):
    """Changes the price of one record from the pricing lists."""
    pk = forms.IntegerField(widget=forms.HiddenInput)
    price = forms.DecimalField(min_value=0, max_digits=14, decimal_places=2)


class DateTimeInput(forms.DateTimeInput):
    input_type = "datetime-local"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%dT%H:%M", **kwargs)


# ------------------------------------------------------------------ M-Pesa

class MpesaTransactionForm(forms.ModelForm):
    class Meta:
        model = FinanceModels.MpesaTransaction
        fields = ("receipt_number", "amount", "phone", "payer_name", "account_reference", "transacted_on")
        widgets = {"transacted_on": DateTimeInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["receipt_number"].help_text = "The 10-character code on the M-Pesa message, such as SJK4H7Q2LM."
        self.fields["receipt_number"].widget.attrs.update({"autocapitalize": "characters", "maxlength": 10, "spellcheck": "false"})

    clean_amount = positive_amount

    def clean_receipt_number(self):
        code = self.cleaned_data["receipt_number"].strip().upper()
        if len(code) != 10 or not code.isalnum():
            raise forms.ValidationError("An M-Pesa receipt has 10 letters and numbers.")
        if FinanceModels.MpesaTransaction.objects.filter(receipt_number=code).exists():
            raise forms.ValidationError("This receipt is already recorded.")
        return code


class MpesaMatchForm(forms.Form):
    transaction = forms.ModelChoiceField(queryset=FinanceModels.MpesaTransaction.objects.filter(status="unmatched"))
    invoice = forms.ModelChoiceField(queryset=FinanceModels.Invoice.objects.filter(status="pending").select_related("patient").with_totals())

    def clean(self):
        cleaned = super().clean()
        transaction, invoice = cleaned.get("transaction"), cleaned.get("invoice")
        if transaction and invoice and transaction.amount > invoice.balance:
            raise forms.ValidationError(
                f"{transaction.receipt_number} is {transaction.amount:,.2f} but {invoice.invoice_number} has only {invoice.balance:,.2f} to pay. "
                "Record the difference as a refund or match it to another invoice.")
        return cleaned


# ------------------------------------------------------------------ shifts

class OpenShiftForm(forms.ModelForm):
    class Meta:
        model = FinanceModels.CashierShift
        fields = ("opening_float",)

    def clean_opening_float(self):
        value = self.cleaned_data["opening_float"]
        if value is None or value < 0:
            raise forms.ValidationError("Enter the float in the drawer, or zero.")
        return value


class CloseShiftForm(forms.ModelForm):
    class Meta:
        model = FinanceModels.CashierShift
        fields = ("counted_cash", "notes")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["counted_cash"].required = True
        self.fields["counted_cash"].help_text = "Count every note and coin in the drawer, float included."

    def clean_counted_cash(self):
        value = self.cleaned_data["counted_cash"]
        if value is None or value < 0:
            raise forms.ValidationError("Enter the cash counted, or zero.")
        return value


# ------------------------------------------------------------------ claims

class ClaimForm(forms.ModelForm):
    class Meta:
        model = FinanceModels.InsuranceClaim
        fields = ("member_number", "preauthorisation", "amount_claimed")

    def clean_amount_claimed(self):
        value = self.cleaned_data["amount_claimed"]
        if value is None or value <= 0:
            raise forms.ValidationError("Enter an amount greater than zero.")
        return value


class ClaimDecisionForm(forms.ModelForm):
    class Meta:
        model = FinanceModels.InsuranceClaim
        fields = ("status", "amount_approved", "insurer_reference", "rejection_reason")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = [choice for choice in FinanceModels.InsuranceClaim.StatusChoices if choice[0] != "draft"]

    def clean(self):
        cleaned = super().clean()
        status, approved = cleaned.get("status"), cleaned.get("amount_approved")
        if status in ("approved", "partial", "paid") and approved is None:
            self.add_error("amount_approved", "Enter the amount the insurer approved.")
        if approved is not None and approved > self.instance.amount_claimed:
            self.add_error("amount_approved", f"The claim was for {self.instance.amount_claimed:,.2f}.")
        if status == "rejected" and not cleaned.get("rejection_reason"):
            self.add_error("rejection_reason", "Record the reason the insurer gave.")
        return cleaned


# ------------------------------------------------------------------ eTIMS

class EtimsRecordForm(forms.ModelForm):
    class Meta:
        model = FinanceModels.EtimsSubmission
        fields = ("invoice", "status", "cu_invoice_number", "receipt_signature", "error_message")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["invoice"].widget = forms.HiddenInput()

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("status") == "submitted" and not cleaned.get("cu_invoice_number"):
            self.add_error("cu_invoice_number", "Enter the control unit invoice number from eTIMS.")
        if cleaned.get("status") == "failed" and not cleaned.get("error_message"):
            self.add_error("error_message", "Record the error eTIMS returned.")
        return cleaned


# ------------------------------------------------------------------ ledger

class LedgerAccountForm(forms.ModelForm):
    class Meta:
        model = FinanceModels.LedgerAccount
        fields = ("code", "name", "account_type", "parent", "description", "is_active")

    def clean(self):
        cleaned = super().clean()
        code, kind, parent = cleaned.get("code") or "", cleaned.get("account_type"), cleaned.get("parent")
        prefix = FinanceModels.LedgerAccount.TYPE_PREFIX.get(kind)
        if prefix and code and not code.startswith(prefix):
            self.add_error("code", f"{dict(FinanceModels.LedgerAccount.TypeChoices)[kind]} account codes start with {prefix}.")
        if parent and kind and parent.account_type != kind:
            self.add_error("parent", "The parent account must be of the same type.")
        if parent and self.instance.pk and parent.pk == self.instance.pk:
            self.add_error("parent", "An account cannot be its own parent.")
        return cleaned


class BankAccountForm(forms.ModelForm):
    class Meta:
        model = FinanceModels.BankAccount
        fields = ("bank_name", "branch", "account_name", "account_number", "currency", "ledger_account",
                  "opening_balance", "opened_on", "is_active")
        widgets = {"opened_on": DateInput}


class BankTransactionForm(forms.ModelForm):
    class Meta:
        model = FinanceModels.BankTransaction
        fields = ("kind", "amount", "reference", "narration", "transacted_on")
        widgets = {"transacted_on": DateInput}

    clean_amount = positive_amount
