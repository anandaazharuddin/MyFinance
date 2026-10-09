from django.core.management.base import BaseCommand

from finance.seeding import run_seed
from finance.models import Budget, Goal, Transaction


class Command(BaseCommand):
    help = 'Isi database dengan data contoh MyFinance (hanya jika masih kosong).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force', action='store_true',
            help='Hapus transaksi, anggaran, dan tujuan yang ada terlebih dahulu.',
        )

    def handle(self, *args, **options):
        if options['force']:
            Transaction.objects.all().delete()
            Goal.objects.all().delete()
            Budget.objects.all().delete()
            self.stdout.write('Data lama dihapus.')
        if run_seed():
            self.stdout.write(self.style.SUCCESS('Data contoh MyFinance berhasil dimuat.'))
        else:
            self.stdout.write(
                'Database sudah berisi data — data contoh dilewati '
                '(gunakan --force untuk menggantinya).'
            )
