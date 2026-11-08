from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.db.models import Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.manager.access import FINANCE
from apps.manager.pages import PageView

from apps.finance import forms as FinanceForms
from apps.finance import models as FinanceModels
from apps.finance.billing import unbilled_items
from apps.patients import models as PatientModals
from apps.lab import models as LabModels
from apps.departments import models as DepartmentModels


def total(queryset, field="amount"):
    return queryset.aggregate(total=Sum(field))["total"] or Decimal("0")


class FinanceModuleView(PageView):
    module = FINANCE

    def save_form(self, form, context_name, message, **extra):
        """Saves a model form with `extra` attributes, or shows it again with its errors."""
        if not form.is_valid():
            return self.render_invalid(**{context_name: form})
        instance = form.save(commit=False)
        for field, value in extra.items():
            setattr(instance, field, value)
        instance.save()
        form.save_m2m()
        messages.success(self.request, message(instance) if callable(message) else message)
        return self.redirect_back()


# ------------------------------------------------------------------ cashier

class CashierView(FinanceModuleView):
    template_name = "cashier/index.html"
    title = "Cashier"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("payment_form", FinanceForms.PaymentForm(prefix="payment"))
        context.setdefault("company_payment_form", FinanceForms.CompanyPaymentForm(prefix="company"))
        context.setdefault("expenditure_form", FinanceForms.ExpenditureForm(prefix="expenditure"))
        context.setdefault("refund_form", FinanceForms.RefundForm(prefix="refund"))
        context.setdefault("category_form", FinanceForms.ExpenseCategoryForm(prefix="category"))
        today = timezone.localdate()
        context.update({
            "pending_invoices": FinanceModels.Invoice.objects.filter(status="pending").select_related(
                "patient", "billing_type", "insurance_company", "account_company").prefetch_related("items").with_totals(),
            "payments_today": FinanceModels.Payment.objects.filter(received_on__date=today).select_related("invoice__patient", "received_by"),
            "company_payments": FinanceModels.CompanyPayment.objects.select_related("insurance_company", "account_company", "received_by")[:100],
            "expenditures": FinanceModels.Expenditure.objects.select_related("category", "recorded_by")[:100],
            "refunds": FinanceModels.Refund.objects.select_related("invoice__patient", "refunded_by")[:100],
            "expense_categories": FinanceModels.ExpenseCategory.objects.all(),
        })
        context["takings_today"] = sum((payment.amount for payment in context["payments_today"]), Decimal("0"))
        return context

    def post_payment(self, request, *args, **kwargs):
        form = FinanceForms.PaymentForm(request.POST, prefix="payment")
        if not form.is_valid():
            return self.render_invalid(payment_form=form)
        payment = form.save(commit=False)
        payment.received_by = request.user
        payment.save()
        payment.invoice.refresh_status()
        messages.success(request, f"Received {payment.amount} on {payment.invoice.invoice_number}.")
        return self.redirect_back()

    def post_company_payment(self, request, *args, **kwargs):
        form = FinanceForms.CompanyPaymentForm(request.POST, prefix="company")
        return self.save_form(form, "company_payment_form", lambda payment: f"Received {payment.amount} from {payment.company}.",
                              received_by=request.user)

    def post_expenditure(self, request, *args, **kwargs):
        form = FinanceForms.ExpenditureForm(request.POST, prefix="expenditure")
        return self.save_form(form, "expenditure_form", lambda expense: f"Recorded {expense.amount} spent on {expense.category}.",
                              recorded_by=request.user)

    def post_expense_category(self, request, *args, **kwargs):
        form = FinanceForms.ExpenseCategoryForm(request.POST, prefix="category")
        return self.save_form(form, "category_form", lambda category: f"Expense category {category} has been added.")

    def post_refund(self, request, *args, **kwargs):
        form = FinanceForms.RefundForm(request.POST, prefix="refund")
        if not form.is_valid():
            return self.render_invalid(refund_form=form)
        refund = form.save(commit=False)
        refund.refunded_by = request.user
        refund.save()
        refund.invoice.refresh_status()
        messages.success(request, f"Refunded {refund.amount} on {refund.invoice.invoice_number}.")
        return self.redirect_back()


