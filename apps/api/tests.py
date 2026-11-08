from django.urls import reverse
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.manager.access import DOCTOR, PATIENTS
from apps.manager.testing import make_drug, make_patient, make_service, make_user, make_visit
from apps.patients import models as PatientModels
from apps.manager import models as ManagerModels
from apps.finance import models as FinanceModels
from apps.lab import models as LabModels


class APIAccessTest(TestCase):
    def test_api_is_versioned_and_lists_its_entry_points(self):
        self.assertTrue(reverse("api:root").startswith("/api/v1/"))
        client = APIClient()
        client.force_authenticate(make_user(modules=[PATIENTS]))
        response = client.get(reverse("api:root"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["version"], "v1")
        self.assertTrue(response.data["patients"].endswith(reverse("api:patient_list")))

    def test_anonymous_requests_are_refused(self):
        response = APIClient().get(reverse("api:patient_list"))
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_users_without_a_module_are_refused(self):
        client = APIClient()
        client.force_authenticate(make_user("nobody"))
        self.assertEqual(client.get(reverse("api:patient_list")).status_code, status.HTTP_403_FORBIDDEN)


class PatientAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(make_user(modules=[PATIENTS]))

    def test_patient_create_list_update(self):
        data = {"firstname": "mark", "middlename": "alex", "lastname": "peter", "nin": "NIOV234923F9VNEVWE",
                "gender": "Male", "telnumber": "+256786273721", "email": "markalex@test.com", "address": "Kampala", "age": 22}
        response = self.client.post(reverse("api:patient_create"), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        patient = PatientModels.Patient.objects.get()
        self.assertTrue(patient.patient_id.endswith(f"-P-{patient.pk:06d}"))
        self.assertEqual(patient.getFullName(), "mark alex peter")

        response = self.client.get(reverse("api:patient_list"), {"search": "alex"})
        self.assertEqual(response.data["results"][0]["patient_id"], patient.patient_id)

        url = reverse("api:patient_update", kwargs={"patient_id": patient.patient_id})
        response = self.client.patch(url, {"address": "Jinja"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        patient.refresh_from_db()
        self.assertEqual(patient.address, "Jinja")

    def test_empty_nin_does_not_clash(self):
        for name in ("one", "two"):
            response = self.client.post(reverse("api:patient_create"),
                                        {"firstname": name, "lastname": "x", "gender": "Female", "telnumber": "1", "nin": ""},
                                        format="json")
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class VisitAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(make_user(modules=[PATIENTS]))
        self.patient = make_patient()
        self.category = ManagerModels.VisitCategory.objects.create(name="Outpatient")

    def create_visit(self, **extra):
        data = {"patient": self.patient.pk, "category": self.category.pk, **extra}
        return self.client.post(reverse("api:visit_create"), data, format="json")

    def test_visit_with_insurance_billing(self):
        insurer = FinanceModels.InsuranceCompany.objects.create(name="Jubilee")
        billing_type = FinanceModels.BillingType.objects.get(kind="insurance")
        response = self.create_visit(billing_type=billing_type.pk, insurance_company=insurer.pk)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        visit = PatientModels.Visit.objects.get()
        self.assertEqual(visit.billing.insurance_company, insurer)
        self.assertEqual(response.data["insurance_company"], insurer.pk)

    def test_insurance_billing_needs_the_company(self):
        billing_type = FinanceModels.BillingType.objects.get(kind="insurance")
        response = self.create_visit(billing_type=billing_type.pk)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_one_active_visit_per_patient(self):
        self.assertEqual(self.create_visit().status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.create_visit().status_code, status.HTTP_409_CONFLICT)

    def test_complete_visit_leaves_active_list(self):
        self.create_visit()
        visit = PatientModels.Visit.objects.get()
        response = self.client.patch(reverse("api:visit_update", kwargs={"pk": visit.pk}), {"complete": True}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse("api:visit_list")).data["count"], 0)

    def test_one_triage_per_visit(self):
        self.create_visit()
        visit = PatientModels.Visit.objects.get()
        data = {"visit": visit.pk, "blood_pressure": "120/80", "temperature": "36.6"}
        self.assertEqual(self.client.post(reverse("api:triage_create"), data, format="json").status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.client.post(reverse("api:triage_create"), data, format="json").status_code, status.HTTP_409_CONFLICT)
        response = self.client.get(reverse("api:visit_triage_retrieve", kwargs={"pk": visit.pk}))
        self.assertEqual(response.data["blood_pressure"], "120/80")


class DoctorOrdersAPITest(TestCase):
    def setUp(self):
        self.user = make_user(modules=[DOCTOR])
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.visit = make_visit()

    def test_prescription_takes_the_drug_price(self):
        drug = make_drug(price="750", stock=20)
        response = self.client.post(reverse("api:prescription_create"),
                                    {"visit": self.visit.pk, "drug": drug.pk, "dosage": "1 x 3", "quantity": 4}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["amount"], "3000.00")
        self.assertEqual(response.data["stock_available"], 20)

    def test_service_order_and_department_request(self):
        dressing = make_service()
        response = self.client.post(reverse("api:visit_service_create"),
                                    {"visit": self.visit.pk, "service": dressing.pk, "quantity": 2}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["total"], "30000.00")

        xray = make_service("Chest X-ray", "radiology", "40000")
        url = reverse("api:department_request_create")
        wrong = self.client.post(url, {"visit": self.visit.pk, "service": dressing.pk, "department": "radiology"}, format="json")
        self.assertEqual(wrong.status_code, status.HTTP_400_BAD_REQUEST)
        right = self.client.post(url, {"visit": self.visit.pk, "service": xray.pk, "department": "radiology"}, format="json")
        self.assertEqual(right.status_code, status.HTTP_201_CREATED)
        self.assertEqual(right.data["status"], "pending")

    def test_invoiced_service_cannot_be_removed(self):
        order = FinanceModels.VisitService.objects.create(visit=self.visit, service=make_service())
        invoice = FinanceModels.Invoice.objects.create(patient=self.visit.patient, visit=self.visit)
        invoice.items.create(description="x", unit_price=1, source=f"visitservice:{order.pk}")
        response = self.client.delete(reverse("api:visit_service_delete", kwargs={"pk": order.pk}))
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_lab_request_create_and_edit(self):
        category = LabModels.TestCategory.objects.create(name="Haematology")
        cbc = LabModels.LabTest.objects.create(name="CBC", category=category, price=15000)
        malaria = LabModels.LabTest.objects.create(name="Malaria", category=category, price=8000)
        response = self.client.post(reverse("api:lab_requests_create"), {
            "visit_pk": self.visit.pk, "category": LabModels.LABORATORY_REQUEST_CATEGORY,
            "selectedTests": [{"test": cbc.pk, "price": "14000"}],
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        lab_request = LabModels.Request.objects.get()
        self.assertEqual(lab_request.category.name, LabModels.LABORATORY_REQUEST_CATEGORY)
        self.assertEqual(lab_request.assignedtest_set.get().price, 14000)

        url = reverse("api:lab_requests_update", kwargs={"pk": lab_request.pk})
        response = self.client.patch(url, {"selectedTests": [{"test": malaria.pk}]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(list(lab_request.assignedtest_set.values_list("test__name", flat=True)), ["Malaria"])

        lab_request.handled = True
        lab_request.save()
        response = self.client.patch(url, {"selectedTests": [{"test": cbc.pk}]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
