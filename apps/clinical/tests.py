import datetime
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.clinical import models as ClinicalModels
from apps.finance.billing import billable_items
from apps.manager.access import DOCTOR, FINANCE, LABORATORY, PATIENTS
from apps.manager.testing import make_patient, make_user, make_visit


class ClinicalAccessTest(TestCase):
    def test_clinical_pages_need_a_clinical_module(self):
        self.client.force_login(make_user("lab", modules=[LABORATORY]))
        for name in ("appointments", "queue", "emergency-queue", "admissions", "wards"):
            self.assertEqual(self.client.get(reverse(f"clinical:{name}")).status_code, 403, name)

    def test_front_desk_opens_clinical_pages(self):
        self.client.force_login(make_user("desk", modules=[PATIENTS]))
        for name in ("appointments", "queue", "emergency-check-in", "emergency-queue", "admissions", "awaiting-admission",
                     "discharges", "wards", "bed-charges"):
            self.assertEqual(self.client.get(reverse(f"clinical:{name}")).status_code, 200, name)

    def test_cashier_reaches_bed_charges_only(self):
        self.client.force_login(make_user("cashier", modules=[FINANCE]))
        self.assertEqual(self.client.get(reverse("clinical:bed-charges")).status_code, 200)
        self.assertEqual(self.client.get(reverse("clinical:wards")).status_code, 403)


class EmergencyTest(TestCase):
    def setUp(self):
        self.client.force_login(make_user("nurse", modules=[PATIENTS]))

    def test_unidentified_patient_is_registered_and_queued(self):
        response = self.client.post(reverse("clinical:emergency-check-in"), {
            "intent": "check_in", "case-firstname": "Unknown", "case-lastname": "Male", "case-gender": "Male", "case-age": 30,
            "case-acuity": "red", "case-arrival_mode": "ambulance", "case-chief_complaint": "Unconscious after a fall"})
        self.assertRedirects(response, reverse("clinical:emergency-queue"))
        case = ClinicalModels.EmergencyCase.objects.get()
        self.assertEqual(case.acuity_rank, 1)
        self.assertIn("-ER-", case.case_number)
        self.assertEqual(case.visit.category.name, "Emergency")

    def test_red_case_is_overdue_at_once(self):
        case = ClinicalModels.EmergencyCase.objects.create(
            patient=make_patient(), acuity="red", chief_complaint="Not breathing",
            arrived_on=timezone.now() - datetime.timedelta(minutes=3))
        self.assertTrue(case.overdue)


class InpatientFlowTest(TestCase):
    def setUp(self):
        self.client.force_login(make_user("doc", modules=[DOCTOR]))
        self.ward = ClinicalModels.Ward.objects.create(name="Male medical", daily_rate=Decimal("2500"))
        self.bed = ClinicalModels.Bed.objects.create(ward=self.ward, number="MM-01")
        self.visit = make_visit()
        self.admission = ClinicalModels.Admission.objects.create(
            patient=self.visit.patient, visit=self.visit, requested_ward=self.ward, reason="Severe malaria")

    def test_assign_charge_and_discharge(self):
        response = self.client.post(reverse("clinical:awaiting-admission"),
                                    {"intent": "assign", "admission": self.admission.pk, "bed": self.bed.pk})
        self.assertRedirects(response, reverse("clinical:admission", kwargs={"pk": self.admission.pk}))
        self.bed.refresh_from_db()
        self.assertEqual(self.bed.status, "occupied")

        # admitted two days ago: three bed days including today
        ClinicalModels.Admission.objects.filter(pk=self.admission.pk).update(
            admitted_on=timezone.now() - datetime.timedelta(days=2))
        self.client.post(reverse("clinical:bed-charges"), {"intent": "post_charges"})
        self.assertEqual(ClinicalModels.BedCharge.objects.filter(admission=self.admission).count(), 3)
        bed_lines = [item for item in billable_items(self.visit) if item["kind"] == "Inpatient"]
        self.assertEqual(sum(item["total"] for item in bed_lines), Decimal("7500"))

        # posting again adds nothing
        self.client.post(reverse("clinical:bed-charges"), {"intent": "post_charges"})
        self.assertEqual(ClinicalModels.BedCharge.objects.count(), 3)

        response = self.client.post(reverse("clinical:admission", kwargs={"pk": self.admission.pk}), {
            "intent": "discharge", "discharge_type": "home", "discharge_summary": "Improved, home on oral treatment."})
        self.assertRedirects(response, reverse("clinical:discharges"))
        self.admission.refresh_from_db()
        self.bed.refresh_from_db()
        self.assertEqual(self.admission.status, "discharged")
        self.assertEqual(self.bed.status, "cleaning")

    def test_an_occupied_bed_cannot_be_given_twice(self):
        self.bed.status = "occupied"
        self.bed.save()
        self.client.post(reverse("clinical:awaiting-admission"),
                         {"intent": "assign", "admission": self.admission.pk, "bed": self.bed.pk})
        self.admission.refresh_from_db()
        self.assertEqual(self.admission.status, "awaiting")
