from django.contrib import admin
from django.apps import apps

# every model of the app is editable from the Django admin
for model in apps.get_app_config("finance").get_models():
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass
