"""Template helpers shared by every module: status tones, money and compact figures."""
from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()

# Every status value maps to one of five tones; the pill always shows the status label too.
TONES = {
    "warn": {"pending", "scheduled", "booked", "waiting", "awaiting", "draft", "open", "collected", "unmatched",
             "submitted", "sent", "partial", "cleaning", "in_analysis", "received_in_lab", "not_submitted"},
    "ok": {"paid", "completed", "checked_in", "admitted", "issued", "received", "matched", "approved", "available",
           "closed", "discharged", "accepted", "active"},
    "bad": {"cancelled", "rejected", "failed", "missed", "died", "out_of_service", "expired", "absconded"},
    "info": {"in_treatment", "occupied", "transferred", "referred"},
}


@register.filter
def tone(status):
    status = str(status or "").lower()
    for name, values in TONES.items():
        if status in values:
            return f"tone-{name}"
    return "tone-neutral"


def _decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


@register.filter
def money(value):
    """1234.5 -> 1,234.50"""
    number = _decimal(value)
    if number is None:
        return ""
    return f"{number:,.2f}"


@register.filter
def whole(value):
    """1234.5 -> 1,235"""
    number = _decimal(value)
    if number is None:
        return ""
    return f"{number:,.0f}"


@register.filter
def compact(value):
    """Auto-compact a figure: 1,284 / 12.9K / 4.2M."""
    number = _decimal(value)
    if number is None:
        return ""
    size = abs(number)
    if size >= 1_000_000:
        return f"{number / 1_000_000:.1f}M".replace(".0M", "M")
    if size >= 10_000:
        return f"{number / 1_000:.1f}K".replace(".0K", "K")
    return f"{number:,.0f}"


@register.filter
def percent_of(value, whole_value):
    number, base = _decimal(value), _decimal(whole_value)
    if not number or not base:
        return 0
    return round(number * 100 / base, 1)


@register.filter
def get_item(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None
