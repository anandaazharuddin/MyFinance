"""Logika penyiapan data contoh MyFinance (dipakai management command & API)."""
import random
from datetime import date

from .models import Budget, Category, Goal, Transaction
from .utils import last_n_months


def run_seed():
    """Isi database dengan data contoh. Return True jika berhasil, False jika data sudah ada."""
    if Transaction.objects.exists():
        return False

    rng = random.Random(42)
    today = date.today()

    catalog = {
        # nama: (type, icon, color)
        'Gaji': ('income', '💼', '#16a34a'),
        'Freelance': ('income', '🧑‍💻', '#0ea5e9'),
        'Investasi': ('income', '📈', '#8b5cf6'),
        'Makanan': ('expense', '🍜', '#f59e0b'),
        'Transportasi': ('expense', '🛵', '#3b82f6'),
        'Belanja': ('expense', '🛍️', '#ec4899'),
        'Hiburan': ('expense', '🎬', '#8b5cf6'),
        'Kesehatan': ('expense', '💊', '#ef4444'),
        'Tagihan': ('expense', '🧾', '#64748b'),
        'Pendidikan': ('expense', '📚', '#06b6d4'),
    }
    categories = {}
    for name, (ttype, icon, color) in catalog.items():
        obj, _ = Category.objects.get_or_create(
            name=name, defaults={'type': ttype, 'icon': icon, 'color': color}
        )
        categories[name] = obj

    txs = []

    for i, (year, month) in enumerate(last_n_months(6)):
        is_current = (year, month) == (today.year, today.month)

        def in_month(day, cat, amount, desc):
            d = date(year, month, day)
            if d > today:
                return
            txs.append((d, cat, amount, desc))

        # Pemasukan
        in_month(1, 'Gaji', 8_500_000, 'Gaji bulanan')
        if rng.random() < 0.7:
            in_month(rng.randint(8, 25), 'Freelance',
                     rng.choice([2_500_000, 3_000_000, 4_500_000]), 'Proyek freelance')
        if rng.random() < 0.3 and not is_current:
            in_month(28, 'Investasi', rng.choice([500_000, 750_000]), 'Return investasi')

        # Pengeluaran rutin
        for _ in range(rng.randint(3, 4)):
            in_month(rng.randint(2, 26), 'Makanan', rng.randint(3, 9) * 50_000,
                     rng.choice(['Belanja mingguan', 'Makan bersama tim', 'Kopi & camilan', 'Groceries']))
        in_month(rng.randint(3, 10), 'Tagihan', rng.randint(8, 11) * 50_000, 'Listrik, air & internet')
        in_month(rng.randint(5, 12), 'Transportasi', rng.randint(4, 7) * 50_000, 'Bensin & parkir')
        if rng.random() < 0.8:
            in_month(rng.randint(12, 26), 'Transportasi', rng.randint(2, 4) * 50_000, 'Ojek online')
        if rng.random() < 0.6:
            in_month(rng.randint(10, 27), 'Belanja', rng.randint(15, 40) * 50_000,
                     rng.choice(['Belanja pakaian', 'Perawatan rumah', 'Kebutuhan elektronik']))
        for _ in range(rng.randint(2, 3)):
            in_month(rng.randint(3, 27), 'Hiburan', rng.randint(2, 12) * 25_000,
                     rng.choice(['Nonton film', 'Langganan streaming', 'Nongkrong', 'Kafe']))
        if rng.random() < 0.35:
            in_month(rng.randint(5, 25), 'Kesehatan', rng.randint(2, 8) * 50_000,
                     rng.choice(['Apotek', 'Konsultasi dokter']))
        if i % 2 == 0:
            in_month(rng.randint(14, 27), 'Pendidikan', rng.randint(3, 6) * 50_000, 'Kursus & buku')

        # Agar notifikasi demo selalu hidup pada bulan berjalan
        if is_current:
            if today.day >= 3:
                in_month(3, 'Hiburan', 350_000, 'Konser & nonton film')
            if today.day >= 4:
                in_month(4, 'Tagihan', 1_050_000, 'Listrik, air & internet')
            if today.day >= 6:
                in_month(6, 'Hiburan', 250_000, 'Langganan streaming')

    for d, cat_name, amount, desc in txs:
        Transaction.objects.create(
            category=categories[cat_name],
            type=categories[cat_name].type,
            amount=amount,
            description=desc,
            date=d,
        )

    for cat, limit in [
        ('Makanan', 2_500_000),
        ('Transportasi', 900_000),
        ('Belanja', 1_500_000),
        ('Hiburan', 700_000),
        ('Tagihan', 1_200_000),
    ]:
        Budget.objects.create(category=categories[cat], monthly_limit=limit)

    from datetime import timedelta

    def months_from_now(n):
        d = today + timedelta(days=30 * n)
        return d.replace(day=min(d.day, 28))

    Goal.objects.create(
        name='Dana Darurat', target_amount=30_000_000, current_amount=21_500_000,
        deadline=months_from_now(8),
    )
    Goal.objects.create(
        name='Liburan Akhir Tahun', target_amount=12_000_000, current_amount=8_400_000,
        deadline=months_from_now(3),
    )
    Goal.objects.create(
        name='Laptop Kerja Baru', target_amount=20_000_000, current_amount=17_800_000,
        deadline=months_from_now(2),
    )
    return True
