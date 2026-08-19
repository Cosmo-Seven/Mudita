from django.apps import AppConfig


# core/apps.py
class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        import core.signals