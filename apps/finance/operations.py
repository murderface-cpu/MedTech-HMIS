"""Accounting pages beyond the cashier and invoices: M-Pesa, cashier shifts, claims, eTIMS and the ledger."""
from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone

from apps.finance import forms as FinanceForms
from apps.finance import models as FinanceModels
from apps.finance.views import FinanceModuleView


# ------------------------------------------------------------------ M-Pesa

class MpesaView(FinanceModuleView):
    template_name = "accounting/mpesa.html"
    title = "M-Pesa payments"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("transaction_form", FinanceForms.MpesaTransactionForm(prefix="mpesa", initial={"transacted_on": timezone.localtime()}))
        transactions = FinanceModels.MpesaTransaction.objects.select_related("payment__invoice__patient", "matched_by")
        unmatched = list(transactions.filter(status="unmatched").order_by("transacted_on"))
        for item in unmatched:
            item.suggestions = item.suggested_invoices()
        context.update({
            "unmatched": unmatched,
            "unmatched_total": sum((item.amount for item in unmatched), Decimal("0")),
            "matched": transactions.filter(status="matched")[:300],
            "rejected": transactions.filter(status="rejected")[:100],
            "pending_invoices": FinanceModels.Invoice.objects.filter(status="pending").select_related("patient").with_totals().order_by("-issued_on")[:300],
        })
        return context

    def post_record(self, request, *args, **kwargs):
        form = FinanceForms.MpesaTransactionForm(request.POST, prefix="mpesa")
        if not form.is_valid():
            return self.render_invalid(transaction_form=form)
        item = form.save(commit=False)
        item.recorded_by = request.user
        item.save()
        messages.success(request, f"{item.receipt_number} for {item.amount:,.2f} is recorded. Match it to the patient's invoice.")
        return self.redirect_back(tab="unmatched_payments")

    def post_match(self, request, *args, **kwargs):
        form = FinanceForms.MpesaMatchForm(request.POST)
        if not form.is_valid():
            self.form_errors(form)
            return self.redirect_back(tab="unmatched_payments")
        item, invoice = form.cleaned_data["transaction"], form.cleaned_data["invoice"]
        with transaction.atomic():
            payment = FinanceModels.Payment.objects.create(
                invoice=invoice, amount=item.amount, method="mpesa", received_by=request.user,
                received_on=item.transacted_on, narration=f"M-Pesa {item.receipt_number} from {item.phone}")
            item.payment = payment
            item.status = "matched"
            item.matched_by = request.user
            item.matched_on = timezone.now()
            item.save()
            invoice.refresh_status()
        messages.success(request, f"{item.receipt_number} is paid into {invoice.invoice_number} for {invoice.patient}.")
        return self.redirect_back(tab="unmatched_payments")

    def post_reject(self, request, *args, **kwargs):
        item = get_object_or_404(FinanceModels.MpesaTransaction, pk=request.POST.get("transaction"), status="unmatched")
        item.status = "rejected"
        item.matched_by = request.user
        item.matched_on = timezone.now()
        item.save()
        messages.success(request, f"{item.receipt_number} is set aside as not for this hospital.")
        return self.redirect_back(tab="unmatched_payments")


# ------------------------------------------------------------------ cashier shifts

