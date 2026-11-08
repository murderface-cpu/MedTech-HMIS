import datetime

from django.conf import settings
from django.utils import timezone


def hospital_abbreviation():
    return "".join(word[0].upper() for word in settings.HOSPITAL_NAME.split() if word)


def build_code(prefix, number):
    """Readable, unique record number such as FLH-P-000012 (number is the primary key)."""
    parts = [part for part in (hospital_abbreviation(), prefix) if part]
    return f"{'-'.join(parts)}-{number:06d}"


def assign_code(instance, field, prefix):
    """Fill `field` from the primary key once the instance has been saved."""
    if getattr(instance, field):
        return
    code = build_code(prefix, instance.pk)
    setattr(instance, field, code)
    type(instance).objects.filter(pk=instance.pk).update(**{field: code})


def age_from_date_of_birth(date_of_birth):
    if isinstance(date_of_birth, datetime.datetime):
        date_of_birth = timezone.localtime(date_of_birth).date() if timezone.is_aware(date_of_birth) else date_of_birth.date()
    today = timezone.localdate()
    return today.year - date_of_birth.year - ((today.month, today.day) < (date_of_birth.month, date_of_birth.day))


def date_of_birth_from_age(age):
    today = timezone.localdate()
    return timezone.make_aware(datetime.datetime(today.year - int(age), 1, 1))
