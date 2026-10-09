"""Buat/astikan akun PEMILIK (superuser) dengan PIN 6 digit.

Contoh:
    python manage.py create_owner
    python manage.py create_owner anandaazhar 754518
"""

import re

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from accounts.models import Profile


class Command(BaseCommand):
    help = 'Buat (atau pastikan) akun pemilik: superuser + role owner + PIN 6 digit.'

    def add_arguments(self, parser):
        parser.add_argument('username', nargs='?', default='anandaazhar')
        parser.add_argument('pin', nargs='?', default='754518')

    def handle(self, *args, **opts):
        username = opts['username']
        pin = opts['pin']
        if not re.fullmatch(r'\d{6}', pin):
            self.stderr.write(self.style.ERROR('PIN harus tepat 6 digit angka.'))
            return

        user, created = User.objects.get_or_create(
            username=username,
            defaults={'is_staff': True, 'is_superuser': True, 'is_active': True},
        )
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(pin)
        user.save()

        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = Profile.Role.OWNER
        profile.save(update_fields=['role'])

        action = 'dibuat' if created else 'diperbarui'
        self.stdout.write(self.style.SUCCESS(
            f'Owner "{username}" {action} — superuser aktif, PIN tersimpan (ter-hash).'
        ))
