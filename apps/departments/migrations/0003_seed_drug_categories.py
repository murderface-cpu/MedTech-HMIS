from django.db import migrations

DRUG_CATEGORIES = ("Tablet", "Syrup", "Injectable", "Cream")


def seed(apps, schema_editor):
    DrugCategory = apps.get_model("departments", "DrugCategory")
    for name in DRUG_CATEGORIES:
        DrugCategory.objects.get_or_create(name=name)


class Migration(migrations.Migration):

    dependencies = [
        ("departments", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