# ------------------------------------------------------------------ invoices

def company_filter_options():
    return (
        [{"value": f"insurance:{company.pk}", "label": company.name} for company in FinanceModels.InsuranceCompany.objects.all()]
        + [{"value": f"account:{company.pk}", "label": company.name} for company in FinanceModels.AccountCompany.objects.all()]
    )


def filter_by_company(queryset, value):
    kind, _, pk = (value or "").partition(":")
    if kind == "insurance" and pk.isdigit():
        return queryset.filter(insurance_company_id=pk)
    if kind == "account" and pk.isdigit():
        return queryset.filter(account_company_id=pk)
    return queryset


class InvoicesView(FinanceModuleView):
    template_name = "administration/invoices.html"
    title = "Invoices"

    def selected_visit(self, value):
        if value and str(value).isdigit():
            return PatientModals.Visit.objects.select_related("patient", "billing__btype").filter(pk=value).first()
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET
        invoices = FinanceModels.Invoice.objects.select_related(
            "patient", "visit", "billing_type", "insurance_company", "account_company").prefetch_related("items").with_totals()
        if params.get("status"):
            invoices = invoices.filter(status=params["status"])
        invoices = filter_by_company(invoices, params.get("company"))

        visit = self.selected_visit(params.get("visit"))
        context.update({
            "invoices": invoices[:500],
            "status_choices": FinanceModels.Invoice.StatusChoices,
            "company_options": company_filter_options(),
            "filters": {"status": params.get("status", ""), "company": params.get("company", "")},
            "visits": PatientModals.Visit.objects.select_related("patient").order_by("-id")[:300],
            "visit": visit,
            "unbilled": unbilled_items(visit) if visit else [],
        })
        context.setdefault("item_form", FinanceForms.InvoiceItemForm(prefix="extra", use_required_attribute=False))
        return context

    def post_create_invoice(self, request, *args, **kwargs):
        visit = self.selected_visit(request.POST.get("visit"))
        if visit is None:
            messages.error(request, "Select the visit to invoice.")
            return self.redirect_back()
        available = {item["source"]: item for item in unbilled_items(visit)}
        selected = [available[source] for source in request.POST.getlist("items") if source in available]

        # the optional extra line counts once it has a description
        extra_form = FinanceForms.InvoiceItemForm(request.POST, prefix="extra", use_required_attribute=False)
        has_extra = bool(request.POST.get("extra-description", "").strip())
        if has_extra and not extra_form.is_valid():
            return self.render_invalid(item_form=extra_form)
        if not selected and not has_extra:
            messages.error(request, "Select at least one item, or add an item, to invoice.")
            return self.redirect_back(visit=visit.pk)

        billing = visit.billing
        billing_type = billing.btype if billing else None
        with transaction.atomic():
            invoice = FinanceModels.Invoice.objects.create(
                patient=visit.patient, visit=visit, billing_type=billing_type,
                insurance_company=billing.insurance_company if billing else None,
                account_company=billing.account_company if billing else None,
                created_by=request.user,
            )
            for item in selected:
                invoice.items.create(description=item["description"], quantity=item["quantity"],
                                     unit_price=item["unit_price"], source=item["source"])
            if has_extra:
                extra = extra_form.save(commit=False)
                extra.invoice = invoice
                extra.save()
            # a company billed visit is covered in full unless the cashier changes it
            if billing_type and billing_type.kind != "cash":
                invoice.company_covered = invoice.total
                invoice.save(update_fields=["company_covered"])
            invoice.refresh_status()
        messages.success(request, f"Invoice {invoice.invoice_number} has been created.")
        return redirect("finance:finance-invoice", pk=invoice.pk)


