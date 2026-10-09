"""Hapus semua kredensial biometrik milik seorang user (pemulihan lockout).

Jika HP hilang / kredensial rusak dan user tidak bisa login dengan biometrik,
perintah ini menghapus kredensialnya sehingga login kembali memakai PIN saja
(user bisa mendaftarkan perangkat baru dari halaman Akun & Keamanan).

Contoh:
    python manage.py webauthn_reset anandaazhar
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from accounts.models import WebauthnCredential


class Command(BaseCommand):
    help = 'Hapus seluruh kredensial biometrik (WebAuthn) milik seorang user.'

    def add_arguments(self, parser):
        parser.add_argument('username')

    def handle(self, *args, **opts):
        user = User.objects.filter(username=opts['username']).first()
        if not user:
            self.stderr.write(self.style.ERROR(f'User "{opts["username"]}" tidak ditemukan.'))
            return
        count, _ = WebauthnCredential.objects.filter(user=user).delete()
        self.stdout.write(self.style.SUCCESS(
            f'{count} kredensial biometrik dihapus untuk "{user.username}". '
            'Login berikutnya cukup dengan PIN.'
        ))