class ShiftsView(FinanceModuleView):
    template_name = "accounting/shifts.html"
    title = "Cashier shifts"

    def open_shift(self):
        return FinanceModels.CashierShift.objects.filter(cashier=self.request.user, closed_on__isnull=True).first()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        shift = self.open_shift()
        context.setdefault("open_form", FinanceForms.OpenShiftForm(prefix="open"))
        context.setdefault("close_form", FinanceForms.CloseShiftForm(prefix="close"))
        shifts = FinanceModels.CashierShift.objects.select_related("cashier")
        context.update({
            "shift": shift,
            "takings": shift.takings() if shift else {},
            "methods": FinanceModels.Payment.MethodChoices,
            "open_shifts": shifts.filter(closed_on__isnull=True),
            "closed_shifts": shifts.filter(closed_on__isnull=False)[:200],
        })
        if shift:
            context["shift_payments"] = shift.window().select_related("invoice__patient").order_by("-received_on")
        return context

    def post_open(self, request, *args, **kwargs):
        if self.open_shift():
            messages.error(request, "You already have an open shift. Close it before opening another.")
            return self.redirect_back()
        form = FinanceForms.OpenShiftForm(request.POST, prefix="open")
        if not form.is_valid():
            return self.render_invalid(open_form=form)
        shift = form.save(commit=False)
        shift.cashier = request.user
        shift.save()
        messages.success(request, f"Your shift is open with a float of {shift.opening_float:,.2f}.")
        return self.redirect_back(tab="my_shift")

    def post_close(self, request, *args, **kwargs):
        shift = self.open_shift()
        if shift is None:
            messages.error(request, "You have no open shift.")
            return self.redirect_back()
        form = FinanceForms.CloseShiftForm(request.POST, prefix="close", instance=shift)
        if not form.is_valid():
            return self.render_invalid(close_form=form)
        shift = form.save(commit=False)
        shift.closed_on = timezone.now()
        shift.save()
        variance = shift.variance
        if variance == 0:
            messages.success(request, "Shift closed. The drawer balances.")
        else:
            word = "over" if variance > 0 else "short"
            messages.warning(request, f"Shift closed {abs(variance):,.2f} {word}. The variance is kept on the shift record.")
        return self.redirect_back(tab="shift_history")


# ------------------------------------------------------------------ insurance claims

def claimable_invoices():
    """Invoices with an insurer's share that are not yet claimed."""
    return (FinanceModels.Invoice.objects.filter(insurance_company__isnull=False, company_covered__gt=0, claim__isnull=True)
            .exclude(status="cancelled").select_related("patient", "insurance_company").order_by("issued_on"))


class ClaimsView(FinanceModuleView):
    template_name = "accounting/claims.html"
    title = "SHA claims"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        insurer = self.request.GET.get("insurer", "")
        claims = FinanceModels.InsuranceClaim.objects.select_related("invoice__patient", "insurer")
        ready = claimable_invoices()
        if insurer.isdigit():
            claims = claims.filter(insurer_id=insurer)
            ready = ready.filter(insurance_company_id=insurer)
        open_claims = claims.filter(status__in=("draft", "submitted"))
        decided = claims.exclude(status__in=("draft", "submitted"))
        context.update({
            "ready": ready,
            "open_claims": open_claims,
            "decided": decided[:300],
            "insurers": FinanceModels.InsuranceCompany.objects.all(),
            "insurer": insurer,
            "totals": {
                "ready": ready.aggregate(total=Sum("company_covered"))["total"] or Decimal("0"),
                "submitted": open_claims.filter(status="submitted").aggregate(total=Sum("amount_claimed"))["total"] or Decimal("0"),
                "approved": decided.filter(status__in=("approved", "partial", "paid")).aggregate(total=Sum("amount_approved"))["total"] or Decimal("0"),
                "rejected": decided.filter(status="rejected").aggregate(total=Sum("amount_claimed"))["total"] or Decimal("0"),
            },
        })
        return context

    def post_create(self, request, *args, **kwargs):
        invoice = get_object_or_404(claimable_invoices(), pk=request.POST.get("invoice"))
        member = request.POST.get("member_number", "").strip()
        if not member:
            messages.error(request, f"Enter the member number for {invoice.patient}.")
            return self.redirect_back()
        claim = FinanceModels.InsuranceClaim.objects.create(
            invoice=invoice, insurer=invoice.insurance_company, member_number=member[:64],
            preauthorisation=request.POST.get("preauthorisation", "").strip()[:64],
            amount_claimed=invoice.company_covered, created_by=request.user)
        messages.success(request, f"{claim.claim_number} drafted for {claim.amount_claimed:,.2f}. Review it, then submit.")
        return redirect("finance:claim", pk=claim.pk)


