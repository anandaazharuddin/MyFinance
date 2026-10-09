from datetime import date

from django.conf import settings

from .models import Category, Transaction
from .utils import budget_items, format_date_long, goal_items


def _notifications():
    from .models import TelegramPendingCategory
    from django.utils import timezone as djtz

    items = []
    pending_qs = TelegramPendingCategory.objects.filter(expires_at__gt=djtz.now())
    if pending_qs.exists():
        if pending_qs.filter(awaiting_budget=True).exists():
            desc = 'Balas di Telegram dengan angka batas bulanan (atau "lewat").'
        else:
            desc = 'Balas di Telegram: simpan / bulanan / batal.'
        items.append({
            'tone': 'info',
            'title': 'Telegram: konfirmasi kategori',
            'desc': desc,
        })
    for b in budget_items():
        if b['state'] == 'over':
            items.append({
                'tone': 'danger',
                'title': f"Anggaran {b['name']} terlampaui",
                'desc': f"Terpakai {b['pct']}% dari batas bulanan.",
            })
        elif b['state'] == 'warn':
            items.append({
                'tone': 'warning',
                'title': f"Anggaran {b['name']} hampir habis",
                'desc': b['remaining_label'],
            })
    for g in goal_items():
        if g['done']:
            items.append({
                'tone': 'success',
                'title': f"Tujuan “{g['name']}” tercapai",
                'desc': f"Target {g['target_label']} sudah terpenuhi. 🎉",
            })
        elif g['pct'] >= 80:
            items.append({
                'tone': 'info',
                'title': f"Tujuan “{g['name']}” hampir tercapai",
                'desc': f"Progres {g['pct']}% dari target {g['target_label']}.",
            })
    return items[:6]


def finance_context(request):
    """Konteks global untuk seluruh halaman MyFinance."""
    user = request.user

    biometric_count = 0
    telegram_status = None
    if user.is_authenticated:
        from accounts.models import WebauthnCredential

        biometric_count = WebauthnCredential.objects.filter(user=user).count()
        # Status integrasi Telegram untuk pill di topbar (getMe di-cache
        # 6 jam di DB, jadi maksimal satu panggilan API per 6 jam).
        from . import telegram_bot

        telegram_status = telegram_bot.status_payload()
        # Bersihkan kategori "hanya bulan ini" yang masa berlakunya habis
        # (transaksinya dipindah ke kategori cadangan).
        telegram_bot.purge_expired_temporary_categories()

    return {
        'mf_categories': Category.objects.all(),
        'mf_has_data': Transaction.objects.exists(),
        'mf_today_long': format_date_long(date.today()),
        'mf_today_iso': date.today().isoformat(),
        'mf_notifications': _notifications(),
        # --- Status akun (dipakai sidebar, topbar, landing) ---
        'mf_is_authenticated': user.is_authenticated,
        'mf_biometric_count': biometric_count,
        'mf_webauthn_enabled': settings.WEBAUTHN_ENABLED,
        # --- Integrasi Telegram (pill topbar + data polling main.js) ---
        'mf_telegram': telegram_status,
    }
