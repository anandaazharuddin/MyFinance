"""Integrasi bot Telegram MyFinance (@Ananzhar_bot).

Alur kerja:
1. main.js di browser memanggil GET /api/telegram/poll/ tiap ~25 detik
   selama aplikasi terbuka. Endpoint itu menarik update dari Telegram
   (getUpdates) dan memproses pesannya di server.
2. Pesan dari chat yang diizinkan di-parse menjadi transaksi:
       [pemasukan|+] <kategori...> <jumlah> [tanggal]
   contoh: "makan siang 25rb", "+gaji 5jt", "sewa 1.500.000 05-07-2026".
3. Jika kategori belum ada, bot TIDAK langsung membuatnya — ia bertanya
   dulu (simpan untuk seterusnya / hanya bulan ini / batal). Jawaban
   disimpan di TelegramPendingCategory hingga kamu membalas di Telegram,
   agar kategori random tidak menumpuk di database.
4. Token bot hanya hidup di server (settings dari .env) dan tidak pernah
   dikirim ke browser.
"""
import html
import json
import logging
import re
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

from django.conf import settings
from django.db import transaction
from django.utils import timezone as djtz

from .models import (
    Budget,
    Category,
    TelegramBotState,
    TelegramPendingCategory,
    Transaction,
)
from .utils import MONTHS_ID_FULL, format_date_short, format_idr

logger = logging.getLogger(__name__)

PENDING_TTL = timedelta(hours=1)      # konfirmasi kategori kadaluarsa 1 jam
ME_CACHE = timedelta(hours=6)         # hasil getMe di-cache 6 jam
AMOUNT_MAX = Decimal(10 ** 12)        # penjaga: maksimal 1 triliun per pesan

# Kategori cadangan saat kategori "hanya bulan ini" dihapus.
FALLBACK_CATEGORIES = {
    Transaction.EXPENSE: ('Lainnya', '📦', '#94a3b8'),
    Transaction.INCOME: ('Lain-lain', '🪙', '#94a3b8'),
}

TYPE_INCOME = {'pemasukan', 'masuk', 'income', 'in', '+'}
TYPE_EXPENSE = {'pengeluaran', 'keluar', 'expense', 'out', '-'}
DATE_WORDS = {'hari ini': timedelta(0), 'kemarin': timedelta(days=1)}

UNAUTHORIZED_MSG = (
    "Halo{name}! Saya bot pencatat keuangan MyFinance. 🤖\n\n"
    "Chat ID kamu: <b>{chat_id}</b>\n\n"
    "Agar pesanmu bisa dicatat, tambahkan ID itu ke file <code>.env</code> "
    "MyFinance:\n<code>TELEGRAM_ALLOWED_CHAT_IDS={chat_id}</code>\n"
    "lalu restart server. Demi keamanan, pesan dari chat lain diabaikan."
)

USAGE_MSG = (
    "Maaf, formatnya belum saya pahami. 😅\n\n"
    "<b>Format:</b> [pemasukan|+] &lt;kategori&gt; &lt;jumlah&gt; [tanggal]\n\n"
    "Contoh:\n"
    "• <code>makan siang 25rb</code>\n"
    "• <code>+gaji 5jt</code>\n"
    "• <code>sewa rumah 1.500.000 05-07-2026</code>\n"
    "• <code>belanja 100rb kemarin</code>"
)

ASK_CATEGORY_MSG = (
    "Kategori <b>{name}</b> belum ada di MyFinance\n"
    "({ttype} {amount}, {date}).\n\n"
    "Mau simpan kategori ini?\n"
    "1️⃣ <code>simpan</code> — untuk seterusnya\n"
    "2️⃣ <code>bulanan</code> — hanya untuk {month}, "
    "dihapus otomatis setelahnya\n"
    "❌ <code>batal</code> — abaikan permintaan ini\n\n"
    "(jawaban kadaluarsa dalam 1 jam)"
)

SAVED_MSG = (
    "✅ <b>Tersimpan</b>\n\n"
    "• Kategori: {icon} {name}\n"
    "• Jenis: {ttype}\n"
    "• Jumlah: {amount}\n"
    "• Tanggal: {date}"
)

