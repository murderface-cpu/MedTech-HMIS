from django.apps import AppConfig


class ManagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.manager'

    def ready(self):
        from apps.manager import audit

        audit.connect()
