"""Kenya Ministry of Health returns: MOH 705A/B outpatient morbidity and MOH 717 service workload.

Diagnoses are recorded as free text, so each is placed in a 705 condition by keywords, in the
order below (the first match wins). Anything that matches none is counted as All other diseases.
"""
import calendar
import datetime

from django.db.models import Count, Min
from django.utils import timezone

from apps.clinical import models as ClinicalModels
from apps.departments import models as DepartmentModels
from apps.lab import models as LabModels
from apps.patients import models as PatientModels
from apps.reports.metrics import local_bounds

CONDITIONS = (
    ("Diarrhoea", ("diarrh", "gastroenteritis", "loose stool")),
    ("Tuberculosis", ("tuberculosis", " tb", "ptb")),
    ("Dysentery (bloody diarrhoea)", ("dysentery", "bloody diarr")),
    ("Cholera", ("cholera",)),
    ("Meningitis", ("meningitis",)),
    ("Measles", ("measles",)),
    ("Chicken pox", ("chicken pox", "chickenpox", "varicella")),
    ("Confirmed malaria", ("confirmed malaria", "malaria (confirmed", "malaria, confirmed", "bs positive", "mrdt positive")),
    ("Malaria in pregnancy", ("malaria in pregnancy",)),
    ("Suspected malaria", ("malaria",)),
    ("Urinary tract infection", ("urinary tract", "uti", "cystitis", "pyelonephritis")),
    ("Typhoid fever", ("typhoid", "enteric fever")),
    ("Intestinal worms", ("worm", "helminth", "ascari", "hookworm")),
    ("Malnutrition", ("malnutrition", "kwashiorkor", "marasmus", "wasting")),
    ("Anaemia", ("anaemia", "anemia")),
    ("Eye infections", ("conjunctivitis", "eye infection")),
    ("Ear infections", ("otitis", "ear infection")),
    ("Pneumonia", ("pneumonia",)),
    ("Upper respiratory tract infections", ("upper respiratory", "urti", "pharyngitis", "tonsillitis", "common cold", "rhinitis", "sinusitis")),
    ("Other lower respiratory tract infections", ("bronchitis", "bronchiolitis", "lower respiratory", "lrti")),
    ("Asthma", ("asthma",)),
    ("Hypertension", ("hypertension", "high blood pressure")),
    ("Diabetes", ("diabetes", "diabetic")),
    ("Mental disorders", ("depression", "psychosis", "anxiety", "mental", "schizophren", "bipolar")),
    ("Dental disorders", ("dental", "caries", "tooth", "gingivitis")),
    ("Skin diseases", ("dermatitis", "eczema", "skin", "scabies", "tinea", "fungal infection", "cellulitis", "abscess")),
    ("Sexually transmitted infections", ("sexually transmitted", "sti", "gonorr", "syphilis", "chlamydia")),
    ("Arthritis and joint pains", ("arthritis", "joint pain", "back pain", "gout")),
    ("Poisoning", ("poisoning",)),
    ("Road traffic injuries", ("road traffic", "rta", "motorcycle accident", "car accident")),
    ("Burns", ("burn",)),
    ("Dog bites", ("dog bite",)),
    ("Snake bites", ("snake bite", "snakebite")),
    ("Other injuries", ("injury", "fracture", "wound", "laceration", "sprain", "contusion")),
)
OTHER = "All other diseases"


def classify(text):
    text = f" {(text or '').lower()} "
    for condition, keywords in CONDITIONS:
        if any(keyword in text for keyword in keywords):
            return condition
    return OTHER


def age_on(patient, day):
    if patient.date_of_birth:
        birth = timezone.localtime(patient.date_of_birth).date() if timezone.is_aware(patient.date_of_birth) else patient.date_of_birth.date()
        return day.year - birth.year - ((day.month, day.day) < (birth.month, birth.day))
    return patient.age or 0


def month_bounds(month):
    last = calendar.monthrange(month.year, month.month)[1]
    return month, month.replace(day=last)


def morbidity(month, under_five):
    start, end = month_bounds(month)
    low, high = local_bounds(start, end)
    days = list(range(1, end.day + 1))
    names = [condition for condition, _ in CONDITIONS] + [OTHER]
    grid = {name: [0] * len(days) for name in names}
    diagnoses = PatientModels.Diagnosis.objects.filter(created_on__gte=low, created_on__lt=high).select_related("visit__patient")
    for diagnosis in diagnoses:
        day = timezone.localtime(diagnosis.created_on).date()
        if (age_on(diagnosis.visit.patient, day) < 5) != under_five:
            continue
        grid[classify(diagnosis.diagnosis)][day.day - 1] += 1
    rows = [{"condition": name, "counts": grid[name], "total": sum(grid[name])} for name in names]
    day_totals = [sum(row["counts"][index] for row in rows) for index in range(len(days))]
    return {"days": days, "rows": rows, "day_totals": day_totals, "total": sum(day_totals),
            "label": "MOH 705A, under 5 years" if under_five else "MOH 705B, 5 years and over"}