PENDING_DONE_MSG = (
    "✅ Kategori <b>{name}</b> dibuat ({scope})\n"
    "{budget_line}• Transaksi {amount} ({ttype}, {date}) tercatat."
)

ASK_BUDGET_MSG = (
    "Kategori <b>{name}</b> akan disimpan untuk seterusnya. ✅\n\n"
    "Satu lagi: berapa <b>batas pengeluaran bulanan</b> untuk {name}?\n"
    "Balas dengan angka, mis. <code>500000</code> atau <code>500rb</code>.\n"
    "(ketik <code>lewat</code> untuk tidak membuat anggarannya —\n"
    "nanti bisa dibuat dari menu Anggaran di web)"
)

BUDGET_REASK_MSG = (
    "Hmm, itu belum berupa angka. 😅\n"
    "Kirim batas bulanan, mis. <code>500000</code> / <code>500rb</code>,\n"
    "atau ketik <code>lewat</code> untuk melewatinya."
)

BUDGET_SKIP_WORDS = {'lewat', 'skip', 'tidak', 'tanpa', 'kosong', '0', 'n', 'no'}


# ---------------------------------------------------------------------------
# Panggilan Telegram Bot API (urllib — tanpa dependensi baru)
# ---------------------------------------------------------------------------

def _api(method, **params):
    """Panggil satu method Telegram Bot API.

    Mengembalikan dict JSON ('ok': True/False) atau None bila token
    kosong / jaringan gagal / respons tidak ok.
    """
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return None
    url = f'https://api.telegram.org/bot{token}/{method}'
    if params:
        url += '?' + urlparse.urlencode(params)
    try:
        req = urlrequest.Request(url, headers={'User-Agent': 'MyFinanceBot/1.0'})
        with urlrequest.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
    except (urlerror.URLError, urlerror.HTTPError, OSError, ValueError) as exc:
        logger.warning('Telegram API %s gagal: %s', method, exc)
        return None
    if not isinstance(payload, dict) or not payload.get('ok'):
        logger.warning('Telegram API %s tidak ok: %s', method,
                       (payload or {}).get('description'))
        return None
    return payload


def _reply(chat_id, text):
    """Kirim balasan teks (HTML) ke chat; aman dipanggil meski gagal."""
    _api('sendMessage', chat_id=chat_id, text=text,
         parse_mode='HTML', disable_web_page_preview='true')


def get_state():
    state, _ = TelegramBotState.objects.get_or_create(pk=1)
    return state


def get_me(fresh=False):
    """Verifikasi token via getMe; hasilnya di-cache 6 jam di state."""
    state = get_state()
    if not fresh and state.me_username and state.me_checked_at:
        if djtz.now() - state.me_checked_at < ME_CACHE:
            return state.me_username
    payload = _api('getMe')
    if payload:
        state.me_username = (payload.get('result') or {}).get('username', '')
        state.me_checked_at = djtz.now()
        state.save(update_fields=['me_username', 'me_checked_at', 'updated_at'])
        return state.me_username
    return None


# ---------------------------------------------------------------------------
# Status untuk UI web (topbar pill, kartu di halaman Akun, notifikasi)
# ---------------------------------------------------------------------------

