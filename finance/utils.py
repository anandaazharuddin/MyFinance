"""Helper utilitas MyFinance: format angka/tanggal & perakitan data dasbor."""
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Q, Sum

from .models import Budget, Goal, Transaction

MONTHS_ID = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
MONTHS_ID_FULL = [
    'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
    'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember',
]
WEEKDAYS_ID = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']


def format_idr(amount):
    """1500000 -> 'Rp 1.500.000' (tanpa tanda negatif)."""
    value = int(round(Decimal(amount or 0)))
    return 'Rp {:,}'.format(abs(value)).replace(',', '.')


def format_idr_signed(amount):
    value = int(round(Decimal(amount or 0)))
    if value < 0:
        return '−' + format_idr(value)
    return format_idr(value)


def format_percent(value, decimals=1):
    return f'{float(value):.{decimals}f}'.replace('.', ',') + '%'


def month_label(d):
    return MONTHS_ID[d.month - 1]


def last_n_months(n=6):
    """Kembali dengan list (year, month) dari bulan tertua sampai bulan ini."""
    today = date.today()
    result = []
    y, m = today.year, today.month
    for _ in range(n):
        result.append((y, m))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return list(reversed(result))


def month_range(y, m):
    start = date(y, m, 1)
    end = date(y + (1 if m == 12 else 0), (m % 12) + 1, 1)
    return start, end


def format_date_long(d):
    return f'{WEEKDAYS_ID[d.weekday()]}, {d.day} {MONTHS_ID_FULL[d.month - 1]} {d.year}'


def format_date_short(d, ref_year=None):
    ref = ref_year if ref_year is not None else date.today().year
    suffix = '' if d.year == ref else f' {d.year}'
    return f'{d.day} {MONTHS_ID[d.month - 1]}{suffix}'


def _month_total(start, end, ttype):
    value = Transaction.objects.filter(
        type=ttype, date__gte=start, date__lte=end
    ).aggregate(s=Sum('amount'))['s']
    return value or Decimal(0)


def stats_payload(now=None):
    """Statistik utama dasbor, siap dipakai template maupun API."""
    now = now or date.today()
    first = now.replace(day=1)
    prev_end = first - timedelta(days=1)
    prev_start = prev_end.replace(day=1)

    inc_mtd = _month_total(first, now, Transaction.INCOME)
    exp_mtd = _month_total(first, now, Transaction.EXPENSE)
    inc_ltm = _month_total(prev_start, prev_end, Transaction.INCOME)
    exp_ltm = _month_total(prev_start, prev_end, Transaction.EXPENSE)

    totals = Transaction.objects.aggregate(
        i=Sum('amount', filter=Q(type=Transaction.INCOME)),
        e=Sum('amount', filter=Q(type=Transaction.EXPENSE)),
    )
    balance = (totals['i'] or Decimal(0)) - (totals['e'] or Decimal(0))
    net_mtd = inc_mtd - exp_mtd
    rate = (net_mtd / inc_mtd * 100) if inc_mtd else Decimal(0)

    def change(cur, prev):
        if not prev:
            return None
        return float((cur - prev) / prev * 100)

    inc_ch = change(inc_mtd, inc_ltm)
    exp_ch = change(exp_mtd, exp_ltm)

    return {
        'balance': {
            'value': float(balance),
            'label': format_idr_signed(balance),
            'delta_text': f'{"+" if net_mtd >= 0 else "−"}{format_idr(abs(net_mtd))} bulan ini',
            'delta_tone': 'good' if net_mtd >= 0 else 'bad',
        },
        'income_mtd': {
            'value': float(inc_mtd),
            'label': format_idr(inc_mtd),
            'delta_text': (
                f'{"↑" if inc_ch >= 0 else "↓"} {abs(inc_ch):.0f}% dari bulan lalu'
                if inc_ch is not None else 'Tanpa pembanding bulan lalu'
            ),
            'delta_tone': 'good' if (inc_ch or 0) >= 0 else 'bad',
        },
        'expense_mtd': {
            'value': float(exp_mtd),
            'label': format_idr(exp_mtd),
            'delta_text': (
                f'{"↑" if exp_ch >= 0 else "↓"} {abs(exp_ch):.0f}% dari bulan lalu'
                if exp_ch is not None else 'Tanpa pembanding bulan lalu'
            ),
            # Pengeluaran turun = baik, naik = buruk
            'delta_tone': 'bad' if (exp_ch or 0) >= 0 else 'good',
        },
        'savings_rate': {
            'value': float(max(rate, 0)),
            'label': format_percent(rate),
            'delta_text': 'Target hemat 30%',
            'delta_tone': 'neutral',
        },
    }


