import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.manager.access import DENTAL, PHARMACY, RADIOLOGY, THEATRE
from apps.manager.testing import make_drug, make_service, make_user, make_visit
from apps.departments import models as DepartmentModels
from apps.finance import models as FinanceModels


class DrugStockTest(TestCase):
    def test_issue_uses_the_batch_that_expires_first(self):
        today = timezone.localdate()
        drug = make_drug(stock=10, expiry=today + datetime.timedelta(days=90))
        soon = DepartmentModels.StockBatch.objects.create(drug=drug, quantity_received=5, expiry_date=today + datetime.timedelta(days=10))
        DepartmentModels.StockBatch.objects.create(drug=drug, quantity_received=50, expiry_date=today - datetime.timedelta(days=1))
        self.assertEqual(drug.stock_available, 15)
        self.assertEqual(drug.stock_expired, 50)

        drug.issue(7)
        soon.refresh_from_db()
        self.assertEqual(soon.quantity_remaining, 0)
        self.assertEqual(drug.stock_available, 8)
        with self.assertRaises(DepartmentModels.InsufficientStock):
            drug.issue(9)


class PharmacyTest(TestCase):
    def setUp(self):
        self.client.force_login(make_user("pharmacist", modules=[PHARMACY]))
        self.prescription = DepartmentModels.Prescription.objects.create(
            visit=make_visit(), drug=make_drug(stock=5), dosage="1x3", quantity=4)

    def issue(self, quantity):
        return self.client.post(reverse("departments:departments-pharmacy"),
                                {"intent": "issue", "prescription": self.prescription.pk, "quantity": quantity})

    def test_issue_prescription(self):
        self.issue(4)
        self.prescription.refresh_from_db()
        self.assertEqual(self.prescription.quantity_issued, 4)
        self.assertEqual(self.prescription.drug.stock_available, 1)

    def test_cannot_issue_more_than_prescribed(self):
        self.issue(5)
        self.prescription.refresh_from_db()
        self.assertEqual(self.prescription.quantity_issued, 0)


class DepartmentReportTest(TestCase):
    def test_radiology_report(self):
        self.client.force_login(make_user("radiographer", modules=[RADIOLOGY]))
        request = DepartmentModels.DepartmentRequest.objects.create(
            department="radiology", visit=make_visit(), service=make_service("Chest X-ray", "radiology", "40000"))
        url = reverse("departments:departments-report", kwargs={"department": "radiology", "pk": request.pk})
        self.client.post(url, {"intent": "report", "result": "Clear lung fields"})
        request.refresh_from_db()
        self.assertEqual(request.status, "completed")
        self.assertIsNotNone(request.reported_on)
        # radiology staff cannot open cardiology reports
        self.assertEqual(self.client.get(reverse("departments:departments-cardiology")).status_code, 403)


class TheatreTest(TestCase):
    def test_book_ordered_theatre_service(self):
        self.client.force_login(make_user("theatre", modules=[THEATRE]))
        visit = make_visit()
        service = make_service("Appendectomy", "theatre", "900000")
        FinanceModels.VisitService.objects.create(visit=visit, service=service)
        self.assertEqual(len(self.client.get(reverse("departments:departments-theatre")).context["orders"]), 1)

        self.client.post(reverse("departments:departments-theatre"), {
            "intent": "book", "visit": visit.pk, "service": service.pk, "surgery_type": "Appendectomy",
            "scheduled_for": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
        })
        self.assertEqual(DepartmentModels.TheatreBooking.objects.count(), 1)
        self.assertEqual(len(self.client.get(reverse("departments:departments-theatre")).context["orders"]), 0)


class DentalTest(TestCase):
    def test_record_procedure_with_standard_fee(self):
        self.client.force_login(make_user("dentist", modules=[DENTAL]))
        visit = make_visit()
        extraction = make_service("Extraction", "dental", "30000")
        self.client.post(reverse("departments:departments-dental"), {
            "intent": "record", "visit": visit.pk, "tooth": "Molar", "diagnosis": "Caries", "procedure": extraction.pk,
            "performed_on": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
        })
        self.assertEqual(DepartmentModels.DentalProcedure.objects.get().fee, 30000)