def status_payload():
    """Ringkasan status integrasi — dipakai context processor & halaman Akun.

    'state':  on    = token OK + chat kamu sudah diizinkan
              warn  = token OK, tapi chat belum diverifikasi / belum diizinkan
              off   = token belum diisi di .env
    """
    state = get_state()
    token_set = bool(settings.TELEGRAM_BOT_TOKEN)
    bot_username = get_me() if token_set else None
    allowed = {str(c) for c in settings.TELEGRAM_ALLOWED_CHAT_IDS}
    last_chat = str(state.last_chat_id) if state.last_chat_id else ''
    chat_verified = bool(last_chat) and last_chat in allowed

    if not token_set:
        state_key, state_label = 'off', 'Belum dikonfigurasi'
        label = ('Token bot belum diisi. Tambahkan TELEGRAM_BOT_TOKEN di '
                 'file .env lalu restart server.')
    elif not allowed:
        state_key, state_label = 'warn', 'Butuh verifikasi chat'
        label = ('Token bot valid, tapi TELEGRAM_ALLOWED_CHAT_IDS masih '
                 'kosong. Kirim pesan apa saja ke @'
                 f'{settings.TELEGRAM_BOT_USERNAME} untuk mendapat chat ID.')
    elif not last_chat:
        state_key, state_label = 'warn', 'Butuh verifikasi chat'
        label = (f'Kirim pesan apa saja ke @{settings.TELEGRAM_BOT_USERNAME} — '
                 'balasannya memuat chat ID yang harus kamu izinkan.')
    elif not chat_verified:
        state_key, state_label = 'warn', 'Chat belum diizinkan'
        label = (f'Chat {last_chat} belum ada di TELEGRAM_ALLOWED_CHAT_IDS. '
                 'Tambahkan lalu restart server.')
    else:
        state_key, state_label = 'on', 'Terhubung'
        label = (f'Terhubung sebagai @{bot_username or settings.TELEGRAM_BOT_USERNAME} '
                 f'— chat {last_chat} terverifikasi. Transaksi dari Telegram '
                 'otomatis tercatat selama aplikasi ini terbuka.')

    return {
        'state': state_key,
        'state_label': state_label,
        'label': label,
        'token_set': token_set,
        'bot_username': bot_username or settings.TELEGRAM_BOT_USERNAME,
        'allowed_count': len(allowed),
        'last_chat_id': last_chat,
        'last_chat_name': state.last_chat_name,
        'chat_verified': chat_verified,
        'last_activity': state.last_activity,
        'pending': TelegramPendingCategory.objects.filter(
            expires_at__gt=djtz.now()).exists(),
    }


# ---------------------------------------------------------------------------
# Parser pesan teks -> transaksi
# ---------------------------------------------------------------------------

def _parse_amount(token):
    """'25rb' -> 25000, '1.500.000' -> 1500000, '+gaji' -> None."""
    tok = (token or '').strip().lower()
    tok = re.sub(r'^(rp|rupiah)\s*', '', tok)
    unit = 1
    for suffix, factor in (('juta', 10 ** 6), ('jt', 10 ** 6),
                           ('ribu', 10 ** 3), ('rb', 10 ** 3), ('r', 10 ** 3)):
        if tok.endswith(suffix):
            unit = factor
            tok = tok[: -len(suffix)]
            break
    cleaned = tok.replace('.', '').replace(',', '').replace(' ', '')
    if not cleaned.isdigit():
        return None
    try:
        value = Decimal(int(cleaned) * unit)
    except InvalidOperation:
        return None
    return value if 0 < value <= AMOUNT_MAX else None


def _parse_date_token(token, today):
    """'05-07-2026' | '2026-07-05' | '05-07' | 'hari ini' | 'kemarin'."""
    tok = (token or '').strip().lower()
    if tok in DATE_WORDS:
        return today - DATE_WORDS[tok]
    m = re.fullmatch(r'(\d{4})-(\d{1,2})-(\d{1,2})', tok)
    if m:
        y, mo, d = (int(x) for x in m.groups())
    else:
        m = re.fullmatch(r'(\d{1,2})-(\d{1,2})-(\d{4})', tok)
        if m:
            d, mo, y = (int(x) for x in m.groups())
        else:
            m = re.fullmatch(r'(\d{1,2})-(\d{1,2})', tok)
            if not m:
                return None
            d, mo = (int(x) for x in m.groups())
            y = today.year
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def parse_message(text, today=None):
    """Parse pesan Telegram menjadi transaksi.

    Format: [pemasukan|+] <kategori...> <jumlah> [tanggal]
    Mengembalikan dict {type, category, amount, date} atau None.
    """
    today = today or date.today()
    tokens = (text or '').strip().split()
    if not tokens:
        return None
    ttype = Transaction.EXPENSE
    first = tokens[0].strip().lower()
    prefix = first[:1] if first[:1] in ('+', '-') else ''
    word = first[len(prefix):]
    if prefix == '+' or word in TYPE_INCOME:
        ttype = Transaction.INCOME
        # Kata kunci tipe ("pemasukan") dibuang; tapi prefix yang MENYERET
        # kata ('+gaji') berarti kata itu nama kategori — dipertahankan.
        rest = ([word] + tokens[1:]) if (prefix and word) else tokens[1:]
    elif prefix == '-' or word in TYPE_EXPENSE:
        rest = ([word] + tokens[1:]) if (prefix and word) else tokens[1:]
    else:
        rest = tokens
    # Tanggal opsional di akhir pesan
    tx_date = today
    if rest and _parse_date_token(rest[-1], today) is not None:
        tx_date = _parse_date_token(rest[-1], today)
        rest = rest[:-1]
    if len(rest) < 2:
        return None
    amount = _parse_amount(rest[-1])
    if amount is None:
        return None
    category = ' '.join(rest[:-1]).strip().lower()
    if not category or len(category) > 60:
        return None
    return {'type': ttype, 'category': category, 'amount': amount, 'date': tx_date}


