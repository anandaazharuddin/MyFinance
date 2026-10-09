from django import template

from finance.utils import format_date_short, format_idr

register = template.Library()


@register.filter
def idr(value):
    """Format angka sebagai Rupiah, mis. 1500000 -> 'Rp 1.500.000'."""
    return format_idr(value)


@register.filter
def id_date(value):
    """Format tanggal pendek berlabel Indonesia, mis. 7 Okt 2026."""
    return format_date_short(value)
