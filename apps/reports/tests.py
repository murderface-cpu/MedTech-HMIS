from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.finance import models as FinanceModels
from apps.manager.access import ADMINISTRATION, DOCTOR, FINANCE
from apps.manager.testing import make_service, make_user, make_visit
from apps.patients import models as PatientModels
from apps.reports.moh import classify


class OverviewTest(TestCase):
    def test_sections_follow_the_modules_held(self):
        self.client.force_login(make_user("doc", modules=[DOCTOR]))
        response = self.client.get(reverse("manager:home"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("clinical", response.context)
        self.assertNotIn("finance", response.context)

        self.client.force_login(make_user("cashier", modules=[FINANCE]))
        response = self.client.get(reverse("manager:home"))
        self.assertIn("finance", response.context)
        self.assertNotIn("clinical", response.context)

    def test_counts_todays_visits(self):
        make_visit()
        make_visit()
        self.client.force_login(make_user("admin", modules=[ADMINISTRATION]))
        response = self.client.get(reverse("manager:home"))
        self.assertContains(response, "Hospital overview", status_code=200)


class AnalyticsTest(TestCase):
    def setUp(self):
        visit = make_visit()
        PatientModels.Diagnosis.objects.create(visit=visit, diagnosis="Confirmed malaria, mRDT positive")
        invoice = FinanceModels.Invoice.objects.create(patient=visit.patient, visit=visit)
        service = make_service(fee="1000")
        invoice.items.create(description=service.name, unit_price=Decimal("1000"), source="visitservice:1")
        FinanceModels.Payment.objects.create(invoice=invoice, amount=Decimal("1000"), method="mpesa")

    def test_analytics_is_for_finance_and_administration(self):
        self.client.force_login(make_user("doc", modules=[DOCTOR]))
        self.assertEqual(self.client.get(reverse("reports:analytics")).status_code, 403)
        self.client.force_login(make_user("cashier", modules=[FINANCE]))
        for period in ("7", "30", "90"):
            self.assertEqual(self.client.get(reverse("reports:analytics"), {"period": period}).status_code, 200)

    def test_csv_export(self):
        self.client.force_login(make_user("cashier", modules=[FINANCE]))
        response = self.client.get(reverse("reports:analytics"), {"period": "7", "format": "csv"})
        self.assertEqual(response["Content-Type"].split(";")[0], "text/csv")
        self.assertIn(b"1000", response.content)

    def test_moh_returns(self):
        self.client.force_login(make_user("admin", modules=[ADMINISTRATION]))
        self.assertEqual(self.client.get(reverse("reports:moh")).status_code, 200)
        response = self.client.get(reverse("reports:moh"), {"format": "705b"})
        self.assertIn(b"Confirmed malaria", response.content)

    def test_diagnoses_map_to_moh_conditions(self):
        self.assertEqual(classify("Confirmed malaria, mRDT positive"), "Confirmed malaria")
        self.assertEqual(classify("Suspected malaria"), "Suspected malaria")
        self.assertEqual(classify("Upper respiratory tract infection"), "Upper respiratory tract infections")
        self.assertEqual(classify("Fracture of the left tibia"), "Other injuries")
        self.assertEqual(classify("Something rare"), "All other diseases")