def workload_717(month):
    start, end = month_bounds(month)
    low, high = local_bounds(start, end)
    visits = list(PatientModels.Visit.objects.filter(visit_date__gte=low, visit_date__lt=high).select_related("patient"))
    first_visit = dict(PatientModels.Visit.objects.filter(patient__in={visit.patient_id for visit in visits})
                       .values_list("patient").annotate(first=Min("id")))
    attendance = {"new_under": 0, "new_over": 0, "re_under": 0, "re_over": 0}
    for visit in visits:
        under = age_on(visit.patient, timezone.localtime(visit.visit_date).date()) < 5
        new = first_visit.get(visit.patient_id) == visit.pk
        attendance[f"{'new' if new else 're'}_{'under' if under else 'over'}"] += 1

    admissions = ClinicalModels.Admission.objects
    discharged = admissions.filter(discharged_on__gte=low, discharged_on__lt=high)
    bed_days = ClinicalModels.BedCharge.objects.filter(charge_date__gte=start, charge_date__lte=end).count()
    beds = ClinicalModels.Bed.objects.filter(ward__is_active=True).exclude(status="out_of_service").count()
    stays = [admission.days_admitted for admission in discharged.filter(status="discharged")]
    occupancy = round(bed_days * 100 / (beds * (end - start).days + beds)) if beds else 0
    emergency = ClinicalModels.EmergencyCase.objects.filter(arrived_on__gte=low, arrived_on__lt=high)
    lab_tests = LabModels.AssignedTest.objects.filter(request__created_on__gte=low, request__created_on__lt=high)
    exams = DepartmentModels.DepartmentRequest.objects.filter(reported_on__gte=low, reported_on__lt=high, status="completed")

    return [
        {"title": "Outpatient attendances", "rows": [
            ("New attendances, under 5 years", attendance["new_under"]),
            ("New attendances, 5 years and over", attendance["new_over"]),
            ("Re-attendances, under 5 years", attendance["re_under"]),
            ("Re-attendances, 5 years and over", attendance["re_over"]),
            ("Total outpatient attendances", len(visits)),
        ]},
        {"title": "Casualty and emergency", "rows": [
            ("Emergency attendances", emergency.count()),
            ("Seen as emergency or very urgent", emergency.filter(acuity__in=("red", "orange")).count()),
            ("Admitted from emergency", emergency.filter(status="admitted").count()),
            ("Deaths in emergency", emergency.filter(status="died").count()),
        ]},
        {"title": "Inpatient services", "rows": [
            ("Admissions", admissions.filter(admitted_on__gte=low, admitted_on__lt=high).count()),
            ("Discharges", discharged.exclude(discharge_type="died").count()),
            ("Inpatient deaths", discharged.filter(discharge_type="died").count()),
            ("Referred out", discharged.filter(discharge_type="referred").count()),
            ("Bed days", bed_days),
            ("Average length of stay (days)", round(sum(stays) / len(stays), 1) if stays else 0),
            ("Bed occupancy (%)", occupancy),
        ]},
        {"title": "Laboratory", "rows": [
            ("Tests requested", lab_tests.count()),
            ("Tests reported", lab_tests.filter(request__handled=True).count()),
            ("Samples rejected", LabModels.Sample.objects.filter(collected_on__gte=low, collected_on__lt=high, status="rejected").count()),
        ]},
        {"title": "Imaging and cardiology", "rows": [
            ("Radiology examinations reported", exams.filter(department="radiology").count()),
            ("Cardiology examinations reported", exams.filter(department="cardiology").count()),
        ]},
        {"title": "Pharmacy", "rows": [
            ("Prescriptions dispensed", DepartmentModels.Prescription.objects.filter(issued_on__gte=low, issued_on__lt=high).count()),
        ]},
        {"title": "Theatre and dental", "rows": [
            ("Operations done", DepartmentModels.TheatreBooking.objects.filter(scheduled_for__gte=low, scheduled_for__lt=high, status="completed").count()),
            ("Dental procedures", DepartmentModels.DentalProcedure.objects.filter(performed_on__gte=low, performed_on__lt=high).count()),
        ]},
    ]
