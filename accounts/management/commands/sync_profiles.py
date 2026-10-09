"""Pastikan semua user punya Profile (untuk user yang dibuat sebelum app accounts)."""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from accounts.models import Profile


class Command(BaseCommand):
    help = 'Buat Profile (role member) untuk user yang belum memilikinya.'

    def handle(self, *args, **opts):
        created = 0
        for user in User.objects.all():
            try:
                user.profile
            except Profile.DoesNotExist:
                Profile.objects.create(user=user)
                created += 1
        self.stdout.write(self.style.SUCCESS(
            f'Selamat — {created} profil baru dibuat. Semua user kini punya Profile.'
        ))