class InvoiceDetailView(FinanceModuleView):
    template_name = "administration/invoice.html"
    title = "Invoice"

    def get_invoice(self):
        return get_object_or_404(
            FinanceModels.Invoice.objects.select_related("patient", "visit", "billing_type", "insurance_company", "account_company"),
            pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        invoice = self.get_invoice()
        context = super().get_context_data(**kwargs)
        editable = invoice.status != "cancelled"
        context.setdefault("invoice_form", FinanceForms.InvoiceUpdateForm(instance=invoice))
        context.setdefault("item_form", FinanceForms.InvoiceItemForm(prefix="item"))
        context.setdefault("payment_form", FinanceForms.PaymentForm(invoice=invoice, prefix="payment"))
        context.setdefault("refund_form", FinanceForms.RefundForm(invoice=invoice, prefix="refund"))
        context.update({
            "invoice": invoice,
            "items": invoice.items.all(),
            "payments": invoice.payments.select_related("received_by"),
            "refunds": invoice.refunds.select_related("refunded_by"),
            "editable": editable,
            "can_cancel": editable and invoice.amount_paid - invoice.amount_refunded == 0,
            "unbilled": unbilled_items(invoice.visit) if invoice.visit and editable else [],
        })
        return context

    def ensure_editable(self, invoice):
        if invoice.status == "cancelled":
            messages.error(self.request, "This invoice has been cancelled.")
            return False
        return True

    def post_update_invoice(self, request, *args, **kwargs):
        invoice = self.get_invoice()
        if not self.ensure_editable(invoice):
            return self.redirect_back()
        form = FinanceForms.InvoiceUpdateForm(request.POST, instance=invoice)
        if not form.is_valid():
            return self.render_invalid(invoice_form=form)
        form.save()
        invoice.refresh_status()
        messages.success(request, "The invoice has been updated.")
        return self.redirect_back()

    def post_add_item(self, request, *args, **kwargs):
        invoice = self.get_invoice()
        if not self.ensure_editable(invoice):
            return self.redirect_back()
        form = FinanceForms.InvoiceItemForm(request.POST, prefix="item")
        if not form.is_valid():
            return self.render_invalid(item_form=form)
        item = form.save(commit=False)
        item.invoice = invoice
        item.save()
        invoice.refresh_status()
        messages.success(request, f"{item.description} has been added to the invoice.")
        return self.redirect_back()

    def post_add_orders(self, request, *args, **kwargs):
        invoice = self.get_invoice()
        if not self.ensure_editable(invoice) or invoice.visit is None:
            return self.redirect_back()
        available = {item["source"]: item for item in unbilled_items(invoice.visit)}
        selected = [available[source] for source in request.POST.getlist("items") if source in available]
        for item in selected:
            invoice.items.create(description=item["description"], quantity=item["quantity"],
                                 unit_price=item["unit_price"], source=item["source"])
        invoice.refresh_status()
        messages.success(request, f"{len(selected)} item(s) added to the invoice.")
        return self.redirect_back()

    def post_remove_item(self, request, *args, **kwargs):
        invoice = self.get_invoice()
        if not self.ensure_editable(invoice):
            return self.redirect_back()
        item = get_object_or_404(invoice.items, pk=request.POST.get("item"))
        if invoice.total - item.total < invoice.amount_paid - invoice.amount_refunded + invoice.company_covered:
            messages.error(request, "Removing this item would leave the invoice below what has been paid and covered.")
            return self.redirect_back()
        item.delete()
        invoice.refresh_status()
        messages.success(request, f"{item.description} has been removed from the invoice.")
        return self.redirect_back()

    def post_payment(self, request, *args, **kwargs):
        invoice = self.get_invoice()
        form = FinanceForms.PaymentForm(request.POST, invoice=invoice, prefix="payment")
        if not form.is_valid():
            return self.render_invalid(payment_form=form)
        payment = form.save(commit=False)
        payment.received_by = request.user
        payment.save()
        invoice.refresh_status()
        messages.success(request, f"Received {payment.amount}.")
        return self.redirect_back()

    def post_refund(self, request, *args, **kwargs):
        invoice = self.get_invoice()
        form = FinanceForms.RefundForm(request.POST, invoice=invoice, prefix="refund")
        if not form.is_valid():
            return self.render_invalid(refund_form=form)
        refund = form.save(commit=False)
        refund.refunded_by = request.user
        refund.save()
        invoice.refresh_status()
        messages.success(request, f"Refunded {refund.amount}.")
        return self.redirect_back()

    def post_cancel(self, request, *args, **kwargs):
        invoice = self.get_invoice()
        if invoice.status == "cancelled" or invoice.amount_paid - invoice.amount_refunded != 0:
            messages.error(request, "Only invoices without payments can be cancelled. Refund the payments first.")
            return self.redirect_back()
        invoice.status = "cancelled"
        invoice.save(update_fields=["status"])
        messages.success(request, f"Invoice {invoice.invoice_number} has been cancelled; its orders can be invoiced again.")
        return self.redirect_back()


# ------------------------------------------------------------------ finances

class FinancesView(FinanceModuleView):
    template_name = "administration/finances.html"
    title = "Finances"

    def get_period(self):
        today = timezone.localdate()
        start = parse_date(self.request.GET.get("start") or "") or today.replace(day=1)
        end = parse_date(self.request.GET.get("end") or "") or today
        if start > end:
            start, end = end, start
        return start, end

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        start, end = self.get_period()
        payments = FinanceModels.Payment.objects.filter(received_on__date__range=(start, end)).select_related("invoice__patient", "received_by")
        company_payments = FinanceModels.CompanyPayment.objects.filter(received_on__date__range=(start, end)).select_related(
            "insurance_company", "account_company", "received_by")
        refunds = FinanceModels.Refund.objects.filter(created_on__date__range=(start, end)).select_related("invoice__patient", "refunded_by")
        expenditures = FinanceModels.Expenditure.objects.filter(spent_on__range=(start, end)).select_related("category", "recorded_by")

        totals = {
            "payments": total(payments),
            "company_payments": total(company_payments),
            "refunds": total(refunds),
            "expenditures": total(expenditures),
        }
        totals["income"] = totals["payments"] + totals["company_payments"] - totals["refunds"]
        totals["net"] = totals["income"] - totals["expenditures"]
        context.update({
            "start": start,
            "end": end,
            "payments": payments,
            "company_payments": company_payments,
            "refunds": refunds,
            "expenditures": expenditures,
            "expenditure_by_category": expenditures.values("category__name").annotate(total=Sum("amount")).order_by("category__name"),
            "totals": totals,
            "outstanding": sum((invoice.balance for invoice in FinanceModels.Invoice.objects.filter(status="pending").with_totals()), Decimal("0")),
        })
        return context


# ------------------------------------------------------------------ insurance and account companies

COMPANY_KINDS = {
    "insurance": (FinanceModels.InsuranceCompany, FinanceForms.InsuranceCompanyForm, "Insurance company"),
    "account": (FinanceModels.AccountCompany, FinanceForms.AccountCompanyForm, "Account company"),
}


class InsuranceView(FinanceModuleView):
    template_name = "insurance/index.html"
    title = "Insurance"

    def company_rows(self, model, kind):
        rows = []
        for company in model.objects.all():
            invoices = company.invoices.exclude(status="cancelled")
            billed = total(invoices, "company_covered")
            received = total(company.payments.all())
            rows.append({"company": company, "kind": kind, "billed": billed, "received": received, "balance": billed - received})
        return rows

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("insurance_form", FinanceForms.InsuranceCompanyForm(prefix="insurance"))
        context.setdefault("account_form", FinanceForms.AccountCompanyForm(prefix="account"))
        context.setdefault("billing_type_form", FinanceForms.BillingTypeForm(prefix="billing"))
        context.update({
            "insurance_companies": self.company_rows(FinanceModels.InsuranceCompany, "insurance"),
            "account_companies": self.company_rows(FinanceModels.AccountCompany, "account"),
            "billing_types": FinanceModels.BillingType.objects.order_by("name"),
        })
        return context

    def post_add_insurance(self, request, *args, **kwargs):
        form = FinanceForms.InsuranceCompanyForm(request.POST, prefix="insurance")
        return self.save_form(form, "insurance_form", lambda company: f"{company.name} has been added.")

    def post_add_account(self, request, *args, **kwargs):
        form = FinanceForms.AccountCompanyForm(request.POST, prefix="account")
        return self.save_form(form, "account_form", lambda company: f"{company.name} has been added.")

    def post_add_billing_type(self, request, *args, **kwargs):
        form = FinanceForms.BillingTypeForm(request.POST, prefix="billing")
        return self.save_form(form, "billing_type_form", lambda billing_type: f"Billing type {billing_type.name} has been added.")


class CompanyDetailView(FinanceModuleView):
    template_name = "insurance/company.html"
    title = "Company"

    def get_company(self):
        if self.kwargs["kind"] not in COMPANY_KINDS:
            raise Http404
        model, form_class, label = COMPANY_KINDS[self.kwargs["kind"]]
        return get_object_or_404(model, pk=self.kwargs["pk"]), form_class, label

    def get_context_data(self, **kwargs):
        company, form_class, label = self.get_company()
        context = super().get_context_data(**kwargs)
        context.setdefault("company_form", form_class(instance=company))
        invoices = company.invoices.select_related("patient").prefetch_related("items")
        context.update({
            "company": company,
            "kind": self.kwargs["kind"],
            "label": label,
            "invoices": invoices,
            "payments": company.payments.select_related("received_by"),
            "billed": total(invoices.exclude(status="cancelled"), "company_covered"),
            "received": total(company.payments.all()),
        })
        context["balance"] = context["billed"] - context["received"]
        return context

    def post_update_company(self, request, *args, **kwargs):
        company, form_class, label = self.get_company()
        form = form_class(request.POST, instance=company)
        return self.save_form(form, "company_form", f"{label} {company.name} has been updated.")


# ------------------------------------------------------------------ pricing

class PricingView(FinanceModuleView):
    template_name = "administration/pricing.html"
    title = "Pricing"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("service_form", FinanceForms.ServiceForm(prefix="service"))
        services = FinanceModels.Service.objects.all()
        context.update({
            "service_groups": [
                {"category": value, "label": label, "services": [service for service in services if service.category == value]}
                for value, label in FinanceModels.Service.CategoryChoices
            ],
            "lab_tests": LabModels.LabTest.objects.select_related("category").order_by("name"),
            "drugs": DepartmentModels.Drug.objects.select_related("category"),
        })
        return context

    def post_add_service(self, request, *args, **kwargs):
        form = FinanceForms.ServiceForm(request.POST, prefix="service")
        return self.save_form(form, "service_form", lambda service: f"{service.name} has been added at {service.fee}.")

    def update_price(self, request, queryset, field):
        form = FinanceForms.PriceForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Enter a valid price of zero or more.")
            return self.redirect_back()
        record = get_object_or_404(queryset, pk=form.cleaned_data["pk"])
        setattr(record, field, form.cleaned_data["price"])
        record.save()
        messages.success(request, f"The price of {record} is now {form.cleaned_data['price']}.")
        return self.redirect_back()

    def post_service_price(self, request, *args, **kwargs):
        return self.update_price(request, FinanceModels.Service.objects.all(), "fee")

    def post_lab_test_price(self, request, *args, **kwargs):
        return self.update_price(request, LabModels.LabTest.objects.all(), "price")

    def post_drug_price(self, request, *args, **kwargs):
        return self.update_price(request, DepartmentModels.Drug.objects.all(), "unit_price")

    def post_toggle_service(self, request, *args, **kwargs):
        service = get_object_or_404(FinanceModels.Service, pk=request.POST.get("pk"))
        service.is_active = not service.is_active
        service.save()
        messages.success(request, f"{service.name} is now {'offered' if service.is_active else 'no longer offered'}.")
        return self.redirect_back()
