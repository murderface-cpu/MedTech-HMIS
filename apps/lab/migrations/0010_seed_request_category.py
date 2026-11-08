from django.db import migrations


def seed(apps, schema_editor):
    RequestCategory = apps.get_model("lab", "RequestCategory")
    if not RequestCategory.objects.filter(name__iexact="Laboratory").exists():
        RequestCategory.objects.create(name="Laboratory")


class Migration(migrations.Migration):

    dependencies = [
        ("lab", "0009_subtest_lower_limit_subtest_normal_result_and_more"),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
