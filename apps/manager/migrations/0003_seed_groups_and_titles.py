from django.db import migrations

from apps.manager.access import MODULES

TITLES = (
    ("Anaesthetist", "anaesthetist"),
    ("Anaesthesiologist", "anaesthetist"),
    ("Cardiologist", "doctor"),
    ("Doctor", "doctor"),
    ("Lab Technologist", "other"),
    ("Nurse", "nurse"),
    ("Pathologist", "doctor"),
    ("Pharmacist", "other"),
    ("Radiologist", "doctor"),
    ("Therapist", "other"),
    ("Receptionist", "other"),
)


def seed(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for module in MODULES:
        Group.objects.get_or_create(name=module)
    StaffTitle = apps.get_model("manager", "StaffTitle")
    for name, kind in TITLES:
        StaffTitle.objects.get_or_create(name=name, defaults={"kind": kind})


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("manager", "0002_stafftitle_staff"),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
