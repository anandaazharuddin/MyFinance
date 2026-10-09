"""Jembatan ke pustaka `webauthn` (duo-labs) untuk MyFinance.

Alur:
1. PENDAFTARAN (user sudah login, di HP-nya):
   - registration_options_for()  -> opsi dikirim ke browser (navigator.credentials.create)
   - verify_registration()       -> server memverifikasi, menyimpan kunci publik
2. LOGIN 2FA (PIN berhasil, lalu biometrik):
   - authentication_options_for() -> opsi dikirim ke browser (navigator.credentials.get)
   - verify_assertion()           -> server memverifikasi tandatangan biometrik

Kunci privat tidak pernah meninggalkan perangkat (Secure Enclave/TEE),
sehingga kredensial terikat pada biometrik HP milik user itu sendiri.
"""

import base64

from django.conf import settings

from .models import WebauthnCredential


def b64u(data: bytes) -> str:
    """Base64url tanpa padding (konvensi WebAuthn di browser)."""
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def b64u_to_bytes(value: str) -> bytes:
    from webauthn import base64url_to_bytes

    return base64url_to_bytes(value)


def enabled() -> bool:
    """Biometrik aktif hanya jika rp_id & origins tersedia.

    Di produksi: set env WEBAUTHN_RP_ID=domain-kamu dan
    WEBAUTHN_ORIGINS=https://domain-kamu (HTTPS wajib untuk WebAuthn).
    """
    return bool(settings.WEBAUTHN_ENABLED)


def _descriptor(cred: WebauthnCredential):
    from webauthn.helpers import structs as st

    return st.PublicKeyCredentialDescriptor(
        id=b64u_to_bytes(cred.credential_id),
        type=st.PublicKeyCredentialType.PUBLIC_KEY,
    )


def registration_options_for(user):
    """Buat opsi pendaftaran untuk user (sudah login).

    Return: (json_options siap jadi `publicKey` browser, challenge base64url).
    """
    from webauthn import generate_registration_options, options_to_json
    from webauthn.helpers import structs as st

    options = generate_registration_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        rp_name=settings.WEBAUTHN_RP_NAME,
        user_name=user.username,
        user_display_name=user.get_full_name() or user.username,
        user_id=f'myfinance-user-{user.pk}'.encode('utf-8'),
        attestation=st.AttestationConveyancePreference.NONE,
        authenticator_selection=st.AuthenticatorSelectionCriteria(
            authenticator_attachment=st.AuthenticatorAttachment.PLATFORM,
            user_verification=st.UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=[
            _descriptor(c) for c in WebauthnCredential.objects.filter(user=user)
        ],
    )
    return options_to_json(options), b64u(options.challenge)


def authentication_options_for(user):
    """Buat opsi autentikasi (login 2FA) untuk user.

    Return: (json_options siap jadi `publicKey` browser, challenge base64url).
    """
    from webauthn import generate_authentication_options, options_to_json
    from webauthn.helpers import structs as st

    options = generate_authentication_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        allow_credentials=[
            _descriptor(c) for c in WebauthnCredential.objects.filter(user=user)
        ],
        user_verification=st.UserVerificationRequirement.REQUIRED,
    )
    return options_to_json(options), b64u(options.challenge)


def verify_registration(credential, challenge):
    """Verifikasi hasil pendaftaran dari browser.

    `credential` = dict JSON mentah dari browser (base64url string),
    `challenge`  = bytes challenge yang dikirim sebelumnya.
    """
    from webauthn import verify_registration_response

    return verify_registration_response(
        credential=credential,
        expected_challenge=challenge,
        expected_rp_id=settings.WEBAUTHN_RP_ID,
        expected_origin=settings.WEBAUTHN_ORIGINS,
        require_user_presence=True,
        require_user_verification=True,
    )


def verify_assertion(assertion, challenge, user):
    """Verifikasi tandatangan biometrik saat login.

    `assertion`  = dict JSON mentah dari browser,
    `challenge`  = bytes challenge yang dikirim sebelumnya,
    `user`       = user yang sedang diverifikasi (belum login penuh).
    """
    from webauthn import verify_authentication_response

    assert_ = assertion or {}
    cred_id = assert_.get('id') or assert_.get('rawId') or ''
    cred = WebauthnCredential.objects.filter(user=user, credential_id=cred_id).first()
    if cred is None:
        raise ValueError('Kredensial tidak terdaftar untuk akun ini.')

    result = verify_authentication_response(
        credential=assertion,
        expected_challenge=challenge,
        expected_rp_id=settings.WEBAUTHN_RP_ID,
        expected_origin=settings.WEBAUTHN_ORIGINS,
        credential_public_key=cred.public_key,
        credential_current_sign_count=cred.sign_count,
        require_user_verification=True,
    )
    if result.new_sign_count > cred.sign_count:
        cred.sign_count = result.new_sign_count
        cred.save(update_fields=['sign_count'])
    return cred
