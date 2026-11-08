"""Fill the database with a believable Kenyan outpatient and inpatient hospital, for demos and testing.

    python manage.py seed_demo            # adds the demo data once
    python manage.py seed_demo --reset    # removes the patient, money and stock records first, then seeds again

Staff accounts are created for every module, all with the password printed at the end.
The data is generated from a fixed random seed, so two runs on the same day give the same hospital.
"""
import datetime
import random
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.clinical import models as ClinicalModels
from apps.clinical.views import post_bed_charges
from apps.departments import models as DepartmentModels
from apps.doctor import models as DoctorModels
from apps.finance import models as FinanceModels
from apps.finance.billing import billable_items
from apps.lab import models as LabModels
from apps.manager import access, audit
from apps.manager import models as ManagerModels
from apps.patients import models as PatientModels
from apps.stores import models as StoreModels

PASSWORD = "Demo-Pass-2026"
MARKER = "demo.admin"
DAYS = 90

FIRST_FEMALE = ["Wanjiku", "Akinyi", "Njeri", "Atieno", "Wambui", "Chebet", "Nyambura", "Achieng", "Mumbua", "Jepkosgei",
                "Nafula", "Kerubo", "Wairimu", "Auma", "Faith", "Mercy", "Grace", "Esther", "Joyce", "Lucy", "Ann",
                "Mary", "Purity", "Beatrice", "Zawadi", "Halima", "Amina", "Neema"]
FIRST_MALE = ["Kamau", "Otieno", "Kiprono", "Mwangi", "Ochieng", "Kipchoge", "Mutua", "Wafula", "Onyango", "Njoroge",
              "Kibet", "Omondi", "Barasa", "Juma", "Brian", "Kevin", "Dennis", "Peter", "John", "James", "David",
              "Samuel", "Joseph", "Daniel", "Hassan", "Ali", "Collins", "Victor"]
MIDDLE = ["Wanjiru", "Muthoni", "Adhiambo", "Jeptoo", "Mwikali", "Kariuki", "Odhiambo", "Kiplagat", "Musyoka", "Simiyu",
          "Achieng", "Nduta", "Chepkoech", "Moraa"]
LAST = ["Kamau", "Otieno", "Mwangi", "Ochieng", "Kiprotich", "Njoroge", "Mutua", "Wafula", "Onyango", "Kariuki",
        "Odhiambo", "Kipkemboi", "Wekesa", "Maina", "Gitau", "Nyaga", "Owino", "Cheruiyot", "Musyoka", "Kilonzo",
        "Barasa", "Omondi", "Rotich", "Kimani", "Macharia", "Ndungu", "Oduor", "Langat", "Wanyama", "Abdi"]
TOWNS = ["Nairobi, Kibera", "Nairobi, Kasarani", "Nairobi, Embakasi", "Kiambu, Ruiru", "Kiambu, Thika", "Machakos, Athi River",
         "Kajiado, Kitengela", "Nairobi, Kawangware", "Nairobi, Umoja", "Kiambu, Kikuyu", "Nairobi, South B", "Nairobi, Githurai"]

# (diagnosis wording, weight, age band) where the band limits who it is given to: "child" under 5, "adult" 15+, None anyone
DIAGNOSES = [
    ("Upper respiratory tract infection", 16, None),
    ("Suspected malaria", 7, None),
    ("Confirmed malaria, mRDT positive", 6, None),
    ("Acute gastroenteritis with diarrhoea", 7, None),
    ("Urinary tract infection", 7, "adult"),
    ("Hypertension, on follow up", 8, "adult"),
    ("Type 2 diabetes mellitus", 5, "adult"),
    ("Pneumonia", 4, None),
    ("Tonsillitis", 4, None),
    ("Intestinal worms", 3, None),
    ("Typhoid fever", 3, "adult"),
    ("Allergic dermatitis", 3, None),
    ("Peptic ulcer disease", 4, "adult"),
    ("Low back pain", 4, "adult"),
    ("Asthma, acute exacerbation", 2, None),
    ("Iron deficiency anaemia", 2, None),
    ("Otitis media", 2, "child"),
    ("Conjunctivitis", 2, None),
    ("Dental caries", 2, None),
    ("Soft tissue injury, left ankle sprain", 2, None),
    ("Road traffic injury, motorcycle accident", 1, "adult"),
    ("Anxiety disorder", 1, "adult"),
    ("Moderate acute malnutrition", 1, "child"),
    ("Antenatal care, normal pregnancy", 3, "adult"),
]
COMPLAINTS = {
    "respiratory": "Cough and running nose for 3 days, mild fever.",
    "malaria": "Fever, chills and headache for 2 days, joint pains.",
    "gastro": "Loose stools 5 times a day since yesterday, abdominal cramps.",
    "default": "Generalised body weakness, review requested.",
}
LAB_TESTS = [
    ("Haematology", "Full blood count", 800, "WBC 4.0-11.0, Hb 12-16 g/dl, Plt 150-400"),
    ("Parasitology", "Malaria rapid diagnostic test (mRDT)", 300, "Negative"),
    ("Parasitology", "Blood slide for malaria parasites", 300, "No parasites seen"),
    ("Parasitology", "Stool for ova and cysts", 400, "No ova or cysts seen"),
    ("Microbiology", "Urinalysis", 400, "Nitrites negative, leucocytes negative"),
    ("Microbiology", "Widal test", 500, "Titres below 1:80"),
    ("Microbiology", "H. pylori stool antigen", 1200, "Negative"),
    ("Chemistry", "Random blood sugar", 200, "3.9-7.8 mmol/l"),
    ("Chemistry", "HbA1c", 2500, "Below 6.5%"),
    ("Chemistry", "Urea, electrolytes and creatinine", 1800, "Creatinine 60-110 umol/l"),
    ("Chemistry", "Liver function tests", 2000, "ALT below 40 U/l"),
    ("Serology", "Pregnancy test (urine hCG)", 300, "Negative"),
    ("Serology", "HIV rapid test", 0, "Non reactive"),
]
TESTS_FOR = {
    "malaria": ["Malaria rapid diagnostic test (mRDT)", "Full blood count"],
    "Typhoid": ["Widal test", "Full blood count"],
    "Urinary": ["Urinalysis"],
    "diabetes": ["Random blood sugar", "HbA1c"],
    "Hypertension": ["Urea, electrolytes and creatinine"],
    "gastro": ["Stool for ova and cysts"],
    "Peptic": ["H. pylori stool antigen"],
    "anaemia": ["Full blood count"],
    "Antenatal": ["Pregnancy test (urine hCG)", "HIV rapid test", "Full blood count"],
    "Pneumonia": ["Full blood count"],
}
DRUGS = [
    ("Paracetamol 500 mg tablets", "Tablet", 5, "1 g three times a day"),
    ("Amoxicillin 500 mg capsules", "Tablet", 10, "500 mg three times a day"),
    ("Artemether/lumefantrine 20/120 mg tablets", "Tablet", 25, "4 tablets twice a day"),
    ("Metformin 500 mg tablets", "Tablet", 8, "500 mg twice a day"),
    ("Amlodipine 5 mg tablets", "Tablet", 10, "5 mg once a day"),
    ("Losartan 50 mg tablets", "Tablet", 15, "50 mg once a day"),
    ("Ibuprofen 400 mg tablets", "Tablet", 5, "400 mg three times a day"),
    ("Ciprofloxacin 500 mg tablets", "Tablet", 15, "500 mg twice a day"),
    ("Omeprazole 20 mg capsules", "Tablet", 10, "20 mg twice a day"),
    ("Metronidazole 400 mg tablets", "Tablet", 5, "400 mg three times a day"),
    ("Cetirizine 10 mg tablets", "Tablet", 5, "10 mg at night"),
    ("Ferrous sulphate 200 mg tablets", "Tablet", 3, "200 mg once a day"),
    ("Albendazole 400 mg tablets", "Tablet", 20, "400 mg single dose"),
    ("Oral rehydration salts sachets", "Syrup", 20, "1 sachet after each loose stool"),
    ("Zinc sulphate 20 mg dispersible tablets", "Tablet", 5, "20 mg once a day"),
    ("Amoxicillin 250 mg/5 ml suspension", "Syrup", 180, "5 ml three times a day"),
    ("Paracetamol 120 mg/5 ml syrup", "Syrup", 120, "5 ml three times a day"),
    ("Salbutamol 100 mcg inhaler", "Injectable", 450, "2 puffs when needed"),
    ("Ceftriaxone 1 g injection", "Injectable", 150, "1 g once a day"),
    ("Hydrocortisone 1% cream", "Cream", 180, "Apply twice a day"),
]
DRUGS_FOR = {
    "malaria": ["Artemether/lumefantrine 20/120 mg tablets", "Paracetamol 500 mg tablets"],
    "respiratory": ["Amoxicillin 500 mg capsules", "Paracetamol 500 mg tablets", "Cetirizine 10 mg tablets"],
    "Tonsillitis": ["Amoxicillin 500 mg capsules", "Paracetamol 500 mg tablets"],
    "Pneumonia": ["Ceftriaxone 1 g injection", "Amoxicillin 500 mg capsules"],
    "gastro": ["Oral rehydration salts sachets", "Zinc sulphate 20 mg dispersible tablets", "Metronidazole 400 mg tablets"],
    "Urinary": ["Ciprofloxacin 500 mg tablets"],
    "Typhoid": ["Ciprofloxacin 500 mg tablets", "Paracetamol 500 mg tablets"],
    "Hypertension": ["Amlodipine 5 mg tablets", "Losartan 50 mg tablets"],
    "diabetes": ["Metformin 500 mg tablets"],
    "Peptic": ["Omeprazole 20 mg capsules"],
    "pain": ["Ibuprofen 400 mg tablets"],
    "worms": ["Albendazole 400 mg tablets"],
    "dermatitis": ["Hydrocortisone 1% cream", "Cetirizine 10 mg tablets"],
    "Asthma": ["Salbutamol 100 mcg inhaler"],
    "anaemia": ["Ferrous sulphate 200 mg tablets"],
    "Antenatal": ["Ferrous sulphate 200 mg tablets"],
}
SERVICES = [
    ("General consultation", "consultation", 1000),
    ("Specialist consultation", "consultation", 2000),
    ("Review visit", "consultation", 500),
    ("Wound dressing", "procedure", 500),
    ("Incision and drainage", "procedure", 2000),
    ("Nebulisation", "procedure", 800),
    ("Intravenous cannulation and fluids", "procedure", 1500),
    ("Chest X-ray", "radiology", 1500),
    ("Abdominal ultrasound", "radiology", 2500),
    ("Obstetric ultrasound", "radiology", 2500),
    ("Electrocardiogram (ECG)", "cardiology", 2000),
    ("Echocardiogram", "cardiology", 6000),
    ("Tooth extraction", "dental", 1500),
    ("Dental filling", "dental", 3000),
    ("Scaling and polishing", "dental", 2500),
    ("Caesarean section", "theatre", 45000),
    ("Appendicectomy", "theatre", 60000),
    ("Hernia repair", "theatre", 40000),
    ("Eye examination", "eye", 1500),
]
NOTE_TEMPLATES = [
    ("Common cold", "presenting_complaints", "Cough, running nose and sore throat for 3 days. No difficulty in breathing."),
    ("Fever with chills", "presenting_complaints", "Fever with chills and headache for 2 days. No vomiting or diarrhoea."),
    ("Well looking adult", "general_appearance", "Alert, not pale, not jaundiced, well hydrated, no lymphadenopathy."),
    ("Sick child", "general_appearance", "Febrile, irritable, mildly dehydrated. Not in respiratory distress."),
    ("Normal heart", "cvs", "S1 and S2 heard, no murmurs. Pulse regular, capillary refill under 2 seconds."),
    ("Clear chest", "respiratory", "Air entry equal both sides, no crackles or wheeze. Not using accessory muscles."),
    ("Soft abdomen", "abdomen_and_Gut", "Soft, non tender, no organomegaly. Bowel sounds present."),
    ("Normal CNS", "cns", "Conscious and oriented, GCS 15/15. No neck stiffness, no focal deficits."),
    ("Uncomplicated malaria", "treatment_plan", "Start AL as per weight for 3 days, paracetamol for fever. Review if vomiting or not better in 48 hours."),
    ("Hypertension review", "treatment_plan", "Continue current medication, low salt diet, review in 1 month with BP log."),
    ("Discharge, home care", "discharge_summary", "Condition improved. Discharged home on oral medication. Review in the clinic in 1 week, return earlier if unwell."),
]
INSURERS = ["Social Health Authority (SHA)", "Jubilee Health Insurance", "AAR Insurance", "Britam Health", "CIC Insurance"]
ACCOUNTS = ["Kenya Power Staff Medical Scheme", "Nairobi Water Staff Scheme"]
SUPPLIERS = [("Mission for Essential Drugs and Supplies (MEDS)", "+254 20 3920000"), ("KEMSA", "+254 20 3922000"),
             ("Dawa Limited", "+254 722 200 300"), ("Surgilinks Limited", "+254 733 410 410")]