class ClaimDetailView(FinanceModuleView):
    template_name = "accounting/claim.html"
    title = "Claim"

    def get_claim(self):
        return get_object_or_404(FinanceModels.InsuranceClaim.objects.select_related("invoice__patient", "invoice__visit", "insurer"), pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        claim = self.get_claim()
        context = super().get_context_data(**kwargs)
        context.setdefault("claim_form", FinanceForms.ClaimForm(instance=claim))
        context.setdefault("decision_form", FinanceForms.ClaimDecisionForm(instance=claim, initial={"status": "approved" if claim.status == "submitted" else claim.status}))
        from apps.patients.models import Diagnosis

        context.update({
            "claim": claim,
            "items": claim.invoice.items.all(),
            "diagnoses": Diagnosis.objects.filter(visit=claim.invoice.visit) if claim.invoice.visit_id else [],
        })
        return context

    def post_update(self, request, *args, **kwargs):
        claim = self.get_claim()
        if claim.status != "draft":
            messages.error(request, "A submitted claim cannot be edited.")
            return self.redirect_back()
        form = FinanceForms.ClaimForm(request.POST, instance=claim)
        if not form.is_valid():
            return self.render_invalid(claim_form=form)
        form.save()
        messages.success(request, "The claim has been saved.")
        return self.redirect_back()

    def post_submit(self, request, *args, **kwargs):
        claim = self.get_claim()
        if claim.status != "draft":
            return self.redirect_back()
        claim.status = "submitted"
        claim.submitted_on = timezone.now()
        claim.save(update_fields=["status", "submitted_on"])
        messages.success(request, f"{claim.claim_number} is marked as submitted to {claim.insurer}. Record the decision when it comes back.")
        return self.redirect_back()

    def post_decide(self, request, *args, **kwargs):
        claim = self.get_claim()
        if claim.status == "draft":
            messages.error(request, "Submit the claim first.")
            return self.redirect_back()
        form = FinanceForms.ClaimDecisionForm(request.POST, instance=claim)
        if not form.is_valid():
            return self.render_invalid(decision_form=form)
        claim = form.save(commit=False)
        claim.decided_on = timezone.now()
        claim.save()
        messages.success(request, f"{claim.claim_number} is now {claim.get_status_display().lower()}.")
        return self.redirect_back()


# ------------------------------------------------------------------ eTIMS

class EtimsView(FinanceModuleView):
    template_name = "accounting/etims.html"
    title = "eTIMS submissions"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        to_submit = (FinanceModels.Invoice.objects.filter(status="paid", etims__isnull=True)
                     .select_related("patient").prefetch_related("items").order_by("issued_on"))
        submissions = FinanceModels.EtimsSubmission.objects.select_related("invoice__patient", "submitted_by")
        context.update({
            "to_submit": to_submit,
            "submitted": submissions.filter(status="submitted")[:300],
            "failed": submissions.filter(status="failed"),
        })
        return context

    def post_record(self, request, *args, **kwargs):
        invoice = get_object_or_404(FinanceModels.Invoice, pk=request.POST.get("invoice"))
        existing = FinanceModels.EtimsSubmission.objects.filter(invoice=invoice).first()
        if existing and existing.status == "submitted":
            messages.error(request, f"{invoice.invoice_number} is already accepted by KRA.")
            return self.redirect_back()
        form = FinanceForms.EtimsRecordForm(request.POST, instance=existing)
        if not form.is_valid():
            self.form_errors(form)
            return self.redirect_back()
        submission = form.save(commit=False)
        submission.submitted_by = request.user
        submission.created_on = timezone.now()
        submission.save()
        if submission.status == "submitted":
            messages.success(request, f"{invoice.invoice_number} is recorded as {submission.cu_invoice_number}.")
        else:
            messages.warning(request, f"{invoice.invoice_number} is listed under Failed until it is transmitted again.")
        return self.redirect_back()


# ------------------------------------------------------------------ chart of accounts and banks

class ChartOfAccountsView(FinanceModuleView):
    template_name = "accounting/chart_of_accounts.html"
    title = "Chart of accounts"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("account_form", FinanceForms.LedgerAccountForm(prefix="account"))
        accounts = list(FinanceModels.LedgerAccount.objects.select_related("parent"))
        groups = []
        for kind, label in FinanceModels.LedgerAccount.TypeChoices:
            groups.append({"kind": kind, "label": label, "accounts": [account for account in accounts if account.account_type == kind]})
        context["groups"] = groups
        context["account_count"] = len(accounts)
        return context

    def post_add_account(self, request, *args, **kwargs):
        form = FinanceForms.LedgerAccountForm(request.POST, prefix="account")
        return self.save_form(form, "account_form", lambda account: f"Account {account} has been added.")


class LedgerAccountDetailView(FinanceModuleView):
    template_name = "accounting/ledger_account.html"
    title = "Ledger account"

    def get_account(self):
        return get_object_or_404(FinanceModels.LedgerAccount, pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        account = self.get_account()
        context = super().get_context_data(**kwargs)
        context.setdefault("account_form", FinanceForms.LedgerAccountForm(instance=account))
        context["account"] = account
        return context

    def post_update(self, request, *args, **kwargs):
        form = FinanceForms.LedgerAccountForm(request.POST, instance=self.get_account())
        if not form.is_valid():
            return self.render_invalid(account_form=form)
        form.save()
        messages.success(request, "The account has been saved.")
        return redirect("finance:chart-of-accounts")


class BanksView(FinanceModuleView):
    template_name = "accounting/banks.html"
    title = "Bank accounts"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("bank_form", FinanceForms.BankAccountForm(prefix="bank"))
        accounts = list(FinanceModels.BankAccount.objects.select_related("ledger_account"))
        context.update({"accounts": accounts,
                        "total_balance": sum((account.balance for account in accounts if account.is_active), Decimal("0"))})
        return context

    def post_add_bank(self, request, *args, **kwargs):
        form = FinanceForms.BankAccountForm(request.POST, prefix="bank")
        if not form.is_valid():
            return self.render_invalid(bank_form=form)
        account = form.save()
        messages.success(request, f"{account} has been added.")
        return redirect("finance:bank", pk=account.pk)


class BankDetailView(FinanceModuleView):
    template_name = "accounting/bank.html"
    title = "Bank account"

    def get_account(self):
        return get_object_or_404(FinanceModels.BankAccount, pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        account = self.get_account()
        context = super().get_context_data(**kwargs)
        context.setdefault("bank_form", FinanceForms.BankAccountForm(instance=account, prefix="bank"))
        context.setdefault("transaction_form", FinanceForms.BankTransactionForm(prefix="txn"))
        rows, running = [], account.opening_balance
        for item in account.transactions.select_related("recorded_by").order_by("transacted_on", "id"):
            running += item.amount if item.kind == "deposit" else -item.amount
            rows.append({"item": item, "balance": running})
        rows.reverse()
        context.update({"account": account, "rows": rows})
        return context

    def post_record(self, request, *args, **kwargs):
        account = self.get_account()
        form = FinanceForms.BankTransactionForm(request.POST, prefix="txn")
        if not form.is_valid():
            return self.render_invalid(transaction_form=form)
        item = form.save(commit=False)
        item.account = account
        item.recorded_by = request.user
        if item.kind == "withdrawal" and item.amount > account.balance:
            messages.error(request, f"The recorded balance is {account.balance:,.2f}; a larger withdrawal would overdraw it.")
            return self.render_invalid(transaction_form=form)
        item.save()
        messages.success(request, f"{item.get_kind_display()} of {item.amount:,.2f} recorded.")
        return self.redirect_back(tab="bank_statement")

    def post_update(self, request, *args, **kwargs):
        form = FinanceForms.BankAccountForm(request.POST, instance=self.get_account(), prefix="bank")
        if not form.is_valid():
            return self.render_invalid(bank_form=form)
        form.save()
        messages.success(request, "The bank account has been saved.")
        return self.redirect_back(tab="bank_details")
