from django.conf import settings

from apps.manager.navigation import current_page, menu_for


def application(request):
    menu = menu_for(request) if hasattr(request, "user") else []
    return {
        "application_name": settings.APPLICATION_NAME,
        "application_short_name": settings.APPLICATION_SHORT_NAME,
        "hospital_name": settings.HOSPITAL_NAME,
        "currency": settings.CURRENCY,
        "menu": menu,
        "current_page": current_page(menu),
    }