# ---------------------------------------------------------------------------
# Kategori: cari / buat (dengan konfirmasi) / bersihkan yang kedaluwarsa
# ---------------------------------------------------------------------------

def _ttype_label(ttype):
    return 'Pengeluaran' if ttype == Transaction.EXPENSE else 'Pemasukan'


def find_category(name, ttype):
    name = (name or '').strip().lower()
    if not name:
        return None
    return Category.objects.filter(type=ttype, name__iexact=name).first()


def create_category(name, ttype, temporary=False):
    """Find-or-create kategori (nama dikecilkan & dipadatkan spasi).

    Idempoten: nama yang sama (termasuk varian berpenanda tipe) selalu
    mengembalikan kategori yang sudah ada. Nama bentrok dengan tipe lain
    diberi penanda, mis. 'makan' -> 'makan (pemasukan)'.

    temporary=True mengisi valid_until dengan akhir bulan berjalan —
    kategori itu akan dihapus oleh purge_expired_temporary_categories().
    """
    base = re.sub(r'\s+', ' ', (name or '').strip().lower())[:60]
    if not base:
        return None
    candidates = [base]
    if Category.objects.filter(name__iexact=base).exists():
        suffixed = f'{base} ({_ttype_label(ttype).lower()})'[:60]
        if suffixed != base:
            candidates.append(suffixed)
    for cand in candidates:
        existing = Category.objects.filter(type=ttype, name__iexact=cand).first()
        if existing:
            return existing
    candidate = candidates[-1]
    icon, color = (('📈', '#16a34a') if ttype == Transaction.INCOME
                   else ('💸', '#f59e0b'))
    try:
        return Category.objects.create(
            name=candidate,
            type=ttype,
            icon=icon,
            color=color,
            temporary=temporary,
            valid_until=end_of_month(date.today()) if temporary else None,
        )
    except Exception:
        # Bentrok unik yang tak terduga — kembalikan yang sudah ada.
        return Category.objects.filter(type=ttype, name__iexact=candidate).first()


def end_of_month(d):
    return d.replace(day=monthrange(d.year, d.month)[1])


def _fallback_category(ttype):
    name, icon, color = FALLBACK_CATEGORIES[ttype]
    cat = Category.objects.filter(type=ttype, name__iexact=name).first()
    if cat:
        return cat
    return Category.objects.create(name=name, type=ttype, icon=icon, color=color)


def purge_expired_temporary_categories():
    """Hapus kategori 'hanya bulan ini' yang masa berlakunya habis.

    Transaksi miliknya dipindah ke kategori cadangan ('Lainnya'/'Lain-lain')
    agar riwayat tidak hilang. Dipanggil lazy dari context processor.
    """
    today = date.today()
    expired = Category.objects.filter(temporary=True, valid_until__lt=today)
    moved = 0
    for cat in expired:
        fallback = _fallback_category(cat.type)
        moved += Transaction.objects.filter(category=cat).update(category=fallback)
        cat.delete()
    if moved:
        logger.info('Purge kategori telegram sementara: %d transaksi dipindah.', moved)
    return moved


# ---------------------------------------------------------------------------
# Proses satu update Telegram
# ---------------------------------------------------------------------------

