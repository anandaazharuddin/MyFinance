import re
from datetime import date
from decimal import Decimal
from functools import wraps

from django.contrib.auth import logout as auth_logout
from django.db.models import Sum
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import BudgetForm, CategoryForm, ContributeForm, GoalForm, TransactionForm
from .models import Budget, Category, Goal, Transaction
from .utils import (
    MONTHS_ID_FULL,
    budget_items,
    expense_breakdown,
    format_idr,
    format_idr_signed,
    goal_items,
    last_n_months,
    month_range,
    monthly_series,
    stats_payload,
    tx_payload,
)


def _month_label(value):
    year, month = value.split('-')
    return f'{MONTHS_ID_FULL[int(month) - 1]} {year}'


def _filtered_transactions(q_type, q_month):
    qs = Transaction.objects.select_related('category')
    if q_type in (Transaction.INCOME, Transaction.EXPENSE):
        qs = qs.filter(type=q_type)
    if re.match(r'^\d{4}-\d{2}$', q_month or ''):
        year, month = (int(part) for part in q_month.split('-'))
        start, end = month_range(year, month)
        qs = qs.filter(date__gte=start, date__lt=end)
    return qs


def _summary(q_type, q_month):
    month_qs = _filtered_transactions('', q_month)
    income = month_qs.filter(type=Transaction.INCOME).aggregate(s=Sum('amount'))['s'] or Decimal(0)
    expense = month_qs.filter(type=Transaction.EXPENSE).aggregate(s=Sum('amount'))['s'] or Decimal(0)
    return {
        'income': float(income),
        'expense': float(expense),
        'net': float(income - expense),
        'count': _filtered_transactions(q_type, q_month).count(),
        'income_label': format_idr(income),
        'expense_label': format_idr(expense),
        'net_label': format_idr_signed(income - expense),
    }


def _goal_item(goal_id):
    item = next((g for g in goal_items() if g['id'] == goal_id), None)
    if item is None:
        raise Http404()
    return item


# ---------------------------------------------------------------------------
# Proteksi halaman & API — seluruh app wajib login (landing tetap publik)
# ---------------------------------------------------------------------------

def _is_owner(user):
    """Satu-satunya yang boleh memakai website ini: pemilik (role=owner)."""
    profile = getattr(user, 'profile', None)
    return bool(profile and profile.is_owner and user.is_active)


