from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.manager.access import LABORATORY
from apps.manager.testing import make_user, make_visit
from apps.lab import models as LabModels


class LabResultsTest(TestCase):
    def setUp(self):
        self.client.force_login(make_user("lab", modules=[LABORATORY]))
        category = LabModels.TestCategory.objects.create(name="Haematology")
        self.test = LabModels.LabTest.objects.create(name="CBC", category=category, price=15000)
        self.haemoglobin = LabModels.SubTest.objects.create(test=self.test, name="Haemoglobin", lower_limit=12, upper_limit=16, units="g/dL")
        self.lab_request = LabModels.Request.objects.create(visit=make_visit())
        self.assigned = LabModels.AssignedTest.objects.create(request=self.lab_request, test=self.test)
        self.url = reverse("lab:lab-request", kwargs={"pk": self.lab_request.pk})

    def test_save_results_and_mark_handled(self):
        response = self.client.post(self.url, {
            "intent": "save_results", f"result_{self.assigned.pk}": "Normal picture",
            f"parameter_{self.assigned.pk}_{self.haemoglobin.pk}": "13.5", "handled": "1",
        })
        self.assertRedirects(response, reverse("lab:lab-home"))
        self.lab_request.refresh_from_db()
        self.assertTrue(self.lab_request.handled)
        self.assertEqual(self.assigned.parameter_results.get().results, Decimal("13.5"))
        self.assertEqual(self.assigned.testresult_set.get().results, "Normal picture")

    def test_invalid_number_saves_nothing(self):
        self.client.post(self.url, {
            "intent": "save_results", f"result_{self.assigned.pk}": "x",
            f"parameter_{self.assigned.pk}_{self.haemoglobin.pk}": "abc",
        })
        self.assertFalse(LabModels.TestResult.objects.exists())
        self.lab_request.refresh_from_db()
        self.assertFalse(self.lab_request.handled)

    def test_doctor_sees_results_through_the_api(self):
        LabModels.SubTestResult.objects.create(assigned_test=self.assigned, subtest=self.haemoglobin, results=Decimal("11"))
        doctor = make_user("doctor", modules=["Doctor"])
        self.client.force_login(doctor)
        response = self.client.get(reverse("api:request_lab_tests_list", kwargs={"pk": self.lab_request.pk}))
        self.assertEqual(response.json()[0]["parameters"][0]["name"], "Haemoglobin")

    def test_parameters_mark_the_test(self):
        url = reverse("lab:lab-test", kwargs={"pk": self.test.pk})
        self.client.post(url, {"intent": "remove_parameter", "parameter": self.haemoglobin.pk})
        self.test.refresh_from_db()
        self.assertFalse(self.test.has_subtest)
        self.client.post(url, {"intent": "add_parameter", "parameter-name": "WBC", "parameter-units": "10^9/L"})
        self.test.refresh_from_db()
        self.assertTrue(self.test.has_subtest)