WARDS = [("Male medical ward", "general_male", 2500, 10), ("Female medical ward", "general_female", 2500, 10),
         ("Paediatric ward", "paediatric", 2000, 8), ("Maternity ward", "maternity", 3000, 8),
         ("Intensive care unit", "icu", 15000, 4), ("Private wing", "private", 6000, 6)]
CHART = [
    ("1000", "Assets", "asset", None), ("1100", "Cash on hand", "asset", "1000"), ("1110", "M-Pesa till", "asset", "1000"),
    ("1200", "Bank accounts", "asset", "1000"), ("1210", "KCB current account", "asset", "1200"),
    ("1220", "Equity Bank collections account", "asset", "1200"), ("1300", "Receivable from insurers", "asset", "1000"),
    ("1400", "Drug and supplies stock", "asset", "1000"),
    ("2000", "Liabilities", "liability", None), ("2100", "Supplier payables", "liability", "2000"),
    ("2200", "VAT payable", "liability", "2000"), ("2300", "PAYE and statutory deductions", "liability", "2000"),
    ("3000", "Equity", "equity", None), ("3100", "Owner capital", "equity", "3000"), ("3200", "Retained earnings", "equity", "3000"),
    ("4000", "Income", "income", None), ("4100", "Consultation fees", "income", "4000"), ("4200", "Laboratory income", "income", "4000"),
    ("4300", "Pharmacy sales", "income", "4000"), ("4400", "Inpatient bed charges", "income", "4000"),
    ("4500", "Imaging and cardiology", "income", "4000"), ("4600", "Theatre and procedures", "income", "4000"),
    ("5000", "Expenses", "expense", None), ("5100", "Staff salaries", "expense", "5000"), ("5200", "Drug purchases", "expense", "5000"),
    ("5300", "Utility bills", "expense", "5000"), ("5400", "Internet and phones", "expense", "5000"),
]

# username, first name, last name, gender, title, modules, is a doctor, speciality
STAFF = [
    ("demo.admin", "Ruth", "Kendi", "Female", "Receptionist", access.MODULES, False, None),
    ("reception", "Faith", "Njambi", "Female", "Receptionist", [access.PATIENTS], False, None),
    ("triage", "Lucy", "Chepkemoi", "Female", "Nurse", [access.PATIENTS], False, None),
    ("dr.mwangi", "Samuel", "Mwangi", "Male", "Doctor", [access.DOCTOR], True, "General medicine"),
    ("dr.achieng", "Mary", "Achieng", "Female", "Doctor", [access.DOCTOR], True, "Paediatrics"),
    ("dr.kiprono", "Daniel", "Kiprono", "Male", "Doctor", [access.DOCTOR, access.THEATRE], True, "Surgery"),
    ("dr.wanjiru", "Grace", "Wanjiru", "Female", "Doctor", [access.DOCTOR], True, "Obstetrics and gynaecology"),
    ("dr.otieno", "Kevin", "Otieno", "Male", "Doctor", [access.DOCTOR, access.DENTAL], True, "Dentistry"),
    ("lab", "Brian", "Wekesa", "Male", "Lab Technologist", [access.LABORATORY], False, None),
    ("pharmacy", "Esther", "Moraa", "Female", "Pharmacist", [access.PHARMACY], False, None),
    ("stores", "Collins", "Barasa", "Male", "Pharmacist", [access.INVENTORY], False, None),
    ("radiology", "Joseph", "Kilonzo", "Male", "Radiologist", [access.RADIOLOGY], False, None),
    ("cardiology", "Halima", "Abdi", "Female", "Cardiologist", [access.CARDIOLOGY], False, None),
    ("theatre", "Neema", "Owino", "Female", "Nurse", [access.THEATRE], False, None),
    ("anaesthesia", "Peter", "Langat", "Male", "Anaesthetist", [access.THEATRE], False, None),
    ("cashier", "Joyce", "Mutua", "Female", "Receptionist", [access.FINANCE], False, None),
    ("accounts", "David", "Kimani", "Male", "Receptionist", [access.FINANCE], False, None),
    ("admin", "Hassan", "Ali", "Male", "Receptionist", [access.ADMINISTRATION], False, None),
]


