from django.apps import apps
from django.contrib import admin

# every model of the app is editable from the Django admin
for model in apps.get_app_config("clinical").get_models():
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass
