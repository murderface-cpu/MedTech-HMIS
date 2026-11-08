from datetime import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.manager.access import PATIENTS
from apps.manager.testing import make_patient, make_user, make_visit
from apps.patients import models as PatientModels


class PatientModelTest(TestCase):
    def test_codes_are_assigned_from_the_primary_key(self):
        visit = make_visit()
        self.assertTrue(visit.patient.patient_id.endswith(f"-P-{visit.patient.pk:06d}"))
        self.assertTrue(visit.visit_id.endswith(f"-V-{visit.pk:06d}"))

    def test_age_follows_date_of_birth(self):
        today = timezone.localdate()
        born = timezone.make_aware(datetime(today.year - 30, 1, 1))
        patient = make_patient(date_of_birth=born, age=None)
        self.assertEqual(patient.age, 30 if (today.month, today.day) >= (1, 1) else 29)

    def test_date_of_birth_estimated_from_age(self):
        patient = make_patient(age=40)
        self.assertEqual(patient.date_of_birth.year, timezone.localdate().year - 40)

    def test_next_of_kin(self):
        patient = make_patient()
        PatientModels.NextOfKin.objects.create(firstname="Flex", lastname="Mugalu", gender="Male", telnumber="1",
                                               relationship="Father", patient=patient)
        self.assertEqual(patient.next_of_kin.get().getFullName(), "Flex Mugalu")

    def test_active_visits_exclude_completed(self):
        visit = make_visit()
        visit.complete = True
        visit.save()
        self.assertFalse(PatientModels.Visit.active.exists())


class PatientPagesTest(TestCase):
    def test_pages_need_the_patients_module(self):
        self.client.force_login(make_user("clerk", modules=[PATIENTS]))
        for name in ("patients:patients-home", "patients:patients-visits", "patients:patients-triage"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)

        self.client.force_login(make_user("other"))
        self.assertEqual(self.client.get(reverse("patients:patients-home")).status_code, 403)

    def test_anonymous_users_are_sent_to_sign_in(self):
        response = self.client.get(reverse("patients:patients-home"))
        self.assertRedirects(response, f"{reverse('manager:login')}?next={reverse('patients:patients-home')}")
