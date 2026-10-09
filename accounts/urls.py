from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    # 2FA biometrik (setelah PIN benar)
    path('verify/', views.webauthn_verify, name='webauthn_verify'),
    # Akun & Keamanan
    path('account/', views.account, name='account'),
    path('account/change-pin/', views.change_pin, name='change_pin'),
    # WebAuthn: pendaftaran kredensial biometrik
    path('account/webauthn/register/start/', views.webauthn_register_start, name='wa_register_start'),
    path('account/webauthn/register/finish/', views.webauthn_register_finish, name='wa_register_finish'),
    path('account/webauthn/credentials/<int:pk>/delete/', views.webauthn_credential_delete, name='wa_credential_delete'),
]
