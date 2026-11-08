from django.db import migrations

BILLING_TYPES = (("Cash", "cash"), ("Insurance", "insurance"), ("Account", "account"))
EXPENSE_CATEGORIES = ("Utility Bills", "Hospital Internet", "Staff Salaries", "Drug Purchases")


def seed(apps, schema_editor):
    BillingType = apps.get_model("finance", "BillingType")
    for name, kind in BILLING_TYPES:
        billing_type = BillingType.objects.filter(name__iexact=name).first()
        if billing_type:
            billing_type.kind = kind
            billing_type.save(update_fields=["kind"])
        else:
            BillingType.objects.create(name=name, kind=kind)
    ExpenseCategory = apps.get_model("finance", "ExpenseCategory")
    for name in EXPENSE_CATEGORIES:
        ExpenseCategory.objects.get_or_create(name=name)


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0002_accountcompany_expensecategory_insurancecompany_and_more"),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
