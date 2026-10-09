import json
from functools import wraps

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import webauthn_util as wa
from .forms import ChangePinForm, PinLoginForm
from .models import WebauthnCredential

SESSION_WA_AUTH = 'mf_wa_auth'
SESSION_WA_NEXT = 'mf_wa_next'
SESSION_WA_REG = 'mf_wa_reg'


def _default_home(user):
    """Setelah login -> dasbor keuangan (home satu-satunya pengguna)."""
    return '/dashboard/'


def _safe_next(next_url, user):
    """Hanya izinkan URL internal (dimulai '/'); selain itu ke home default."""
    if next_url and next_url.startswith('/') and not next_url.startswith('//'):
        return next_url
    return _default_home(user)


def _is_owner(user):
    """Satu-satunya yang boleh memakai website ini: pemilik (role=owner)."""
    profile = getattr(user, 'profile', None)
    return bool(profile and profile.is_owner and user.is_active)


# ---------------------------------------------------------------------------
# Login / Logout (PIN + biometrik WebAuthn)
# ---------------------------------------------------------------------------

def login_view(request):
    if request.user.is_authenticated:
        return redirect(_default_home(request.user))

    error_msg = None
    next_url = request.GET.get('next', '')
    if request.GET.get('msg') == 'nonaktif':
        error_msg = 'Akun ini dinonaktifkan oleh pemilik situs. Hubungi pemilik untuk akses kembali.'
    elif request.GET.get('msg') == 'ditolak':
        error_msg = 'Akses ditolak — website ini khusus untuk pemilik.'

    if request.method == 'POST':
        form = PinLoginForm(data=request.POST)
        next_url = request.POST.get('next', '')
        if form.is_valid():
            username = form.cleaned_data['username']
            pin = form.cleaned_data['pin']
            user = authenticate(request, username=username, password=pin)
            if user is None:
                form.add_error(None, 'Nama pengguna atau PIN salah.')
            elif not user.is_active:
                form.add_error(None, 'Akun ini dinonaktifkan oleh pemilik situs.')
            elif not _is_owner(user):
                form.add_error(None, 'Akses ditolak — website ini khusus untuk pemilik.')
            elif WebauthnCredential.objects.filter(user=user).exists():
                # 2FA: PIN benar, tapi biometrik wajib. Belum login penuh —
                # simpan state di sesi, lalu minta sidik jari/face di /verify/.
                options_json, challenge_b64 = wa.authentication_options_for(user)
                request.session[SESSION_WA_AUTH] = {
                    'options': options_json,
                    'challenge': challenge_b64,
                    'user_id': user.pk,
                }
                request.session[SESSION_WA_NEXT] = _safe_next(next_url, user)
                return redirect('accounts:webauthn_verify')
            else:
                login(request, user)
                return redirect(_safe_next(next_url, user))
        return render(request, 'accounts/login.html', {
            'form': form,
            'next': next_url,
            'error_msg': error_msg,
        })

    form = PinLoginForm()
    return render(request, 'accounts/login.html', {
        'form': form,
        'next': next_url,
        'error_msg': error_msg,
    })


def logout_view(request):
    auth_logout(request)
    return redirect('accounts:login')


def webauthn_verify(request):
    """Langkah 2FA: verifikasi biometrik setelah PIN benar."""
    state = request.session.get(SESSION_WA_AUTH)
    next_url = request.session.get(SESSION_WA_NEXT, '')

    def _clear_state():
        request.session.pop(SESSION_WA_AUTH, None)
        request.session.pop(SESSION_WA_NEXT, None)

    user = (
        User.objects.filter(pk=state.get('user_id')).first() if state else None
    )
    if not state or not user or not user.is_active:
        _clear_state()
        return redirect('/login/?msg=nonaktif' if state else '/login/')
    if not _is_owner(user):
        _clear_state()
        return redirect('/login/?msg=ditolak')

    if request.method == 'POST':
        assertion = None
        try:
            assertion = json.loads(request.body or b'{}').get('assertion')
        except ValueError:
            assertion = None

        error = None
        try:
            if not wa.enabled():
                raise ValueError('Biometrik belum dikonfigurasi di server.')
            wa.verify_assertion(assertion, wa.b64u_to_bytes(state['challenge']), user)
        except Exception:
            error = 'Verifikasi biometrik gagal. Silakan coba lagi.'

        if error:
            # Generate challenge baru lalu tampilkan ulang halaman verifikasi.
            options_json, challenge_b64 = wa.authentication_options_for(user)
            request.session[SESSION_WA_AUTH] = {
                'options': options_json,
                'challenge': challenge_b64,
                'user_id': user.pk,
            }
            return render(request, 'accounts/verify.html', {
                'wa_options': json.loads(request.session[SESSION_WA_AUTH]['options']),
                'username': user.username,
                'error': error,
            })

        _clear_state()
        login(request, user)
        return JsonResponse({'ok': True, 'redirect': _safe_next(next_url, user)})

    return render(request, 'accounts/verify.html', {
        'wa_options': json.loads(state['options']),
        'username': user.username,
        'error': None,
    })