class Command(BaseCommand):
    help = "Seed believable demo data: staff for every module, patients, 90 days of visits, wards, money and stock."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Remove patient, money and stock records first.")

    def handle(self, *args, **options):
        User = get_user_model()
        if User.objects.filter(username=MARKER).exists() and not options["reset"]:
            raise CommandError("Demo data is already in this database. Run with --reset to rebuild it.")
        self.random = random.Random(2026)
        self.now = timezone.localtime()
        self.today = self.now.date()
        with audit.paused(), transaction.atomic():
            if options["reset"]:
                self.reset()
            self.lookups()
            self.people()
            self.stock()
            self.patients()
            self.history()
            self.inpatients()
            self.emergencies()
            self.appointments()
            self.money()
            self.stores()
            # a visit's last change is its last recorded step, not the moment it was seeded
            self.touch_visits()
        self.stdout.write(self.style.SUCCESS(
            f"Seeded {PatientModels.Patient.objects.count()} patients and {PatientModels.Visit.objects.count()} visits."))
        self.stdout.write(f"Sign in as any of: {', '.join(row[0] for row in STAFF)}")
        self.stdout.write(f"Password for all of them: {PASSWORD}  ({MARKER} can open every module)")

    # ------------------------------------------------------------------ helpers

    def touch_visits(self):
        from django.db.models import Max

        latest = PatientModels.Visit.objects.annotate(
            triaged=Max("triage__created_on"), diagnosed=Max("diagnosis__created_on"))
        for visit in latest.only("pk", "visit_date"):
            moments = [moment for moment in (visit.visit_date, visit.triaged, visit.diagnosed) if moment]
            PatientModels.Visit.objects.filter(pk=visit.pk).update(updated_on=max(moments))

    def at(self, day, hour, minute=0):
        moment = timezone.make_aware(datetime.datetime.combine(day, datetime.time(hour, minute)))
        return min(moment, self.now - datetime.timedelta(minutes=2)) if day == self.today else moment

    def day_time(self, day):
        """A time during clinic hours, weighted to the morning rush."""
        hour = self.random.choices(range(7, 20), weights=[6, 10, 10, 9, 7, 6, 6, 5, 4, 3, 2, 2, 1])[0]
        return self.at(day, hour, self.random.randrange(60))

    def later(self, moment, low, high):
        moment = moment + datetime.timedelta(minutes=self.random.randint(low, high))
        return min(moment, self.now - datetime.timedelta(minutes=1))

    def phone(self):
        return f"+2547{self.random.randint(0, 99):02d}{self.random.randint(0, 999999):06d}"

    def money_value(self, value):
        return Decimal(value).quantize(Decimal("0.01"))

    # ------------------------------------------------------------------ reset

    def reset(self):
        doomed = [
            FinanceModels.EtimsSubmission, FinanceModels.InsuranceClaim, FinanceModels.MpesaTransaction, FinanceModels.Refund,
            FinanceModels.Payment, FinanceModels.InvoiceItem, FinanceModels.Invoice, FinanceModels.CompanyPayment,
            FinanceModels.CashierShift, FinanceModels.BankTransaction, FinanceModels.BankAccount, FinanceModels.Expenditure,
            ClinicalModels.BedCharge, ClinicalModels.Admission, ClinicalModels.EmergencyCase, ClinicalModels.Appointment,
            ClinicalModels.Bed, ClinicalModels.Ward, ClinicalModels.NoteTemplate,
            StoreModels.RequisitionLine, StoreModels.Requisition, StoreModels.PurchaseOrderLine, StoreModels.PurchaseOrder,
            StoreModels.StockAdjustment, DepartmentModels.ExamImage, DepartmentModels.TheatreBooking,
            DepartmentModels.DentalProcedure, DepartmentModels.DepartmentRequest, DepartmentModels.Prescription,
            DepartmentModels.StockBatch, LabModels.Sample, LabModels.SubTestResult, LabModels.TestResult,
            LabModels.AssignedTest, LabModels.Request, FinanceModels.VisitService,
            PatientModels.Diagnosis, PatientModels.GeneralFinding, PatientModels.Triage, PatientModels.Allergy,
            PatientModels.Visit, FinanceModels.Billing, PatientModels.NextOfKin, PatientModels.Patient,
            FinanceModels.LedgerAccount,
        ]
        for model in doomed:
            if model is FinanceModels.LedgerAccount:
                for depth in range(3):
                    model.objects.filter(children__isnull=True).delete()
                model.objects.all().delete()
                continue
            model.objects.all().delete()
        usernames = [row[0] for row in STAFF]
        staff = ManagerModels.Staff.objects.filter(user__username__in=usernames)
        DoctorModels.Doctor.objects.filter(pk__in=staff.exclude(doctor=None).values("doctor")).delete()
        staff.delete()
        get_user_model().objects.filter(username__in=usernames).delete()
        demo_locations = ManagerModels.Location.objects.filter(code__startswith="D-")
        while demo_locations.exists():  # leaves first, the parent link is protected
            demo_locations.filter(children__isnull=True).delete()
        self.stdout.write("Removed the previous records.")

    # ------------------------------------------------------------------ lookups

    def lookups(self):
        self.categories = {name: ManagerModels.VisitCategory.objects.get_or_create(name=name)[0]
                           for name in ("Outpatient", "Emergency", "Inpatient", "Antenatal")}
        self.billing_types = {kind: FinanceModels.BillingType.objects.filter(kind=kind).first()
                              or FinanceModels.BillingType.objects.create(name=kind.title(), kind=kind)
                              for kind in ("cash", "insurance", "account")}
        self.insurers = [FinanceModels.InsuranceCompany.objects.get_or_create(
            name=name, defaults={"telephone": self.phone(), "contact_person": "Claims desk", "location": "Nairobi"})[0]
            for name in INSURERS]
        self.sha = self.insurers[0]
        self.account_companies = [FinanceModels.AccountCompany.objects.get_or_create(
            name=name, defaults={"telephone": self.phone(), "contact_person": "HR office", "location": "Nairobi"})[0]
            for name in ACCOUNTS]
        self.services = {}
        for name, category, fee in SERVICES:
            self.services[name] = FinanceModels.Service.objects.get_or_create(
                name=name, defaults={"category": category, "fee": Decimal(fee)})[0]
        self.lab_tests = {}
        for category, name, price, normal in LAB_TESTS:
            test_category = LabModels.TestCategory.objects.get_or_create(name=category)[0]
            self.lab_tests[name] = LabModels.LabTest.objects.get_or_create(
                name=name, defaults={"category": test_category, "price": Decimal(price), "dafault_range": normal})[0]
        self.lab_category = LabModels.RequestCategory.objects.get_or_create(name=LabModels.LABORATORY_REQUEST_CATEGORY)[0]
        self.suppliers = [DepartmentModels.Supplier.objects.get_or_create(name=name, defaults={"telephone": phone})[0]
                          for name, phone in SUPPLIERS]
        self.drugs, self.dosages = {}, {}
        for name, category, price, dosage in DRUGS:
            self.drugs[name] = DepartmentModels.Drug.objects.get_or_create(name=name, defaults={
                "category": DepartmentModels.DrugCategory.objects.get_or_create(name=category)[0],
                "unit_price": Decimal(price), "supplier": self.random.choice(self.suppliers)})[0]
            self.dosages[name] = dosage
        self.expense_categories = {name: FinanceModels.ExpenseCategory.objects.get_or_create(name=name)[0]
                                   for name in ("Drug Purchases", "Hospital Internet", "Staff Salaries", "Utility Bills")}

    # ------------------------------------------------------------------ staff

    def people(self):
        User = get_user_model()
        self.users, self.doctors = {}, {}
        groups = {module: Group.objects.get_or_create(name=module)[0] for module in access.MODULES}
        for username, first, last, gender, title, modules, is_doctor, speciality in STAFF:
            user = User.objects.create_user(username=username, password=PASSWORD, first_name=first, last_name=last,
                                            email=f"{username.replace('.', '')}@demo-hospital.example")
            user.groups.set([groups[module] for module in modules])
            staff = ManagerModels.Staff(
                firstname=first, lastname=last, gender=gender, telnumber=self.phone(), user=user,
                title=ManagerModels.StaffTitle.objects.get_or_create(name=title)[0], location="Main block")
            if is_doctor:
                spec = DoctorModels.DoctorSpeciality.objects.get_or_create(name=speciality)[0]
                doctor = DoctorModels.Doctor.objects.create(firstname=first, lastname=last, gender=gender, telnumber=staff.telnumber)
                staff.doctor, staff.speciality = doctor, spec
                self.doctors[username] = (doctor, spec, user)
            staff.save()
            self.users[username] = user
        self.staff = {row.user.username: row for row in ManagerModels.Staff.objects.filter(user__in=self.users.values())}
        self.cashiers = [self.users["cashier"], self.users["accounts"]]

        building = ManagerModels.Location.objects.create(name="Main block", code="D-MB", kind="building")
        self.floors = [ManagerModels.Location.objects.create(name=name, code=f"D-MB-{index}", kind="floor", parent=building)
                       for index, name in enumerate(("Ground floor", "First floor", "Second floor"))]
        for name, code, kind, floor in [
            ("Outpatient clinic", "D-OPD", "clinic", 0), ("Emergency department", "D-ER", "department", 0),
            ("Laboratory", "D-LAB", "department", 0), ("Pharmacy", "D-PHA", "department", 0),
            ("Radiology", "D-RAD", "department", 0), ("Main store", "D-STO", "store", 0),
            ("Main theatre", "D-THE", "theatre", 2), ("Accounts office", "D-ACC", "office", 1),
            ("Dental clinic", "D-DEN", "clinic", 1),
        ]:
            ManagerModels.Location.objects.create(name=name, code=code, kind=kind, parent=self.floors[floor])

        self.wards = []
        for index, (name, kind, rate, beds) in enumerate(WARDS):
            location = ManagerModels.Location.objects.create(
                name=name, code=f"D-W{index + 1}", kind="ward", parent=self.floors[1 if index < 4 else 2])
            ward = ClinicalModels.Ward.objects.create(name=name, kind=kind, daily_rate=Decimal(rate), location=location)
            prefix = "".join(word[0] for word in name.split()[:2]).upper()
            for number in range(1, beds + 1):
                ClinicalModels.Bed.objects.create(ward=ward, number=f"{prefix}-{number:02d}")
            self.wards.append(ward)

        for name, section, body in NOTE_TEMPLATES:
            ClinicalModels.NoteTemplate.objects.create(name=name, section=section, body=body, created_by=self.users["dr.mwangi"])

        accounts = {}
        for code, name, kind, parent in CHART:
            accounts[code] = FinanceModels.LedgerAccount.objects.create(
                code=code, name=name, account_type=kind, parent=accounts.get(parent))
        self.ledger = accounts

    # ------------------------------------------------------------------ stock

    def stock(self):
        store = self.users["stores"]
        for index, drug in enumerate(self.drugs.values()):
            received = self.at(self.today - datetime.timedelta(days=self.random.randint(100, 200)), 10)
            DepartmentModels.StockBatch.objects.create(
                drug=drug, supplier=drug.supplier, quantity_received=3000, quantity_remaining=3000,
                expiry_date=self.today + datetime.timedelta(days=self.random.randint(240, 700)), received_by=store, received_on=received)
            if index % 4 == 0:  # a batch close to expiry
                DepartmentModels.StockBatch.objects.create(
                    drug=drug, supplier=drug.supplier, quantity_received=200, quantity_remaining=self.random.randint(20, 160),
                    expiry_date=self.today + datetime.timedelta(days=self.random.choice([12, 25, 40, 55, 80])),
                    received_by=store, received_on=received - datetime.timedelta(days=200))
            if index % 7 == 3:  # an expired batch still on the shelf
                DepartmentModels.StockBatch.objects.create(
                    drug=drug, supplier=drug.supplier, quantity_received=100, quantity_remaining=self.random.randint(5, 40),
                    expiry_date=self.today - datetime.timedelta(days=self.random.randint(3, 30)),
                    received_by=store, received_on=received - datetime.timedelta(days=400))

    # ------------------------------------------------------------------ patients

    def patients(self):
        self.patient_list = []
        for index in range(140):
            gender = self.random.choice(["Female", "Male"])
            # a population with many young children and working-age adults
            age = self.random.choices([self.random.randint(0, 4), self.random.randint(5, 14), self.random.randint(15, 39),
                                       self.random.randint(40, 64), self.random.randint(65, 88)], weights=[22, 14, 34, 22, 8])[0]
            born = self.today - datetime.timedelta(days=age * 365 + self.random.randint(0, 364))
            created = self.at(self.today - datetime.timedelta(days=self.random.randint(DAYS + 5, 540)), 9)
            first = self.random.choice(FIRST_FEMALE if gender == "Female" else FIRST_MALE)
            patient = PatientModels.Patient.objects.create(
                firstname=first, middlename=self.random.choice(MIDDLE), lastname=self.random.choice(LAST), gender=gender,
                age=age, date_of_birth=timezone.make_aware(datetime.datetime.combine(born, datetime.time(0))),
                telnumber=self.phone(), address=self.random.choice(TOWNS),
                nin=f"{self.random.randint(20000000, 39999999)}" if age >= 18 else None, created_on=created)
            if age < 18 or self.random.random() < 0.4:
                PatientModels.NextOfKin.objects.create(
                    patient=patient, firstname=self.random.choice(FIRST_FEMALE + FIRST_MALE), lastname=patient.lastname,
                    gender=self.random.choice(["Female", "Male"]), telnumber=self.phone(),
                    relationship="Mother" if age < 18 else self.random.choice(["Husband", "Wife", "Brother", "Sister", "Son", "Daughter"]))
            if self.random.random() < 0.12:
                PatientModels.Allergy.objects.create(patient=patient, name=self.random.choice(
                    ["Penicillin", "Sulphonamides", "Aspirin", "Groundnuts"]), comment="Reported by the patient.")
            # payer stays the same for the patient across visits
            patient.payer = self.random.choices(["cash", "insurance", "account"], weights=[60, 33, 7])[0]
            patient.insurer = self.sha if self.random.random() < 0.55 else self.random.choice(self.insurers[1:])
            patient.member_number = f"{'SHA' if patient.insurer == self.sha else 'M'}{self.random.randint(10000000, 99999999)}"
            self.patient_list.append(patient)
        # patients registered within the period, so new registrations show on the home page
        for patient in self.random.sample(self.patient_list, 30):
            patient.created_on = self.at(self.today - datetime.timedelta(days=self.random.randint(0, DAYS)), 8)
            PatientModels.Patient.objects.filter(pk=patient.pk).update(created_on=patient.created_on)

    def billing_for(self, patient):
        kind = patient.payer
        billing = FinanceModels.Billing.objects.create(btype=self.billing_types[kind])
        if kind == "insurance":
            billing.insurance_company = patient.insurer
        elif kind == "account":
            billing.account_company = self.random.choice(self.account_companies)
        billing.save()
        return billing

    # ------------------------------------------------------------------ outpatient history

    def pick_diagnosis(self, patient):
        options = [(text, weight) for text, weight, band in DIAGNOSES
                   if band is None or (band == "child" and patient.age < 5) or (band == "adult" and patient.age >= 15)]
        if patient.gender == "Male":
            options = [(text, weight) for text, weight in options if "pregnancy" not in text]
        return self.random.choices([text for text, _ in options], weights=[weight for _, weight in options])[0]

    def history(self):
        self.visits = []
        busy_today = set()
        for offset in range(DAYS, -1, -1):
            day = self.today - datetime.timedelta(days=offset)
            weekday = day.weekday()
            base = {5: 10, 6: 6}.get(weekday, 18)
            trend = 1 + (DAYS - offset) / DAYS * 0.25  # the hospital is getting busier
            count = max(3, int(self.random.gauss(base * trend, 3)))
            if day == self.today:
                count = max(8, min(count, 26))
            patients = self.random.sample(self.patient_list, min(count, len(self.patient_list)))
            for patient in patients:
                if day == self.today:
                    busy_today.add(patient.pk)
                self.visit(patient, day, is_today=day == self.today)
        self.busy_today = busy_today

    def visit(self, patient, day, is_today=False):
        doctor_key = self.random.choices(
            ["dr.mwangi", "dr.achieng", "dr.kiprono", "dr.wanjiru", "dr.otieno"],
            weights=[40, 30 if patient.age < 15 else 4, 12, 14 if patient.gender == "Female" and patient.age >= 15 else 2, 6])[0]
        doctor, speciality, doctor_user = self.doctors[doctor_key]
        arrived = self.day_time(day)
        diagnosis_text = self.pick_diagnosis(patient)
        category = "Antenatal" if "Antenatal" in diagnosis_text else "Outpatient"
        visit = PatientModels.Visit.objects.create(
            patient=patient, category=self.categories[category], doctor=doctor, speciality=speciality,
            billing=self.billing_for(patient), visit_date=arrived, created_on=arrived, complete=not is_today)
        self.visits.append(visit)
        # today some patients are still at each step of the journey
        stage = self.random.choices(["waiting", "triaged", "consulted", "done"], weights=[3, 3, 5, 6])[0] if is_today else "done"
        if stage == "waiting":
            return visit

        triage_time = self.later(arrived, 5, 25)
        PatientModels.Triage.objects.create(
            visit=visit, blood_pressure=f"{self.random.randint(105, 165)}/{self.random.randint(65, 100)}",
            heart_rate=self.random.randint(62, 118), respiratory_rate=self.random.randint(14, 28),
            temperature=Decimal(f"{self.random.uniform(36.2, 39.4):.1f}"), oxygen_saturation=self.random.randint(93, 100),
            weight=Decimal(f"{(self.random.uniform(4, 18) if patient.age < 5 else self.random.uniform(18, 45) if patient.age < 15 else self.random.uniform(48, 98)):.1f}"),
            height=Decimal(f"{(self.random.uniform(55, 110) if patient.age < 5 else self.random.uniform(110, 165) if patient.age < 15 else self.random.uniform(150, 185)):.0f}"),
            created_on=triage_time)
        if stage == "triaged":
            return visit

        seen = self.later(triage_time, 10, 60)
        consult_fee = self.services["Specialist consultation" if doctor_key != "dr.mwangi" else "General consultation"]
        FinanceModels.VisitService.objects.create(visit=visit, service=consult_fee, price=consult_fee.fee,
                                                  ordered_by=doctor_user, created_on=seen)
        key = next((word for word in ("malaria", "respiratory", "gastro") if word in diagnosis_text.lower()), "default")
        PatientModels.GeneralFinding.objects.create(
            visit=visit, presenting_complaints=COMPLAINTS[key], general_appearance="Alert, not pale, well hydrated.",
            treatment_plan="As prescribed. Review if symptoms persist.", created_on=seen)
        PatientModels.Diagnosis.objects.create(visit=visit, diagnosis=diagnosis_text, created_by=doctor_user, created_on=seen)
        if self.random.random() < 0.15:
            PatientModels.Diagnosis.objects.create(visit=visit, diagnosis=self.pick_diagnosis(patient),
                                                   created_by=doctor_user, created_on=seen)
        pending = is_today and stage == "consulted"
        self.lab_work(visit, diagnosis_text, doctor, doctor_user, seen, pending)
        self.prescriptions(visit, diagnosis_text, doctor_user, seen, pending)
        self.extras(visit, patient, diagnosis_text, doctor_user, seen, pending)
        if not pending:
            self.bill(visit, seen, is_today)
        return visit

    def lab_work(self, visit, diagnosis_text, doctor, doctor_user, seen, pending):
        names = next((tests for key, tests in TESTS_FOR.items() if key.lower() in diagnosis_text.lower()), None)
        if not names and self.random.random() < 0.25:
            names = [self.random.choice(["Full blood count", "Urinalysis", "Random blood sugar"])]
        if not names or self.random.random() < 0.2:
            return
        request = LabModels.Request.objects.create(visit=visit, category=self.lab_category, doctor=doctor,
                                                   handled=not pending, created_on=seen)
        for name in names:
            test = self.lab_tests[name]
            assigned = LabModels.AssignedTest.objects.create(request=request, test=test, price=test.price)
            if not pending:
                result = test.dafault_range
                if "Confirmed malaria" in diagnosis_text and "malaria" in name.lower():
                    result = "Positive, P. falciparum"
                LabModels.TestResult.objects.create(test=assigned, results=result, created_on=self.later(seen, 40, 120))
        specimen = "urine" if any("Urin" in name or "Pregnancy" in name for name in names) else (
            "stool" if any("Stool" in name or "stool" in name for name in names) else "whole_blood")
        collected = self.later(seen, 5, 20)
        if pending:
            status = self.random.choice(["collected", "received_in_lab", "in_analysis", None])
            if status is None:
                return  # ordered, not collected yet
        else:
            status = "rejected" if self.random.random() < 0.02 else "completed"
        LabModels.Sample.objects.create(
            request=request, specimen=specimen, status=status, collected_by=self.users["lab"], collected_on=collected,
            received_on=self.later(collected, 5, 15) if status != "collected" else None,
            completed_on=self.later(collected, 40, 120) if status == "completed" else None,
            rejection_reason="Haemolysed sample" if status == "rejected" else "")

    def prescriptions(self, visit, diagnosis_text, doctor_user, seen, pending):
        lowered = diagnosis_text.lower()
        names = next((drugs for key, drugs in DRUGS_FOR.items() if key.lower() in lowered), None)
        if "upper respiratory" in lowered:
            names = DRUGS_FOR["respiratory"]
        if "gastroenteritis" in lowered:
            names = DRUGS_FOR["gastro"]
        if not names:
            names = DRUGS_FOR["pain"]
        if visit.patient.age < 5:
            names = [{"Amoxicillin 500 mg capsules": "Amoxicillin 250 mg/5 ml suspension",
                      "Paracetamol 500 mg tablets": "Paracetamol 120 mg/5 ml syrup"}.get(name, name) for name in names]
        for name in names:
            drug = self.drugs[name]
            quantity = 1 if drug.category.name in ("Syrup", "Injectable", "Cream") else self.random.choice([10, 14, 15, 20, 24, 30])
            issued = not pending or self.random.random() < 0.3
            DepartmentModels.Prescription.objects.create(
                visit=visit, drug=drug, dosage=self.dosages[name], duration=self.random.choice(["3 days", "5 days", "7 days", "1 month"]),
                quantity=quantity, unit_price=drug.unit_price, prescribed_by=doctor_user, created_on=seen,
                quantity_issued=quantity if issued else 0, issued_by=self.users["pharmacy"] if issued else None,
                issued_on=self.later(seen, 20, 90) if issued else None)
            if issued:
                batch = drug.batches.filter(quantity_remaining__gte=quantity).order_by("expiry_date").first() if hasattr(drug, "batches") \
                    else DepartmentModels.StockBatch.objects.filter(drug=drug, quantity_remaining__gte=quantity).order_by("expiry_date").first()
                if batch:
                    batch.quantity_remaining -= quantity
                    batch.save(update_fields=["quantity_remaining"])

    def extras(self, visit, patient, diagnosis_text, doctor_user, seen, pending):
        roll = self.random.random()
        if "Pneumonia" in diagnosis_text or (roll < 0.04 and patient.age >= 15):
            self.department_request(visit, "radiology", "Chest X-ray", doctor_user, seen, pending)
        elif "Antenatal" in diagnosis_text:
            self.department_request(visit, "radiology", "Obstetric ultrasound", doctor_user, seen, pending)
        elif "Hypertension" in diagnosis_text and roll < 0.3:
            self.department_request(visit, "cardiology", "Electrocardiogram (ECG)", doctor_user, seen, pending)
        elif "Peptic" in diagnosis_text and roll < 0.3:
            self.department_request(visit, "radiology", "Abdominal ultrasound", doctor_user, seen, pending)
        if "Dental" in diagnosis_text:
            procedure = self.services[self.random.choice(["Tooth extraction", "Dental filling", "Scaling and polishing"])]
            DepartmentModels.DentalProcedure.objects.create(
                visit=visit, tooth=self.random.choice(["Incisor", "Canine", "Pre-molar", "Molar"]), diagnosis="Dental caries",
                procedure=procedure, fee=procedure.fee, performed_on=self.later(seen, 15, 45), created_by=self.users["dr.otieno"])
        if "injury" in diagnosis_text.lower() or "sprain" in diagnosis_text:
            service = self.services["Wound dressing"]
            FinanceModels.VisitService.objects.create(visit=visit, service=service, price=service.fee,
                                                      ordered_by=doctor_user, created_on=seen)
        if "Asthma" in diagnosis_text:
            service = self.services["Nebulisation"]
            FinanceModels.VisitService.objects.create(visit=visit, service=service, price=service.fee,
                                                      ordered_by=doctor_user, created_on=seen)

    def department_request(self, visit, department, service_name, doctor_user, seen, pending):
        service = self.services[service_name]
        done = not pending or self.random.random() < 0.4
        reporter = self.users["radiology" if department == "radiology" else "cardiology"]
        findings = {
            "Chest X-ray": "Patchy opacities in the right lower zone, in keeping with pneumonia.",
            "Obstetric ultrasound": "Single live intrauterine pregnancy, cephalic, appropriate for dates.",
            "Electrocardiogram (ECG)": "Sinus rhythm, rate 78. Voltage criteria for left ventricular hypertrophy.",
            "Abdominal ultrasound": "Normal liver, gall bladder and kidneys. No free fluid.",
        }
        DepartmentModels.DepartmentRequest.objects.create(
            department=department, visit=visit, service=service, price=service.fee, requested_by=doctor_user, created_on=seen,
            status="completed" if done else "pending", result=findings.get(service_name) if done else None,
            reported_by=reporter if done else None, reported_on=self.later(seen, 30, 150) if done else None)

    # ------------------------------------------------------------------ billing

    def bill(self, visit, seen, is_today, items=None):
        items = items if items is not None else billable_items(visit)
        if not items:
            return None
        billing = visit.billing
        issued = self.later(seen, 30, 140)
        invoice = FinanceModels.Invoice.objects.create(
            patient=visit.patient, visit=visit, billing_type=billing.btype, insurance_company=billing.insurance_company,
            account_company=billing.account_company, issued_on=timezone.localtime(issued).date(),
            created_by=self.random.choice(self.cashiers), created_on=issued)
        for item in items:
            invoice.items.create(description=item["description"], quantity=item["quantity"],
                                 unit_price=item["unit_price"], source=item["source"])
        total = invoice.total
        kind = billing.btype.kind
        if kind == "insurance":
            covered = total if billing.insurance_company != self.sha else (total if self.random.random() < 0.8 else total * Decimal("0.7"))
            invoice.company_covered = self.money_value(covered)
            invoice.save(update_fields=["company_covered"])
        elif kind == "account":
            invoice.company_covered = total
            invoice.save(update_fields=["company_covered"])
        payable = invoice.patient_payable
        unpaid = self.random.random() < (0.35 if is_today else 0.04)
        if payable > 0 and not unpaid:
            method = self.random.choices(["mpesa", "cash", "card", "bank"], weights=[58, 30, 9, 3])[0]
            amount = payable if self.random.random() > 0.05 else self.money_value(payable / 2)
            cashier = self.random.choice(self.cashiers)
            payment = FinanceModels.Payment.objects.create(invoice=invoice, amount=amount, method=method, received_by=cashier,
                                                           received_on=self.later(issued, 2, 20))
            if method == "mpesa":
                FinanceModels.MpesaTransaction.objects.create(
                    receipt_number=self.mpesa_receipt(), phone=visit.patient.telnumber,
                    payer_name=f"{visit.patient.firstname} {visit.patient.lastname}".upper(),
                    account_reference=visit.patient.patient_id, amount=amount, transacted_on=payment.received_on,
                    status="matched", payment=payment, recorded_by=cashier, matched_by=cashier, matched_on=payment.received_on)
        invoice.refresh_status()
        if kind == "insurance" and invoice.company_covered:
            self.claim(invoice, visit.patient, issued, is_today)
        return invoice

    def mpesa_receipt(self):
        letters = "ABCDEFGHJKLMNPQRSTUVWXYZ0123456789"
        return "T" + "".join(self.random.choice(letters) for _ in range(9))

    def claim(self, invoice, patient, issued, is_today):
        age = (self.today - timezone.localtime(issued).date()).days
        if is_today:
            status = "draft"
        elif age < 7:
            status = self.random.choice(["draft", "submitted"])
        elif age < 30:
            status = self.random.choices(["submitted", "approved", "partial", "rejected"], weights=[5, 4, 1, 1])[0]
        else:
            status = self.random.choices(["paid", "approved", "partial", "rejected"], weights=[7, 2, 1, 1])[0]
        claimed = invoice.company_covered
        approved = {"approved": claimed, "paid": claimed, "partial": self.money_value(claimed * Decimal("0.8"))}.get(status)
        FinanceModels.InsuranceClaim.objects.create(
            invoice=invoice, insurer=invoice.insurance_company, member_number=patient.member_number,
            preauthorisation=f"PA{self.random.randint(100000, 999999)}" if invoice.insurance_company == self.sha else "",
            amount_claimed=claimed, amount_approved=approved, status=status,
            insurer_reference=f"REF{self.random.randint(1000000, 9999999)}" if status != "draft" else "",
            rejection_reason="Member benefits exhausted for the year" if status == "rejected" else "",
            submitted_on=self.later(issued, 60, 60 * 24 * 3) if status != "draft" else None,
            decided_on=self.later(issued, 60 * 24 * 5, 60 * 24 * 20) if status in ("approved", "partial", "rejected", "paid") else None,
            created_by=self.users["accounts"], created_on=issued)

    # ------------------------------------------------------------------ inpatients

    def inpatients(self):
        nurse_user = self.users["triage"]
        beds = {ward.pk: list(ward.beds.order_by("number")) for ward in self.wards}
        busy = set(self.busy_today)
        ward_for = lambda patient: (self.wards[2] if patient.age < 13 else
                                    self.wards[3] if patient.gender == "Female" and patient.age < 40 and self.random.random() < 0.3 else
                                    self.wards[0] if patient.gender == "Male" else self.wards[1])
        reasons = ["Severe malaria for intravenous artesunate", "Pneumonia, needs oxygen and IV antibiotics",
                   "Severe dehydration from gastroenteritis", "Uncontrolled diabetes with high sugars",
                   "Hypertensive urgency for observation", "Road traffic injury, fracture of the left tibia",
                   "Labour, admitted for delivery", "Post operative care after appendicectomy"]
        candidates = [patient for patient in self.patient_list if patient.pk not in busy]
        self.random.shuffle(candidates)

        # discharged over the period
        for patient in candidates[:45]:
            ward = ward_for(patient)
            admitted_day = self.today - datetime.timedelta(days=self.random.randint(5, DAYS))
            stay = self.random.choice([1, 2, 2, 3, 3, 4, 5, 7])
            admitted = self.at(admitted_day, self.random.randint(9, 18))
            discharged = admitted + datetime.timedelta(days=stay, hours=self.random.randint(-3, 3))
            if discharged >= self.now:
                continue
            visit = self.inpatient_visit(patient, admitted, complete=True)
            bed = self.random.choice(beds[ward.pk])
            admission = ClinicalModels.Admission.objects.create(
                patient=patient, visit=visit, requested_ward=ward, bed=bed, doctor=visit.doctor, reason=self.random.choice(reasons),
                status="discharged", requested_on=admitted - datetime.timedelta(minutes=40), admitted_on=admitted,
                discharged_on=discharged, discharge_type=self.random.choices(["home", "referred", "absconded", "died"], weights=[90, 6, 2, 2])[0],
                discharge_summary=NOTE_TEMPLATES[-1][2], requested_by=nurse_user, discharged_by=self.users["dr.mwangi"])
            post_bed_charges([admission], until=timezone.localtime(discharged).date())
            self.bill(visit, discharged - datetime.timedelta(hours=1), False)

        # in the wards now
        current = candidates[45:45 + 26]
        for patient in current:
            ward = ward_for(patient)
            free = [bed for bed in beds[ward.pk] if bed.status == "available"]
            if not free:
                ward = self.wards[5]
                free = [bed for bed in beds[ward.pk] if bed.status == "available"]
                if not free:
                    break
            bed = free[0]
            admitted = self.at(self.today - datetime.timedelta(days=self.random.randint(0, 9)), self.random.randint(8, 18))
            visit = self.inpatient_visit(patient, admitted, complete=False)
            admission = ClinicalModels.Admission.objects.create(
                patient=patient, visit=visit, requested_ward=ward, bed=bed, doctor=visit.doctor, reason=self.random.choice(reasons),
                status="admitted", requested_on=admitted - datetime.timedelta(minutes=30), admitted_on=admitted, requested_by=nurse_user)
            bed.status = "occupied"
            bed.save(update_fields=["status"])
            post_bed_charges([admission], until=self.today - datetime.timedelta(days=self.random.choice([0, 1, 1, 2])))
        # ICU and a couple of beds being cleaned or repaired
        for ward in self.wards:
            for bed in [bed for bed in beds[ward.pk] if bed.status == "available"][:1]:
                bed.status = self.random.choice(["cleaning", "cleaning", "out_of_service"])
                bed.save(update_fields=["status"])

        # waiting for a bed
        for patient in candidates[71:75]:
            requested = self.now - datetime.timedelta(minutes=self.random.randint(20, 300))
            visit = self.inpatient_visit(patient, requested, complete=False)
            ClinicalModels.Admission.objects.create(
                patient=patient, visit=visit, requested_ward=ward_for(patient), doctor=visit.doctor, reason=self.random.choice(reasons),
                status="awaiting", requested_on=requested, requested_by=nurse_user)
        self.inpatient_ids = {patient.pk for patient in candidates[:75]}

        # theatre
        surgeon, anaesthetist, nurse = self.staff["dr.kiprono"], self.staff["anaesthesia"], self.staff["theatre"]
        for offset in list(range(-30, 0, 3)) + [0, 1, 2, 4]:
            day = self.today + datetime.timedelta(days=offset)
            patient = self.random.choice([p for p in self.patient_list if p.age >= 15])
            visit = PatientModels.Visit.objects.filter(patient=patient).order_by("-visit_date").first()
            if visit is None:
                continue
            operation = self.random.choice(["Appendicectomy", "Hernia repair", "Caesarean section" if patient.gender == "Female" else "Hernia repair"])
            scheduled = timezone.make_aware(datetime.datetime.combine(day, datetime.time(self.random.choice([8, 10, 13]))))
            DepartmentModels.TheatreBooking.objects.create(
                visit=visit, service=self.services[operation], surgery_type=operation, body_location="Abdomen",
                surgeon=surgeon, anaesthetist=anaesthetist, nurse_one=nurse, scheduled_for=scheduled,
                status="completed" if scheduled < self.now else "scheduled", created_by=self.users["dr.kiprono"])

    def inpatient_visit(self, patient, moment, complete):
        doctor, speciality, doctor_user = self.doctors["dr.achieng" if patient.age < 13 else "dr.mwangi"]
        visit = PatientModels.Visit.objects.create(
            patient=patient, category=self.categories["Inpatient"], doctor=doctor, speciality=speciality,
            billing=self.billing_for(patient), visit_date=moment, created_on=moment, complete=complete)
        PatientModels.Diagnosis.objects.create(visit=visit, diagnosis=self.pick_diagnosis(patient), created_by=doctor_user, created_on=moment)
        return visit

    # ------------------------------------------------------------------ emergency

    def emergencies(self):
        complaints = [("red", "Unconscious after a road traffic accident"), ("red", "Severe difficulty in breathing"),
                      ("orange", "Chest pain radiating to the left arm"), ("orange", "Convulsions in a child with fever"),
                      ("orange", "Heavy bleeding in pregnancy"), ("yellow", "Deep cut on the forearm"),
                      ("yellow", "Vomiting and severe abdominal pain"), ("yellow", "High fever with confusion"),
                      ("green", "Ankle twisted while playing football"), ("green", "Minor burn on the hand"),
                      ("green", "Dog bite on the leg")]
        busy = self.busy_today | self.inpatient_ids
        candidates = [patient for patient in self.patient_list if patient.pk not in busy]
        self.random.shuffle(candidates)
        doctor = self.doctors["dr.kiprono"][0]
        for offset in range(DAYS, 0, -1):
            for _ in range(self.random.choice([1, 2, 2, 3, 4])):
                patient = self.random.choice(self.patient_list)
                acuity, complaint = self.random.choices(complaints, weights=[1, 1, 2, 2, 1, 3, 3, 2, 4, 2, 1])[0]
                arrived = self.at(self.today - datetime.timedelta(days=offset), self.random.randint(0, 23), self.random.randrange(60))
                wait = {"red": 2, "orange": 9, "yellow": 45, "green": 120}[acuity]
                seen = arrived + datetime.timedelta(minutes=max(0, int(self.random.gauss(wait, wait / 2))))
                ClinicalModels.EmergencyCase.objects.create(
                    patient=patient, acuity=acuity, chief_complaint=complaint, arrival_mode=self.random.choices(
                        ["walk_in", "ambulance", "referral", "police"], weights=[6, 3, 2, 1])[0],
                    status=self.random.choices(["discharged", "admitted", "transferred", "died"], weights=[80, 14, 5, 1])[0],
                    attending=doctor, arrived_on=arrived, seen_on=seen, closed_on=seen + datetime.timedelta(hours=self.random.randint(1, 6)),
                    created_by=self.users["triage"])
        # open right now
        for index, (status, minutes) in enumerate([("waiting", 6), ("waiting", 25), ("waiting", 75), ("in_treatment", 40),
                                                    ("in_treatment", 95), ("awaiting", 150), ("waiting", 3)]):
            patient = candidates[index]
            acuity, complaint = complaints[[0, 5, 8, 2, 6, 1, 3][index]]
            arrived = self.now - datetime.timedelta(minutes=minutes)
            visit = PatientModels.Visit.objects.create(
                patient=patient, category=self.categories["Emergency"], billing=self.billing_for(patient),
                visit_date=arrived, created_on=arrived, complete=False)
            ClinicalModels.EmergencyCase.objects.create(
                patient=patient, visit=visit, acuity=acuity, chief_complaint=complaint, arrival_mode="ambulance" if acuity == "red" else "walk_in",
                status=status, attending=doctor if status != "waiting" else None, arrived_on=arrived,
                seen_on=arrived + datetime.timedelta(minutes=minutes // 3) if status != "waiting" else None, created_by=self.users["triage"])

    # ------------------------------------------------------------------ appointments

    def appointments(self):
        reasons = ["Hypertension review", "Diabetes clinic", "Antenatal visit", "Wound review", "Child welfare clinic",
                   "Follow up of lab results", "Dental review"]
        doctor_keys = ["dr.mwangi", "dr.achieng", "dr.wanjiru", "dr.otieno"]
        visits_by_patient = {}
        for visit in self.visits:
            visits_by_patient.setdefault((visit.patient_id, timezone.localtime(visit.visit_date).date()), visit)
        for offset in range(-21, 15):
            day = self.today + datetime.timedelta(days=offset)
            if day.weekday() == 6:
                continue
            for _ in range(self.random.randint(3, 7)):
                patient = self.random.choice(self.patient_list)
                doctor, speciality, _ = self.doctors[self.random.choice(doctor_keys)]
                when = timezone.make_aware(datetime.datetime.combine(day, datetime.time(self.random.randint(8, 16), self.random.choice([0, 15, 30, 45]))))
                visit = visits_by_patient.get((patient.pk, day))
                if offset < 0:
                    status = "checked_in" if visit else self.random.choices(["missed", "cancelled"], weights=[3, 1])[0]
                elif offset == 0:
                    status = "checked_in" if visit and when < self.now else "booked"
                else:
                    status = "booked"
                ClinicalModels.Appointment.objects.create(
                    patient=patient, doctor=doctor, speciality=speciality, category=self.categories["Outpatient"],
                    scheduled_for=when, reason=self.random.choice(reasons), status=status,
                    visit=visit if status == "checked_in" else None, created_by=self.users["reception"],
                    created_on=when - datetime.timedelta(days=self.random.randint(3, 30)))

    # ------------------------------------------------------------------ money

    def money(self):
        # insurer remittances against paid claims, one per insurer a month
        for insurer in self.insurers:
            by_month = {}
            for claim in FinanceModels.InsuranceClaim.objects.filter(insurer=insurer, status="paid"):
                paid_on = (claim.decided_on or claim.created_on).date()
                by_month.setdefault((paid_on.year, paid_on.month), []).append(claim)
            for (year, month), claims in sorted(by_month.items()):
                day = min(datetime.date(year, month, 1) + datetime.timedelta(days=self.random.randint(18, 27)), self.today - datetime.timedelta(days=1))
                total = sum((claim.amount_approved or 0 for claim in claims), Decimal("0"))
                FinanceModels.CompanyPayment.objects.create(
                    insurance_company=insurer, amount=total, narration=f"Remittance for {len(claims)} claims, {day:%B %Y}",
                    received_by=self.users["accounts"], received_on=self.at(day, 11))
        # M-Pesa payments waiting to be matched to a bill
        for minutes in (12, 35, 64, 110, 190):
            patient = self.random.choice(self.patient_list)
            FinanceModels.MpesaTransaction.objects.create(
                receipt_number=self.mpesa_receipt(), phone=patient.telnumber, payer_name=f"{patient.firstname} {patient.lastname}".upper(),
                account_reference=patient.patient_id if self.random.random() < 0.6 else "HOSPITAL",
                amount=Decimal(self.random.choice([500, 1000, 1500, 2300, 3450])),
                transacted_on=self.now - datetime.timedelta(minutes=minutes), status="unmatched", recorded_by=self.users["cashier"])
        # cashier shifts: closed for the last two weeks, open today
        for offset in range(14, -1, -1):
            day = self.today - datetime.timedelta(days=offset)
            for cashier in self.cashiers:
                opened = self.at(day, 7, 30)
                shift = FinanceModels.CashierShift.objects.create(cashier=cashier, opened_on=opened, opening_float=Decimal("5000"))
                if offset:
                    shift.closed_on = self.at(day, 19, 30)
                    shift.save(update_fields=["closed_on"])
                    variance = self.random.choices([0, 0, 0, -50, -200, 100], k=1)[0]
                    shift.counted_cash = shift.expected_cash + Decimal(variance)
                    shift.notes = "Short, reported to accounts" if variance < 0 else ""
                    shift.save(update_fields=["counted_cash", "notes"])
        # eTIMS: paid invoices go to KRA the same evening; today's and a handful of failures are left to deal with
        for invoice in FinanceModels.Invoice.objects.filter(status="paid", issued_on__lt=self.today):
            if self.random.random() < 0.004:
                continue
            failed = self.random.random() < 0.004
            FinanceModels.EtimsSubmission.objects.create(
                invoice=invoice, status="failed" if failed else "submitted",
                cu_invoice_number="" if failed else f"KRAMW{self.random.randint(10**10, 10**11 - 1)}",
                receipt_signature="" if failed else "".join(self.random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567") for _ in range(16)),
                error_message="Taxpayer PIN not recognised, check the KRA PIN" if failed else "",
                submitted_by=invoice.created_by, created_on=timezone.make_aware(datetime.datetime.combine(invoice.issued_on, datetime.time(20))))
        # refunds
        for invoice in FinanceModels.Invoice.objects.filter(status="paid", payments__isnull=False).order_by("?")[:3]:
            FinanceModels.Refund.objects.create(invoice=invoice, amount=self.money_value(min(invoice.total, Decimal("500"))),
                                                narration="Drug out of stock, refunded", refunded_by=self.users["accounts"],
                                                created_on=self.at(invoice.issued_on, 17))
        # monthly expenses
        for months_back in range(3, -1, -1):
            day = (self.today.replace(day=1) - datetime.timedelta(days=30 * months_back)).replace(day=5)
            if day > self.today:
                continue
            for name, amount in (("Staff Salaries", 1850000), ("Utility Bills", 86000), ("Hospital Internet", 15000), ("Drug Purchases", 420000)):
                FinanceModels.Expenditure.objects.create(category=self.expense_categories[name], amount=Decimal(amount) + self.random.randint(-5000, 5000),
                                                         narration=f"{name} for {day:%B %Y}", spent_on=day, recorded_by=self.users["accounts"])
        # banks
        kcb = FinanceModels.BankAccount.objects.create(
            bank_name="KCB Bank", branch="Moi Avenue", account_name="Demo Hospital Operations", account_number="1102345678",
            ledger_account=self.ledger["1210"], opening_balance=Decimal("2500000"), opened_on=self.today - datetime.timedelta(days=DAYS + 10))
        equity = FinanceModels.BankAccount.objects.create(
            bank_name="Equity Bank", branch="Kenyatta Avenue", account_name="Demo Hospital Collections", account_number="0170298765432",
            ledger_account=self.ledger["1220"], opening_balance=Decimal("800000"), opened_on=self.today - datetime.timedelta(days=DAYS + 10))
        for offset in range(DAYS, -1, -7):
            day = self.today - datetime.timedelta(days=offset)
            takings = FinanceModels.Payment.objects.filter(
                received_on__date__gt=day - datetime.timedelta(days=7), received_on__date__lte=day).values_list("amount", flat=True)
            total = sum(takings, Decimal("0"))
            if total:
                FinanceModels.BankTransaction.objects.create(account=equity, kind="deposit", amount=total, reference=f"DEP{day:%y%m%d}",
                                                             narration="Weekly banking of cash and M-Pesa takings", transacted_on=day,
                                                             recorded_by=self.users["accounts"])
        for expense in FinanceModels.Expenditure.objects.all():
            FinanceModels.BankTransaction.objects.create(account=kcb, kind="withdrawal", amount=expense.amount, reference=f"CHQ{expense.pk:05d}",
                                                         narration=expense.narration, transacted_on=expense.spent_on, recorded_by=self.users["accounts"])
        for payment in FinanceModels.CompanyPayment.objects.all():
            FinanceModels.BankTransaction.objects.create(account=kcb, kind="deposit", amount=payment.amount, reference=f"EFT{payment.pk:05d}",
                                                         narration=payment.narration, transacted_on=timezone.localtime(payment.received_on).date(),
                                                         recorded_by=self.users["accounts"])

    # ------------------------------------------------------------------ stores

    def stores(self):
        store, pharmacy = self.users["stores"], self.users["pharmacy"]
        drugs = list(self.drugs.values())
        plans = [("received", 40), ("received", 22), ("partial", 8), ("sent", 3), ("sent", 1), ("draft", 0), ("cancelled", 15)]
        for status, days_ago in plans:
            created = self.at(self.today - datetime.timedelta(days=days_ago + 2), 10)
            order = StoreModels.PurchaseOrder.objects.create(
                supplier=self.random.choice(self.suppliers), status=status, created_by=store, created_on=created,
                expected_on=self.today + datetime.timedelta(days=7 - days_ago), sent_on=created if status != "draft" else None,
                notes="Monthly restock")
            for drug in self.random.sample(drugs, self.random.randint(3, 6)):
                ordered = self.random.choice([500, 1000, 2000])
                received = {"received": ordered, "partial": ordered // 2}.get(status, 0)
                StoreModels.PurchaseOrderLine.objects.create(order=order, drug=drug, quantity_ordered=ordered,
                                                             unit_cost=self.money_value(drug.unit_price * Decimal("0.6")), quantity_received=received)
                if received:
                    DepartmentModels.StockBatch.objects.create(
                        drug=drug, supplier=order.supplier, quantity_received=received, quantity_remaining=received,
                        expiry_date=self.today + datetime.timedelta(days=self.random.randint(300, 720)), received_by=store,
                        received_on=self.at(self.today - datetime.timedelta(days=days_ago), 14))
        for department, status, days_ago in [("pharmacy", "pending", 0), ("wards", "pending", 0), ("laboratory", "issued", 2),
                                             ("theatre", "issued", 5), ("emergency", "partial", 3), ("dental", "rejected", 6),
                                             ("wards", "issued", 9)]:
            requested = self.at(self.today - datetime.timedelta(days=days_ago), 9, 30)
            requisition = StoreModels.Requisition.objects.create(
                department=department, status=status, requested_by=pharmacy if department == "pharmacy" else self.users["triage"],
                requested_on=requested, handled_by=store if status != "pending" else None,
                handled_on=self.later(requested, 60, 240) if status != "pending" else None,
                response="Duplicate of an earlier request" if status == "rejected" else "")
            for drug in self.random.sample(drugs, self.random.randint(2, 4)):
                wanted = self.random.choice([50, 100, 200])
                StoreModels.RequisitionLine.objects.create(
                    requisition=requisition, drug=drug, quantity_requested=wanted,
                    quantity_issued={"issued": wanted, "partial": wanted // 2}.get(status, 0))
        reasons = [("count", -12, "Monthly stock count"), ("damaged", -6, "Bottles broken in transit"),
                   ("returned", 20, "Returned unused from the ward"), ("expired", None, "Expired, sent for destruction")]
        batches = list(DepartmentModels.StockBatch.objects.filter(quantity_remaining__gt=30).order_by("?")[:4])
        for batch, (reason, change, notes) in zip(batches, reasons):
            change = change if change is not None else -min(batch.quantity_remaining, 25)
            adjustment = StoreModels.StockAdjustment.apply(batch, change, reason, store, notes)
            StoreModels.StockAdjustment.objects.filter(pk=adjustment.pk).update(
                adjusted_on=self.at(self.today - datetime.timedelta(days=self.random.randint(1, 20)), 16))
