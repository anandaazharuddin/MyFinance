"""Entry point eksplisit untuk Vercel Python runtime.

Dokumen resmi Vercel: entry point Python dicari di file root bernama
`app.py`, `index.py`, `server.py`, `main.py`, `wsgi.py`, atau `asgi.py`
yang mendefinisikan nama top-level `application` (untuk WSGI/Django).

File ini hanya meneruskan ke aplikasi WSGI asli (config.wsgi), sehingga
perilakunya identik dengan auto-detection Django via manage.py, tapi
tersaji secara eksplisit sebagai cadangan jika deteksi framework
tidak berjalan.
"""
from config.wsgi import application  # noqa: F401