def require_site(view_func):
    """Halaman app: wajib login + pemilik; selain itu ke /login/."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect('/login/?next=' + request.get_full_path())
        if not user.is_active:
            auth_logout(request)
            return redirect('/login/?msg=nonaktif')
        if not _is_owner(user):
            auth_logout(request)
            return redirect('/login/?msg=ditolak')
        return view_func(request, *args, **kwargs)

    return wrapper


def require_api(view_func):
    """API: wajib login + pemilik; selain itu balas 401 JSON
    (main.js menangkapnya lalu mengalihkan ke /login/)."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated or not _is_owner(user):
            if user.is_authenticated:
                auth_logout(request)
            return JsonResponse(
                {'ok': False, 'unauthorized': True, 'message': 'Akses ditolak — sesi berakhir.'},
                status=401,
            )
        return view_func(request, *args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# Halaman
# ---------------------------------------------------------------------------

def landing(request):
    return render(request, 'finance/landing.html')


@require_site
def dashboard(request):
    now = date.today()
    stats = stats_payload(now)
    series = monthly_series(6)
    breakdown, total_exp = expense_breakdown(now)

    context = {
        'mf_page': 'dashboard',
        'stats': stats,
        'series': series,
        'breakdown': breakdown,
        'breakdown_total_label': format_idr(total_exp),
        'current_month_label': f'{MONTHS_ID_FULL[now.month - 1]} {now.year}',
        'budgets_top': sorted(budget_items(now), key=lambda b: -b['pct'])[:4],
        'goals_top': goal_items()[:3],
        'recent_tx': list(Transaction.objects.select_related('category')[:8]),
        'mf_js_data': {
            'page': 'dashboard',
            'charts': {
                'cashflow': {
                    'labels': [s['label'] for s in series],
                    'income': [s['income'] for s in series],
                    'expense': [s['expense'] for s in series],
                },
                'spend': {
                    'labels': [b['name'] for b in breakdown],
                    'values': [b['value'] for b in breakdown],
                    'colors': [b['color'] for b in breakdown],
                },
            },
        },
    }
    return render(request, 'finance/dashboard.html', context)


@require_site
def transactions(request):
    q_type = request.GET.get('type', '')
    q_month = request.GET.get('month', '')
    qs = _filtered_transactions(q_type, q_month)
    months = [f'{y:04d}-{m:02d}' for y, m in last_n_months(12)]

    context = {
        'mf_page': 'transactions',
        'tx_list': list(qs[:200]),
        'summary': _summary(q_type, q_month),
        'filter_type': q_type,
        'filter_month': q_month,
        'month_options': [(value, _month_label(value)) for value in months],
        'mf_js_data': {'page': 'transactions'},
    }
    return render(request, 'finance/transactions.html', context)


@require_site
def budgets(request):
    now = date.today()
    month_label = f'{MONTHS_ID_FULL[now.month - 1]} {now.year}'
    context = {
        'mf_page': 'budgets',
        'budgets': budget_items(),
        'unbudgeted': [
            c for c in Category.objects.filter(type=Category.EXPENSE)
            if not hasattr(c, 'budget')
        ],
        'expense_categories': Category.objects.filter(type=Category.EXPENSE),
        'current_month_label': month_label,
        'mf_js_data': {'page': 'budgets', 'month_label': month_label},
    }
    return render(request, 'finance/budgets.html', context)


@require_site
def goals(request):
    context = {
        'mf_page': 'goals',
        'goals': goal_items(),
        'mf_js_data': {'page': 'goals'},
    }
    return render(request, 'finance/goals.html', context)


# ---------------------------------------------------------------------------
# API (dipanggil via fetch dari main.js)
# ---------------------------------------------------------------------------

@require_api
@require_POST
def api_create_transaction(request):
    form = TransactionForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
    tx = form.save()
    return JsonResponse({
        'ok': True,
        'message': 'Transaksi berhasil dicatat.',
        'tx': tx_payload(tx),
        'stats': stats_payload(),
    })


@require_api
@require_POST
def api_delete_transaction(request, pk):
    tx = get_object_or_404(Transaction, pk=pk)
    tx.delete()
    return JsonResponse({
        'ok': True,
        'message': 'Transaksi dihapus.',
        'stats': stats_payload(),
    })


@require_api
def api_tx_summary(request):
    return JsonResponse(_summary(request.GET.get('type', ''), request.GET.get('month', '')))


@require_api
@require_POST
def api_create_category(request):
    """Buat kategori baru langsung dari form transaksi (inline, tanpa buka admin)."""
    form = CategoryForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
    category = form.save()
    return JsonResponse({
        'ok': True,
        'message': f'Kategori "{category.name}" dibuat.',
        'category': {
            'id': category.id,
            'name': category.name,
            'type': category.type,
            'icon': category.icon,
            'color': category.color,
        },
    })


@require_api
@require_POST
def api_save_budget(request):
    instance = None
    if request.POST.get('id'):
        instance = Budget.objects.filter(pk=request.POST['id']).first()
    form = BudgetForm(request.POST, instance=instance)
    if not form.is_valid():
        return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
    saved = form.save()
    item = next(b for b in budget_items() if b['id'] == saved.id)
    return JsonResponse({
        'ok': True,
        'message': 'Anggaran berhasil disimpan.',
        'budget': item,
    })


@require_api
@require_POST
def api_delete_budget(request, pk):
    budget = get_object_or_404(Budget, pk=pk)
    category_id = budget.category_id
    budget.delete()
    return JsonResponse({
        'ok': True,
        'message': 'Anggaran dihapus.',
        'category_id': category_id,
    })


@require_api
@require_POST
def api_create_goal(request):
    form = GoalForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
    saved = form.save()
    return JsonResponse({
        'ok': True,
        'message': 'Tujuan keuangan berhasil dibuat.',
        'goal': _goal_item(saved.id),
    })


@require_api
@require_POST
def api_goal_contribute(request, pk):
    goal = get_object_or_404(Goal, pk=pk)
    form = ContributeForm(request.POST)
    if form.is_valid():
        amount = form.cleaned_data['amount']
        if goal.target_amount and goal.current_amount + amount > goal.target_amount:
            form.add_error(
                'amount',
                f"Maksimal {format_idr(goal.target_amount - goal.current_amount)} (sisa target).",
            )
    if not form.is_valid():
        return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
    amount = form.cleaned_data['amount']
    goal.current_amount = min(goal.current_amount + amount, goal.target_amount)
    goal.save(update_fields=['current_amount'])
    item = _goal_item(goal.id)
    message = 'Tujuan tercapai! 🎉' if item['done'] else 'Dana berhasil ditambahkan.'
    return JsonResponse({'ok': True, 'message': message, 'goal': item})


@require_api
@require_POST
def api_delete_goal(request, pk):
    goal = get_object_or_404(Goal, pk=pk)
    goal.delete()
    return JsonResponse({'ok': True, 'message': 'Tujuan dihapus.'})


@require_api
@require_POST
def api_seed(request):
    from .seeding import run_seed

    if run_seed():
        return JsonResponse({'ok': True, 'message': 'Data contoh berhasil dimuat.'})
    return JsonResponse(
        {'ok': False, 'message': 'Database sudah berisi data, data contoh dilewati.'},
        status=400,
    )


# ---------------------------------------------------------------------------
# API integrasi Telegram
# ---------------------------------------------------------------------------

@require_api
def api_telegram_poll(request):
    """Dipanggil main.js tiap ~25 dtk selama aplikasi terbuka.

    Menarik update Telegram baru (getUpdates), memprosesnya di server
    (parse -> transaksi / tanya kategori), lalu mengembalikan status
    integrasi + transaksi yang baru tercatat untuk ditampilkan di web.
    """
    from . import telegram_bot

    result = telegram_bot.poll_updates()
    if result is None:
        # Token belum diisi — tetap balas status agar UI bisa memandu setup.
        return JsonResponse({
            'ok': True,
            'status': telegram_bot.status_payload(),
            'new_tx': [],
            'events': [],
        })
    events, txs = result
    new_budgets = []
    for ev in events:
        if ev.get('budget_created'):
            item = next(
                (b for b in budget_items() if b['category_id'] == ev.get('category_id')),
                None,
            )
            if item:
                new_budgets.append(item)
    return JsonResponse({
        'ok': True,
        'status': telegram_bot.status_payload(),
        'new_tx': [tx_payload(tx) for tx in txs],
        'new_budgets': new_budgets,
        'events': events,
    })
