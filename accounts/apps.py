from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    verbose_name = 'Akun & Keamanan'

    def ready(self):
        from . import signals  # noqa: F401  (pasang signal penciptaan Profile)