# ---------------------------------------------------------------------------
# Halaman Akun & Keamanan
# ---------------------------------------------------------------------------

def _require_owner(view_func):
    """Halaman akun: khusus pemilik — satu-satunya pengguna website ini."""
    @wraps(view_func)
    @login_required(login_url='/login/')
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_active or not _is_owner(user):
            auth_logout(request)
            msg = 'nonaktif' if not user.is_active else 'ditolak'
            return redirect('/login/?msg=' + msg)
        return view_func(request, *args, **kwargs)

    return wrapper


@_require_owner
def account(request):
    from finance import telegram_bot

    context = {
        'mf_page': 'account',
        'change_form': ChangePinForm(user=request.user),
        'creds': list(WebauthnCredential.objects.filter(user=request.user)),
        'wa_enabled': wa.enabled(),
        'tg': telegram_bot.status_payload(),
    }
    return render(request, 'accounts/account.html', context)


@_require_owner
@require_POST
def change_pin(request):
    form = ChangePinForm(user=request.user, data=request.POST)
    if form.is_valid():
        request.user.set_password(form.cleaned_data['new_pin'])
        request.user.save(update_fields=['password'])
        # Refresh hash sesi agar tetap login setelah PIN berganti.
        from django.contrib.auth import update_session_auth_hash

        update_session_auth_hash(request, request.user)
        messages.success(request, 'PIN berhasil diganti.')
    return redirect('accounts:account')


# ---------------------------------------------------------------------------
# WebAuthn: pendaftaran & penghapusan kredensial (di halaman Akun)
# ---------------------------------------------------------------------------

@_require_owner
@require_POST
def webauthn_register_start(request):
    if not wa.enabled():
        return JsonResponse(
            {'ok': False, 'message': 'Biometrik belum dikonfigurasi di server.'},
            status=400,
        )
    try:
        options_json, challenge_b64 = wa.registration_options_for(request.user)
    except Exception:
        return JsonResponse(
            {'ok': False, 'message': 'Gagal menyiapkan pendaftaran. Coba lagi.'},
            status=500,
        )
    request.session[SESSION_WA_REG] = {
        'options': options_json,
        'challenge': challenge_b64,
    }
    return JsonResponse({'ok': True, 'publicKey': json.loads(options_json)})


@_require_owner
@require_POST
def webauthn_register_finish(request):
    state = request.session.get(SESSION_WA_REG)
    if not state:
        return JsonResponse(
            {'ok': False, 'message': 'Sesi pendaftaran sudah habis. Silakan ulangi.'},
            status=400,
        )
    credential = None
    try:
        credential = json.loads(request.body or b'{}').get('credential')
    except ValueError:
        credential = None
    try:
        result = wa.verify_registration(credential, wa.b64u_to_bytes(state['challenge']))
    except Exception:
        request.session.pop(SESSION_WA_REG, None)
        return JsonResponse(
            {'ok': False, 'message': 'Pendaftaran tidak valid. Silakan coba lagi.'},
            status=400,
        )
    request.session.pop(SESSION_WA_REG, None)
    WebauthnCredential.objects.create(
        user=request.user,
        credential_id=wa.b64u(result.credential_id),
        public_key=result.credential_public_key,
        sign_count=result.sign_count,
        aaguid=result.aaguid or '',
        name='Autentikator perangkat',
    )
    return JsonResponse({
        'ok': True,
        'message': 'Biometrik berhasil didaftarkan. Login berikutnya akan meminta sidik jari.',
    })


@_require_owner
@require_POST
def webauthn_credential_delete(request, pk):
    cred = get_object_or_404(WebauthnCredential, pk=pk, user=request.user)
    cred.delete()
    return JsonResponse({'ok': True, 'message': 'Kredensial biometrik dihapus.'})
