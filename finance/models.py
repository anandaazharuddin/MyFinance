from django.db import models


class Category(models.Model):
    INCOME = 'income'
    EXPENSE = 'expense'
    TYPE_CHOICES = ((INCOME, 'Pemasukan'), (EXPENSE, 'Pengeluaran'))

    name = models.CharField('nama', max_length=60, unique=True)
    type = models.CharField('jenis', max_length=10, choices=TYPE_CHOICES, default=EXPENSE)
    icon = models.CharField('ikon', max_length=16, default='💳')
    color = models.CharField('warna', max_length=9, default='#16a34a')
    # Kategori "sekali pakai" (dipakai bot Telegram saat kamu memilih
    # "hanya bulan ini"): valid_until diisi akhir bulan berjalan, lalu
    # telegram_bot.purge_expired_temporary_categories() menghapusnya —
    # transaksinya dipindah ke kategori cadangan ('Lainnya'/'Lain-lain').
    temporary = models.BooleanField(
        'hanya bulan ini',
        default=False,
        help_text='Kategori sementara yang dihapus otomatis saat bulan berakhir.',
    )
    valid_until = models.DateField('berlaku sampai', null=True, blank=True)

    class Meta:
        verbose_name = 'kategori'
        verbose_name_plural = 'kategori'
        ordering = ['type', 'name']

    def __str__(self):
        return self.name


class Transaction(models.Model):
    INCOME = 'income'
    EXPENSE = 'expense'
    TYPE_CHOICES = ((INCOME, 'Pemasukan'), (EXPENSE, 'Pengeluaran'))

    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name='transactions', verbose_name='kategori'
    )
    type = models.CharField('jenis', max_length=10, choices=TYPE_CHOICES, default=EXPENSE)
    amount = models.DecimalField('jumlah', max_digits=15, decimal_places=2)
    description = models.CharField('keterangan', max_length=200, blank=True)
    date = models.DateField('tanggal')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'transaksi'
        verbose_name_plural = 'transaksi'
        ordering = ['-date', '-id']

    def __str__(self):
        return f'{self.get_type_display()} — {self.category.name}'


class Budget(models.Model):
    category = models.OneToOneField(
        Category, on_delete=models.CASCADE, related_name='budget', verbose_name='kategori'
    )
    monthly_limit = models.DecimalField('batas bulanan', max_digits=15, decimal_places=2)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'anggaran'
        verbose_name_plural = 'anggaran'
        ordering = ['category__name']

    def __str__(self):
        return f'{self.category.name} — {self.monthly_limit}'


class Goal(models.Model):
    name = models.CharField('nama tujuan', max_length=120)
    target_amount = models.DecimalField('target', max_digits=15, decimal_places=2)
    current_amount = models.DecimalField('terkumpul', max_digits=15, decimal_places=2, default=0)
    deadline = models.DateField('target waktu', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'tujuan keuangan'
        verbose_name_plural = 'tujuan keuangan'
        ordering = ['deadline', 'name']

    def __str__(self):
        return self.name

    @property
    def progress(self):
        if not self.target_amount:
            return 0
        return min(self.current_amount / self.target_amount, 1.0)


# ---------------------------------------------------------------------------
# Integrasi bot Telegram (state & konfirmasi kategori)
# ---------------------------------------------------------------------------

class TelegramBotState(models.Model):
    """State tunggal integrasi bot Telegram (baris tunggal, pk=1).

    - last_update_id : offset getUpdates (update <= id ini sudah diproses).
    - last_chat_*    : chat terakhir yang mengirim pesan — dipakai web untuk
                       memandu verifikasi TELEGRAM_ALLOWED_CHAT_IDS.
    - me_username    : hasil getMe (verifikasi token), di-cache 6 jam.
    """

    last_update_id = models.IntegerField(default=0)
    last_chat_id = models.BigIntegerField(null=True, blank=True)
    last_chat_name = models.CharField('nama chat terakhir', max_length=120, blank=True, default='')
    me_username = models.CharField(max_length=64, blank=True, default='')
    me_checked_at = models.DateTimeField(null=True, blank=True)
    last_activity = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'state bot telegram'
        verbose_name_plural = 'state bot telegram'

    def __str__(self):
        return f'TelegramBotState(offset={self.last_update_id})'


class TelegramPendingCategory(models.Model):
    """Kategori baru dari Telegram yang masih MENUNGGU konfirmasi kamu.

    Bot tidak pernah membuat kategori tanpa izin: pesan transaksi dengan
    kategori belum ada disimpan di sini dulu, lalu kamu memilih
    (1) simpan untuk seterusnya, (2) hanya bulan ini, atau (3) batal —
    agar kategori random tidak menumpuk di database.
    """

    chat_id = models.BigIntegerField()
    category_name = models.CharField('nama kategori', max_length=60)
    tx_type = models.CharField('jenis', max_length=10, choices=Transaction.TYPE_CHOICES)
    amount = models.DecimalField('jumlah', max_digits=15, decimal_places=2)
    tx_date = models.DateField('tanggal transaksi')
    # Tahap tanya "simpan" sudah dilewati & menunggu angka batas bulanan
    # (khusus kategori pengeluaran). Income tidak punya anggaran.
    awaiting_budget = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField('kadaluarsa')

    class Meta:
        verbose_name = 'konfirmasi kategori telegram'
        verbose_name_plural = 'konfirmasi kategori telegram'
        ordering = ['-created_at']

    def __str__(self):
        return f'Tanya kategori "{self.category_name}" (chat {self.chat_id})'