def monthly_series(n=6):
    series = []
    for y, m in last_n_months(n):
        start, end = month_range(y, m)
        series.append({
            'label': month_label(start),
            'income': float(_month_total(start, end - timedelta(days=1), Transaction.INCOME)),
            'expense': float(_month_total(start, end - timedelta(days=1), Transaction.EXPENSE)),
        })
    return series


def expense_breakdown(now=None, limit=6):
    """Rincian pengeluaran bulan ini per kategori, top N + 'Lainnya'."""
    now = now or date.today()
    first = now.replace(day=1)
    rows = (
        Transaction.objects.filter(type=Transaction.EXPENSE, date__gte=first, date__lte=now)
        .values('category__name', 'category__color')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
    total = sum(r['total'] for r in rows)
    items = []
    for r in rows[:limit]:
        items.append({
            'name': r['category__name'],
            'color': r['category__color'],
            'value': float(r['total']),
            'pct': round(float(r['total'] / total * 100)) if total else 0,
        })
    if len(rows) > limit:
        rest = sum(r['total'] for r in rows[limit:])
        items.append({
            'name': 'Lainnya',
            'color': '#94a3b8',
            'value': float(rest),
            'pct': round(float(rest / total * 100)) if total else 0,
        })
    return items, float(total)


def budget_items(now=None):
    now = now or date.today()
    first = now.replace(day=1)
    month_label = f'{MONTHS_ID_FULL[now.month - 1]} {now.year}'
    spent_map = {
        r['category__id']: r['total']
        for r in Transaction.objects.filter(type=Transaction.EXPENSE, date__gte=first, date__lte=now)
        .values('category__id').annotate(total=Sum('amount'))
    }
    state_labels = {'ok': 'Aman', 'warn': 'Menjelang habis', 'over': 'Terlampaui'}
    items = []
    for b in Budget.objects.select_related('category'):
        limit = b.monthly_limit
        spent = spent_map.get(b.category_id, Decimal(0))
        pct = float(spent / limit * 100) if limit else 0.0
        state = 'over' if pct >= 100 else ('warn' if pct >= 85 else 'ok')
        remaining = limit - spent
        items.append({
            'id': b.id,
            'category_id': b.category_id,
            'name': b.category.name,
            'icon': b.category.icon,
            'color': b.category.color,
            'limit': float(limit),
            'limit_label': format_idr(limit),
            'spent': float(spent),
            'spent_label': format_idr(spent),
            'pct': min(round(pct), 999),
            'state': state,
            'state_label': state_labels[state],
            'remaining_label': (
                f'Sisa {format_idr(remaining)}' if remaining >= 0
                else f'Melebihi {format_idr(-remaining)}'
            ),
            'month_label': month_label,
        })
    return items


def goal_items():
    items = []
    for g in Goal.objects.all():
        target = g.target_amount or Decimal(0)
        pct = float(min(g.current_amount / target * 100, 100)) if target else 0.0
        remaining = max(target - g.current_amount, 0)
        items.append({
            'id': g.id,
            'name': g.name,
            'target': float(target),
            'target_label': format_idr(target),
            'current': float(g.current_amount),
            'current_label': format_idr(g.current_amount),
            'pct': round(pct),
            'ring_p': round(float(min(g.current_amount / target, 1.0)), 4) if target else 0,
            'deadline': g.deadline,
            'deadline_label': format_date_short(g.deadline) if g.deadline else None,
            'remaining': float(remaining),
            'remaining_label': format_idr(remaining),
            'done': bool(target and g.current_amount >= target),
        })
    return items


def tx_payload(tx):
    return {
        'id': tx.id,
        'type': tx.type,
        'date': tx.date.isoformat(),
        'date_label': format_date_short(tx.date),
        'category': {
            'name': tx.category.name,
            'icon': tx.category.icon,
            'color': tx.category.color,
        },
        'description': tx.description or tx.category.name,
        'amount': float(tx.amount),
        'amount_label': format_idr(tx.amount),
    }
