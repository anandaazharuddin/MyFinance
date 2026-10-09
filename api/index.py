"""Wrapper WSGI untuk Vercel serverless function.

Vercel menjalankan Django sebagai function (lihat "functions" di vercel.json).
File ini meneruskan semua request ke aplikasi WSGI MyFinance.
"""
import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()


def handler(environ, start_response):
    return application(environ, start_response)
