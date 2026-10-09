from django.conf import settings
from django.db import models


class Profile(models.Model):
    """Profil tambahan untuk setiap user.

    Website ini hanya dipakai satu orang: pemilik (role=owner).
    Akun selain pemilik tidak bisa login/mengakses halaman mana pun.
    """

    class Role(models.TextChoices):
        OWNER = 'owner', 'Pemilik'
        MEMBER = 'member', 'Member'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    role = models.CharField(
        'peran',
        max_length=16,
        choices=Role.choices,
        default=Role.MEMBER,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Profil pengguna'
        verbose_name_plural = 'Profil pengguna'

    def __str__(self):
        return f'Profil {self.user.username}'

    @property
    def is_owner(self):
        return self.role == self.Role.OWNER


class WebauthnCredential(models.Model):
    """Kredensial biometrik (WebAuthn / passkey) milik seorang user.

    Kunci privat TIDAK pernah disimpan di server — ia tertanam di perangkat
    (Secure Enclave/TEE di HP) dan terkunci oleh biometrik perangkat itu.
    Server hanya menyimpan kunci publik + penanda kredensial. Akibatnya,
    mengetahui username + PIN orang lain TIDAK cukup untuk login:
    tandatangan biometrik hanya bisa dibuat oleh perangkat milik user itu.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='webauthn_credentials',
    )
    # Base64url dari ID kredensial — sama persis dengan `id`/`rawId` di browser.
    credential_id = models.CharField(max_length=255, unique=True)
    # Kunci publik (byte mentah) — dipakai untuk memverifikasi tandatangan.
    public_key = models.BinaryField()
    # Sign counter autentikator (deteksi clonning).
    sign_count = models.IntegerField(default=0)
    aaguid = models.CharField(max_length=64, blank=True, default='')
    name = models.CharField('nama', max_length=120, default='Autentikator perangkat')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at',)
        verbose_name = 'Kredensial biometrik'
        verbose_name_plural = 'Kredensial biometrik'

    def __str__(self):
        return f'{self.user.username} — {self.name}'
