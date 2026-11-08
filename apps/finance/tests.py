from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.manager.access import FINANCE
from apps.manager.testing import make_drug, make_service, make_user, make_visit
from apps.finance import models as FinanceModels
from apps.finance.billing import unbilled_items
from apps.departments import models as DepartmentModels
from apps.lab import models as LabModels


class BillingTest(TestCase):
    def setUp(self):
        self.visit = make_visit()
        FinanceModels.VisitService.objects.create(visit=self.visit, service=make_service(), quantity=2)
        DepartmentModels.Prescription.objects.create(visit=self.visit, drug=make_drug(price="500"), dosage="1x3", quantity=6)
        category = LabModels.TestCategory.objects.create(name="Haematology")
        lab_request = LabModels.Request.objects.create(visit=self.visit)
        LabModels.AssignedTest.objects.create(request=lab_request, test=LabModels.LabTest.objects.create(name="CBC", category=category, price=12000))

    def test_every_order_is_billable_once(self):
        items = unbilled_items(self.visit)
        self.assertEqual(sum(item["total"] for item in items), Decimal("30000") + Decimal("3000") + Decimal("12000"))

        invoice = FinanceModels.Invoice.objects.create(patient=self.visit.patient, visit=self.visit)
        first = items[0]
        invoice.items.create(description=first["description"], quantity=first["quantity"], unit_price=first["unit_price"], source=first["source"])
        self.assertEqual(len(unbilled_items(self.visit)), 2)

        # cancelling the invoice releases its orders
        invoice.status = "cancelled"
        invoice.save()
        self.assertEqual(len(unbilled_items(self.visit)), 3)


class InvoiceFlowTest(TestCase):
    def setUp(self):
        self.client.force_login(make_user("cashier", modules=[FINANCE]))

    def create_invoice(self, visit):
        sources = [item["source"] for item in unbilled_items(visit)]
        response = self.client.post(reverse("finance:finance-invoices"), {"intent": "create_invoice", "visit": visit.pk, "items": sources})
        invoice = FinanceModels.Invoice.objects.get()
        self.assertRedirects(response, reverse("finance:finance-invoice", kwargs={"pk": invoice.pk}))
        return invoice

    def test_cash_invoice_payment_and_refund(self):
        visit = make_visit(billing_kind="cash")
        FinanceModels.VisitService.objects.create(visit=visit, service=make_service(fee="20000"))
        invoice = self.create_invoice(visit)
        self.assertEqual(invoice.total, Decimal("20000"))
        self.assertEqual(invoice.status, "pending")

        url = reverse("finance:finance-invoice", kwargs={"pk": invoice.pk})
        # paying more than the balance is refused
        self.client.post(url, {"intent": "payment", "payment-invoice": invoice.pk, "payment-amount": "25000"})
        self.assertFalse(invoice.payments.exists())

        self.client.post(url, {"intent": "payment", "payment-invoice": invoice.pk, "payment-amount": "20000"})
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "paid")

        # paid invoices cannot be cancelled until refunded
        self.client.post(url, {"intent": "cancel"})
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "paid")

        self.client.post(url, {"intent": "refund", "refund-invoice": invoice.pk, "refund-amount": "20000", "refund-narration": "Wrong patient"})
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "pending")
        self.client.post(url, {"intent": "cancel"})
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "cancelled")

    def test_insurance_invoice_is_covered_by_the_company(self):
        visit = make_visit(billing_kind="insurance")
        FinanceModels.VisitService.objects.create(visit=visit, service=make_service(fee="50000"))
        invoice = self.create_invoice(visit)
        self.assertEqual(invoice.company_covered, Decimal("50000"))
        self.assertEqual(invoice.balance, Decimal("0"))
        self.assertEqual(invoice.insurance_company, visit.billing.insurance_company)

    def test_pages_render(self):
        for name in ("finance:finance-cashier", "finance:finance-invoices", "finance:finance-finances",
                     "finance:finance-insurance", "finance:finance-pricing"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_price_change(self):
        service = make_service(fee="1000")
        self.client.post(reverse("finance:finance-pricing"), {"intent": "service_price", "pk": service.pk, "price": "1500"})
        service.refresh_from_db()
        self.assertEqual(service.fee, Decimal("1500"))


class MpesaMatchTest(TestCase):
    def setUp(self):
        self.client.force_login(make_user("cashier", modules=[FINANCE]))
        visit = make_visit()
        self.invoice = FinanceModels.Invoice.objects.create(patient=visit.patient, visit=visit)
        self.invoice.items.create(description="Consultation", unit_price=Decimal("1500"))
        self.transaction = FinanceModels.MpesaTransaction.objects.create(
            receipt_number="TK4H7Q2LMX", phone="+254712345678", amount=Decimal("1500"), account_reference=visit.patient.patient_id)

    def test_suggests_the_patient_invoice(self):
        self.assertIn(self.invoice, list(self.transaction.suggested_invoices()))

    def test_matching_pays_the_invoice(self):
        response = self.client.post(reverse("finance:mpesa"), {"intent": "match", "transaction": self.transaction.pk, "invoice": self.invoice.pk})
        self.assertEqual(response.status_code, 302)
        self.invoice.refresh_from_db()
        self.transaction.refresh_from_db()
        self.assertEqual(self.invoice.status, "paid")
        self.assertEqual(self.transaction.status, "matched")
        self.assertEqual(self.transaction.payment.method, "mpesa")

    def test_cannot_match_more_than_the_balance(self):
        self.transaction.amount = Decimal("5000")
        self.transaction.save()
        self.client.post(reverse("finance:mpesa"), {"intent": "match", "transaction": self.transaction.pk, "invoice": self.invoice.pk})
        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, "unmatched")


class InvoiceTotalsTest(TestCase):
    def test_annotated_totals_match_the_properties(self):
        visit = make_visit()
        invoice = FinanceModels.Invoice.objects.create(patient=visit.patient, visit=visit)
        invoice.items.create(description="Consultation", unit_price=Decimal("1000"), quantity=2)
        FinanceModels.Payment.objects.create(invoice=invoice, amount=Decimal("1500"))
        FinanceModels.Refund.objects.create(invoice=invoice, amount=Decimal("200"))
        annotated = FinanceModels.Invoice.objects.with_totals().get(pk=invoice.pk)
        self.assertEqual((annotated.total, annotated.amount_paid, annotated.balance), (Decimal("2000"), Decimal("1500"), Decimal("700")))

        # a payment made after loading is counted when the status is refreshed
        FinanceModels.Payment.objects.create(invoice=annotated, amount=Decimal("700"))
        annotated.refresh_status()
        self.assertEqual(annotated.status, "paid")


class OperationsPagesTest(TestCase):
    def test_finance_pages_open_for_finance_only(self):
        names = ("mpesa", "shifts", "claims", "etims", "chart-of-accounts", "banks")
        self.client.force_login(make_user("doc", modules=["Doctor"]))
        for name in names:
            self.assertEqual(self.client.get(reverse(f"finance:{name}")).status_code, 403, name)
        self.client.force_login(make_user("cashier", modules=[FINANCE]))
        for name in names:
            self.assertEqual(self.client.get(reverse(f"finance:{name}")).status_code, 200, name)