def _finish_pending(pending, chat_id, temporary, budget_limit=None):
    """Konfirmasi final: buat kategori (+ anggaran bulanan) & catat transaksinya."""
    with transaction.atomic():
        category = create_category(
            pending.category_name, pending.tx_type, temporary=temporary)
        tx = Transaction.objects.create(
            category=category,
            type=pending.tx_type,
            amount=pending.amount,
            date=pending.tx_date,
        )
        budget = None
        if budget_limit is not None:
            # Anggaran bulanan -> langsung jadi kartu di menu Anggaran.
            budget, _ = Budget.objects.update_or_create(
                category=category, defaults={'monthly_limit': budget_limit})
        pending.delete()
    today = date.today()
    scope = (
        f'hanya bulan {MONTHS_ID_FULL[today.month - 1]} {today.year}'
        if temporary else 'untuk seterusnya'
    )
    budget_line = (
        f'• Anggaran: {format_idr(budget.monthly_limit)}/bulan — '
        'kartunya sudah masuk ke menu Anggaran\n'
        if budget is not None else ''
    )
    _reply(chat_id, PENDING_DONE_MSG.format(
        name=html.escape(category.name),
        scope=scope,
        budget_line=budget_line,
        amount=format_idr(tx.amount),
        ttype=_ttype_label(tx.type),
        date=format_date_short(tx.date),
    ))
    return {
        'kind': 'tx',
        'tx_id': tx.id,
        'category_new': True,
        'temporary': temporary,
        'category': category.name,
        'category_id': category.id,
        'budget_created': budget is not None,
    }


