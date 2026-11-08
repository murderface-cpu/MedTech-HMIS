from django.test import TestCase
from django.urls import reverse

from apps.manager import models as ManagerModels
from apps.manager.access import ADMINISTRATION, DOCTOR, INVENTORY, PATIENTS
from apps.manager.testing import PASSWORD, make_drug, make_user
from apps.doctor import models as DoctorModels
from apps.departments import models as DepartmentModels


class SignInTest(TestCase):
    def test_sign_in_opens_the_first_module(self):
        make_user("nurse", modules=[PATIENTS])
        response = self.client.post(reverse("manager:login"), {"username": "nurse", "password": PASSWORD}, follow=True)
        self.assertRedirects(response, reverse("manager:home"))
        self.assertTemplateUsed(response, "reports/overview.html")

    def test_wrong_password_is_refused(self):
        make_user("nurse", modules=[PATIENTS])
        response = self.client.post(reverse("manager:login"), {"username": "nurse", "password": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_user_without_modules_sees_no_access_page(self):
        self.client.force_login(make_user("new"))
        self.assertEqual(self.client.get(reverse("manager:home")).status_code, 403)

    def test_sign_out(self):
        self.client.force_login(make_user("nurse", modules=[PATIENTS]))
        self.client.post(reverse("manager:logout"))
        self.assertEqual(self.client.get(reverse("patients:patients-home")).status_code, 302)

    def test_menu_lists_only_allowed_modules(self):
        self.client.force_login(make_user("doc", modules=[DOCTOR]))
        response = self.client.get(reverse("doctor:doctor-home"))
        menu = response.context["menu"]
        self.assertEqual([workspace["label"] for workspace in menu], ["Home", "Outpatient", "Emergency", "Inpatient"])
        live_pages = [page["label"] for workspace in menu for section in workspace["sections"]
                      for page in section["pages"] if not page["planned"]]
        self.assertIn("Consultation", live_pages)
        self.assertIn("Hospital overview", live_pages)
        self.assertNotIn("Staff", live_pages)
        self.assertEqual(response.context["current_page"]["label"], "Consultation")

    def test_detail_pages_mark_their_parent_page_current(self):
        self.client.force_login(make_user("admin", modules=[ADMINISTRATION]))
        title = ManagerModels.StaffTitle.objects.get_or_create(name="Nurse")[0]
        staff = ManagerModels.Staff.objects.create(firstname="Ann", lastname="Otieno", title=title)
        response = self.client.get(reverse("manager:manager-staff", kwargs={"pk": staff.pk}))
        self.assertEqual(response.context["current_page"]["label"], "Staff")
        self.assertFalse(response.context["current_page"]["exact"])

    def test_menu_tab_marks_the_matching_page(self):
        self.client.force_login(make_user("store", modules=[INVENTORY]))
        response = self.client.get(reverse("manager:manager-inventory"), {"tab": "suppliers"})
        self.assertEqual(response.context["current_page"]["label"], "Suppliers")


class NavigationDefinitionTest(TestCase):
    """Every live menu entry opens a real tab, and no planned route is already taken."""

    def test_live_pages_open_existing_tabs(self):
        from django.urls import Resolver404, resolve
        from apps.manager.navigation import WORKSPACES, page_url

        self.client.force_login(make_user("root", is_superuser=True, is_staff=True))
        pages = [page for workspace in WORKSPACES for section in workspace.sections for page in section.pages]
        for page in pages:
            if page.planned:
                with self.assertRaises(Resolver404, msg=page.planned_route):
                    resolve(page.planned_route)
                continue
            response = self.client.get(page_url(page))
            self.assertEqual(response.status_code, 200, page.label)
            if page.tab:
                self.assertContains(response, f'data-section="{page.tab}"', msg_prefix=page.label)


class StaffAdminTest(TestCase):
    def setUp(self):
        self.client.force_login(make_user("admin", modules=[ADMINISTRATION]))
        self.speciality = DoctorModels.DoctorSpeciality.objects.create(name="General")
        self.doctor_title = ManagerModels.StaffTitle.objects.get_or_create(name="Medical Officer", defaults={"kind": "doctor"})[0]

    def staff_data(self, **extra):
        data = {"intent": "register_staff", "firstname": "Jane", "lastname": "Akello", "gender": "Female",
                "telnumber": "0700000000", "title": self.doctor_title.pk, "speciality": self.speciality.pk, "is_active": "on",
                "account-username": "jakello", "account-password": "Str0ng-Passw0rd!", "account-modules": [DOCTOR],
                "account-can_sign_in": "on"}
        data.update(extra)
        return data

    def test_register_doctor_with_account(self):
        response = self.client.post(reverse("manager:manager-admin"), self.staff_data())
        staff = ManagerModels.Staff.objects.get()
        self.assertRedirects(response, reverse("manager:manager-staff", kwargs={"pk": staff.pk}))
        self.assertEqual(staff.user.username, "jakello")
        self.assertTrue(staff.user.check_password("Str0ng-Passw0rd!"))
        self.assertEqual(list(staff.user.groups.values_list("name", flat=True)), [DOCTOR])
        # a doctor record is kept so the doctor can be assigned to visits
        self.assertEqual(staff.doctor.getFullName(), "Jane Akello")
        self.assertEqual(list(staff.doctor.speciality.all()), [self.speciality])

    def test_doctor_needs_a_speciality(self):
        self.client.post(reverse("manager:manager-admin"), self.staff_data(speciality=""))
        self.assertFalse(ManagerModels.Staff.objects.exists())

    def test_new_account_needs_a_password(self):
        self.client.post(reverse("manager:manager-admin"), self.staff_data(**{"account-password": ""}))
        self.assertFalse(ManagerModels.Staff.objects.exists())

    def test_deactivating_staff_disables_sign_in(self):
        self.client.post(reverse("manager:manager-admin"), self.staff_data())
        staff = ManagerModels.Staff.objects.get()
        data = self.staff_data(intent="update_staff", **{"account-password": ""})
        data.pop("is_active")
        self.client.post(reverse("manager:manager-staff", kwargs={"pk": staff.pk}), data)
        staff.refresh_from_db()
        self.assertFalse(staff.is_active)
        self.assertFalse(staff.user.is_active)

    def test_admin_page_needs_the_module(self):
        self.client.force_login(make_user("clerk", modules=[PATIENTS]))
        self.assertEqual(self.client.get(reverse("manager:manager-admin")).status_code, 403)


class InventoryTest(TestCase):
    def setUp(self):
        self.client.force_login(make_user("store", modules=[INVENTORY]))
        self.category = DepartmentModels.DrugCategory.objects.get_or_create(name="Tablet")[0]

    def test_add_drug_with_opening_stock(self):
        self.client.post(reverse("manager:manager-inventory"), {
            "intent": "add_drug", "drug-name": "Amoxicillin", "drug-category": self.category.pk, "drug-unit_price": "300",
            "drug-is_active": "on", "drug-opening_stock": "100",
        })
        drug = DepartmentModels.Drug.objects.get()
        self.assertEqual(drug.stock_available, 100)
        self.assertTrue(drug.drug_number.endswith(f"-DRG-{drug.pk:06d}"))

    def test_receive_stock(self):
        drug = make_drug()
        response = self.client.post(reverse("manager:manager-inventory"), {
            "intent": "receive_stock", "stock-drug": drug.pk, "stock-quantity_received": "50", "tab": "receive_stock"})
        self.assertRedirects(response, f"{reverse('manager:manager-inventory')}?tab=receive_stock")
        self.assertEqual(drug.stock_available, 50)

    def test_invalid_form_is_shown_again(self):
        response = self.client.post(reverse("manager:manager-inventory"), {"intent": "receive_stock", "stock-quantity_received": "0"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["stock_form"].errors)


class MovedRoutesTest(TestCase):
    def test_old_paths_redirect_permanently_with_their_query(self):
        for old, new in [
            ("/patients/", reverse("patients:patients-home")),
            ("/doctor/", reverse("doctor:doctor-home")),
            ("/pricing/?tab=drug_prices", reverse("finance:finance-pricing") + "?tab=drug_prices"),
            ("/departments/radiology/requests/7/", reverse("departments:departments-report", kwargs={"department": "radiology", "pk": 7})),
            ("/app-admin/", reverse("manager:manager-admin")),
        ]:
            response = self.client.get(old)
            self.assertEqual(response.status_code, 301, old)
            self.assertEqual(response["Location"], new)
