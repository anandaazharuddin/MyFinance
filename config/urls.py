from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

urlpatterns = [
    # Login/PIN, verifikasi biometrik, halaman akun (URL: /login/, /verify/, /account/, ...)
    path('', include('accounts.urls')),
    # Halaman utama: landing (publik) + dasbor (wajib login, khusus pemilik).
    path('', include('finance.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
