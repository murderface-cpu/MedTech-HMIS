"""The audit trail: every change to a hospital record, and every sign-in, written to AuditEntry.

The middleware remembers who is making the request; model signals then record the change with
the fields that differ. Seeding and tests can switch recording off with `audit.paused()`.
"""
import contextlib
import contextvars
import datetime
import decimal

from django.contrib.auth import signals as auth_signals
from django.db.models import signals

_actor = contextvars.ContextVar("audit_actor", default=None)
_paused = contextvars.ContextVar("audit_paused", default=False)

AUDITED_APPS = {"manager", "patients", "doctor", "finance", "lab", "departments", "clinical", "stores", "auth"}
# models whose changes are bookkeeping, not decisions someone made
SKIPPED_MODELS = {"manager.auditentry", "auth.permission", "sessions.session", "contenttypes.contenttype"}
SKIPPED_FIELDS = {"updated_on", "password", "last_login", "slug"}


class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _actor.set(request)
        try:
            return self.get_response(request)
        finally:
            _actor.reset(token)


@contextlib.contextmanager
def paused():
    token = _paused.set(True)
    try:
        yield
    finally:
        _paused.reset(token)


def client_ip(request):
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")) or None


def current_user():
    request = _actor.get()
    user = getattr(request, "user", None)
    return user if user is not None and user.is_authenticated else None


def label_of(sender):
    return f"{sender._meta.app_label}.{sender._meta.model_name}"


def is_audited(sender):
    # historical models (migrations) live in the "__fake__" module and are never audited
    if sender.__module__ == "__fake__":
        return False
    return sender._meta.app_label in AUDITED_APPS and label_of(sender) not in SKIPPED_MODELS


def plain(value):
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return str(value)
    if hasattr(value, "name") and hasattr(value, "url"):  # files
        return value.name or ""
    return value if isinstance(value, (str, int, float, bool, type(None))) else str(value)


def snapshot(instance):
    data = {}
    for field in instance._meta.concrete_fields:
        if field.name in SKIPPED_FIELDS:
            continue
        data[field.verbose_name.capitalize() if isinstance(field.verbose_name, str) else str(field.verbose_name).capitalize()] = plain(getattr(instance, field.attname))
    return data


def write(action, *, model="", object_id="", summary="", changes=None, user=None, request=None):
    from apps.manager.models import AuditEntry

    request = request or _actor.get()
    user = user or current_user()
    AuditEntry.objects.create(
        user=user, username=user.get_username() if user else "", action=action, model=model,
        object_id=str(object_id or ""), summary=str(summary)[:256], changes=changes or {}, ip_address=client_ip(request),
    )


def record_label(sender):
    return str(sender._meta.verbose_name).capitalize()


def on_pre_save(sender, instance, raw=False, **kwargs):
    if raw or _paused.get() or not is_audited(sender) or not instance.pk:
        return
    previous = sender._default_manager.filter(pk=instance.pk).first()
    instance._audit_before = snapshot(previous) if previous is not None else None


def on_post_save(sender, instance, created, raw=False, **kwargs):
    if raw or _paused.get() or not is_audited(sender):
        return
    after = snapshot(instance)
    if created:
        write("create", model=record_label(sender), object_id=instance.pk, summary=instance, changes={"after": after})
        return
    before = getattr(instance, "_audit_before", None) or {}
    changed = {key: [before.get(key), value] for key, value in after.items() if before.get(key) != value}
    if changed:
        write("update", model=record_label(sender), object_id=instance.pk, summary=instance, changes={"changed": changed})


def on_post_delete(sender, instance, **kwargs):
    if _paused.get() or not is_audited(sender):
        return
    write("delete", model=record_label(sender), object_id=instance.pk, summary=instance, changes={"before": snapshot(instance)})


def on_sign_in(sender, request, user, **kwargs):
    if not _paused.get():
        write("sign_in", model="Account", object_id=user.pk, summary=f"{user.get_username()} signed in", user=user, request=request)


def on_sign_out(sender, request, user, **kwargs):
    if not _paused.get() and user is not None:
        write("sign_out", model="Account", object_id=user.pk, summary=f"{user.get_username()} signed out", user=user, request=request)


def on_sign_in_failed(sender, credentials, request=None, **kwargs):
    if not _paused.get():
        username = credentials.get("username", "")
        write("sign_in_failed", model="Account", summary=f"Failed sign-in as '{username}'"[:256], request=request)


def connect():
    signals.pre_save.connect(on_pre_save, dispatch_uid="audit_pre_save")
    signals.post_save.connect(on_post_save, dispatch_uid="audit_post_save")
    signals.post_delete.connect(on_post_delete, dispatch_uid="audit_post_delete")
    auth_signals.user_logged_in.connect(on_sign_in, dispatch_uid="audit_sign_in")
    auth_signals.user_logged_out.connect(on_sign_out, dispatch_uid="audit_sign_out")
    auth_signals.user_login_failed.connect(on_sign_in_failed, dispatch_uid="audit_sign_in_failed")
