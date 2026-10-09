import re

from django import forms

PIN_RE = re.compile(r'^\d{6}$')

PIN_WIDGET_ATTRS = {
    'autocomplete': 'new-password',
    'inputmode': 'numeric',
    'maxlength': '6',
    'placeholder': '••••••',
}


def _validate_pin(value):
    pin = (value or '').strip()
    if not PIN_RE.match(pin):
        raise forms.ValidationError('PIN harus tepat 6 digit angka.')
    return pin


class PinLoginForm(forms.Form):
    """Form login website: nama pengguna + PIN 6 digit."""

    username = forms.CharField(
        label='Nama Pengguna',
        widget=forms.TextInput(attrs={
            'autofocus': True,
            'autocomplete': 'username',
            'placeholder': 'anandaazhar',
        }),
    )
    pin = forms.CharField(
        label='PIN',
        strip=False,
        widget=forms.PasswordInput(attrs={
            **PIN_WIDGET_ATTRS,
            'autocomplete': 'current-password',
            'class': 'pin-input',
        }),
    )

    def clean_pin(self):
        return _validate_pin(self.cleaned_data['pin'])


class ChangePinForm(forms.Form):
    """Ganti PIN dari halaman Akun & Keamanan."""

    old_pin = forms.CharField(
        label='PIN saat ini',
        strip=False,
        widget=forms.PasswordInput(attrs={**PIN_WIDGET_ATTRS, 'autocomplete': 'current-password'}),
    )
    new_pin = forms.CharField(
        label='PIN baru',
        strip=False,
        widget=forms.PasswordInput(attrs=PIN_WIDGET_ATTRS),
    )
    new_pin2 = forms.CharField(
        label='Ulangi PIN baru',
        strip=False,
        widget=forms.PasswordInput(attrs=PIN_WIDGET_ATTRS),
    )

    def __init__(self, user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_old_pin(self):
        return _validate_pin(self.cleaned_data['old_pin'])

    def clean_new_pin(self):
        return _validate_pin(self.cleaned_data['new_pin'])

    def clean_new_pin2(self):
        return _validate_pin(self.cleaned_data['new_pin2'])

    def clean(self):
        cleaned = super().clean()
        old = cleaned.get('old_pin')
        new = cleaned.get('new_pin')
        new2 = cleaned.get('new_pin2')
        if old and self.user and not self.user.check_password(old):
            self.add_error('old_pin', 'PIN saat ini salah.')
        if new and new == old:
            self.add_error('new_pin', 'PIN baru tidak boleh sama dengan PIN lama.')
        if new and new2 and new != new2:
            self.add_error('new_pin2', 'Konfirmasi PIN baru tidak cocok.')
        return cleaned