def process_update(update):
    """Proses satu update Telegram.

    Mengembalikan event dict untuk UI web (atau None bila bukan pesan teks).
    Offset update dijamin maju (update tak akan diproses dua kali).
    """
    message = (update or {}).get('message') or {}
    text = (message.get('text') or '').strip()
    if not text:
        return None
    chat = message.get('chat') or {}
    chat_id = chat.get('id')
    chat_name = ' '.join(
        filter(None, [chat.get('first_name'), chat.get('last_name')])
    ) or chat.get('username') or str(chat_id)

    state = get_state()
    if chat_id is not None:
        state.last_chat_id = chat_id
        state.last_chat_name = chat_name[:120]
    update_id = update.get('update_id') or 0
    if update_id:
        state.last_update_id = max(state.last_update_id, update_id)
    state.last_activity = djtz.now()
    state.save()

    allowed = {str(c) for c in settings.TELEGRAM_ALLOWED_CHAT_IDS}
    if str(chat_id) not in allowed:
        _reply(chat_id, UNAUTHORIZED_MSG.format(
            name=f' {html.escape(chat_name)}' if chat_name else '',
            chat_id=chat_id,
        ))
        return {'kind': 'unauthorized', 'chat_id': str(chat_id)}

    # Masih ada pertanyaan yang menunggu? Tangani jawabannya.
    pending = TelegramPendingCategory.objects.filter(
        chat_id=chat_id, expires_at__gt=djtz.now()).first()
    if pending:
        answer = text.lower().strip()
        if pending.awaiting_budget:
            # TAHAP 2: angka batas bulanan untuk kategori yang akan disimpan.
            if answer in BUDGET_SKIP_WORDS:
                return _finish_pending(
                    pending, chat_id, temporary=False, budget_limit=None)
            if answer in ('batal', 'hapus', 'cancel', 'x'):
                pending.delete()
                _reply(chat_id, 'Permintaan dibatalkan. '
                                'Kategori & anggaran tidak dibuat.')
                return {'kind': 'cancelled'}
            limit = _parse_amount(answer)
            if limit is not None:
                return _finish_pending(
                    pending, chat_id, temporary=False, budget_limit=limit)
            if parse_message(text) is not None:
                # Pesan baru berupa transaksi — buang pertanyaan, proses
                # sebagai usual di bawah.
                pending.delete()
            else:
                _reply(chat_id, BUDGET_REASK_MSG)
                return {'kind': 'ask_budget', 'category': pending.category_name}
        else:
            # TAHAP 1: simpan untuk seterusnya / hanya bulan ini / batal.
            if answer in ('simpan', '1', 'y', 'ya', 'seterusnya', 'selamanya'):
                if pending.tx_type == Transaction.EXPENSE:
                    # Satu lagi: tanya batas bulanan (jadi kartu di Anggaran).
                    pending.awaiting_budget = True
                    pending.expires_at = djtz.now() + PENDING_TTL
                    pending.save(update_fields=['awaiting_budget', 'expires_at'])
                    _reply(chat_id, ASK_BUDGET_MSG.format(
                        name=html.escape(pending.category_name)))
                    return {'kind': 'ask_budget', 'category': pending.category_name}
                # Pemasukan tidak punya konsep anggaran — langsung final.
                return _finish_pending(pending, chat_id, temporary=False)
            if answer in ('bulanan', '2', 'b', 'bulan ini', 'bulanini', 'sementara'):
                return _finish_pending(pending, chat_id, temporary=True)
            if answer in ('batal', 'hapus', 'cancel', 'x', 'tidak'):
                pending.delete()
                _reply(chat_id, 'Permintaan kategori dibatalkan. '
                                'Kirim transaksi baru kapan saja.')
                return {'kind': 'cancelled'}
            # Bukan jawaban konfirmasi -> lanjut parse sebagai pesan baru.

    parsed = parse_message(text)
    if not parsed:
        _reply(chat_id, USAGE_MSG)
        return {'kind': 'error', 'text': text}

    category = find_category(parsed['category'], parsed['type'])
    if category is None:
        # JANGAN langsung buat — tanyakan dulu (anti kategori random).
        TelegramPendingCategory.objects.filter(chat_id=chat_id).delete()
        TelegramPendingCategory.objects.create(
            chat_id=chat_id,
            category_name=parsed['category'],
            tx_type=parsed['type'],
            amount=parsed['amount'],
            tx_date=parsed['date'],
            expires_at=djtz.now() + PENDING_TTL,
        )
        _reply(chat_id, ASK_CATEGORY_MSG.format(
            name=html.escape(parsed['category']),
            ttype=_ttype_label(parsed['type']),
            amount=format_idr(parsed['amount']),
            date=format_date_short(parsed['date']),
            month=f'{MONTHS_ID_FULL[parsed["date"].month - 1]} {parsed["date"].year}',
        ))
        return {'kind': 'ask_category', 'category': parsed['category']}

    tx = Transaction.objects.create(
        category=category,
        type=parsed['type'],
        amount=parsed['amount'],
        date=parsed['date'],
    )
    _reply(chat_id, SAVED_MSG.format(
        icon=category.icon,
        name=html.escape(category.name),
        ttype=_ttype_label(tx.type),
        amount=format_idr(tx.amount),
        date=format_date_short(tx.date),
    ))
    return {'kind': 'tx', 'tx_id': tx.id, 'category': category.name}


# ---------------------------------------------------------------------------
# Polling (dipanggil endpoint /api/telegram/poll/)
# ---------------------------------------------------------------------------

def poll_updates():
    """Tarik semua update Telegram yang belum diproses, proses satu-satu.

    Mengembalikan (events, txs) — events untuk notifikasi web, txs adalah
    objek Transaction yang baru dibuat. None bila token belum diisi.
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        return None
    state = get_state()
    payload = _api('getUpdates',
                   offset=state.last_update_id + 1,
                   timeout=0,
                   allowed_updates='["message"]')
    if payload is None:
        # Jaringan/Telegram belum siap — percobaan lagi di poll berikutnya.
        return [], []
    events = []
    txs = []
    for update in payload.get('result', []):
        try:
            event = process_update(update)
        except Exception:  # noqa: BLE001 — satu update rusak tak boleh macet-kan antrian
            logger.exception('Gagal memproses update Telegram %s',
                             update.get('update_id'))
            event = {'kind': 'error'}
        if event:
            events.append(event)
            if event.get('kind') == 'tx' and event.get('tx_id'):
                tx = Transaction.objects.filter(pk=event['tx_id']).first()
                if tx:
                    txs.append(tx)
    return events, txs
