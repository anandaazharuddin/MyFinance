/* MyFinance — biometric.js
   Pendaftaran kredensial WebAuthn dari halaman Akun & Keamanan.
   (Pencocokan aslinya terjadi di perangkat: HP meminta sidik jari.) */
(function () {
  'use strict';

  var csrf = document.querySelector('meta[name="csrf-token"]');
  var enrollBtn = document.getElementById('wa-enroll');
  var statusEl = document.getElementById('wa-status');
  if (!enrollBtn) return;

  function b64uToBytes(s) {
    var p = s.replace(/-/g, '+').replace(/_/g, '/');
    while (p.length % 4) p += '=';
    var raw = window.atob(p);
    var out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
  }
  function bytesToB64u(buf) {
    var bytes = new Uint8Array(buf);
    var raw = '';
    for (var i = 0; i < bytes.length; i++) raw += String.fromCharCode(bytes[i]);
    return window.btoa(raw).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }
  function setStatus(msg, tone) {
    if (!statusEl) return;
    statusEl.textContent = msg || '';
    statusEl.className = 'biometric__status' + (tone ? ' biometric__status--' + tone : '');
  }

  if (!window.PublicKeyCredential) {
    setStatus('Perangkat/browser ini tidak mendukung WebAuthn. Gunakan browser modern di HP ' +
      '(Chrome/Safari) dan buka lewat https.', 'error');
    enrollBtn.disabled = true;
    return;
  }

  enrollBtn.addEventListener('click', function () {
    enrollBtn.disabled = true;
    setStatus('Menyiapkan permintaan ke perangkat…', 'info');

    fetch('/account/webauthn/register/start/', {
      method: 'POST',
      headers: { 'X-CSRFToken': csrf ? csrf.content : '' }
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.ok) throw new Error(data.message || 'Gagal memulai pendaftaran.');
        var pk = data.publicKey;
        if (pk.challenge) pk.challenge = b64uToBytes(pk.challenge);
        if (pk.user && pk.user.id) pk.user.id = b64uToBytes(pk.user.id);
        (pk.excludeCredentials || []).forEach(function (c) { c.id = b64uToBytes(c.id); });
        return navigator.credentials.create({ publicKey: pk });
      })
      .then(function (cred) {
        setStatus('Memverifikasi sidik jari di server…', 'info');
        var payload = {
          id: cred.id,
          rawId: bytesToB64u(cred.rawId),
          type: cred.type,
          response: {
            clientDataJSON: bytesToB64u(cred.response.clientDataJSON),
            attestationObject: bytesToB64u(cred.response.attestationObject)
          }
        };
        return fetch('/account/webauthn/register/finish/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrf ? csrf.content : ''
          },
          body: JSON.stringify({ credential: payload })
        });
      })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (j.ok) {
          setStatus(j.message || 'Berhasil didaftarkan.', 'ok');
          setTimeout(function () { window.location.reload(); }, 1100);
        } else {
          throw new Error(j.message || 'Pendaftaran gagal.');
        }
      })
      .catch(function (err) {
        var msg = (err && err.name === 'NotAllowedError')
          ? 'Pendaftaran dibatalkan di perangkat.'
          : (err && err.message ? err.message : 'Pendaftaran gagal.');
        setStatus(msg, 'error');
        enrollBtn.disabled = false;
      });
  });

  /* Hapus kredensial */
  document.querySelectorAll('[data-delete-cred]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      if (!window.confirm('Hapus autentikator ini?\n\nSetelah dihapus, akun kembali masuk ' +
        'cukup dengan PIN (tanpa sidik jari) sampai ada perangkat baru terdaftar.')) return;
      fetch(btn.dataset.deleteCred, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf ? csrf.content : '' }
      })
        .then(function (r) { return r.json(); })
        .then(function (j) {
          if (j.ok) window.location.reload();
          else window.alert(j.message || 'Gagal menghapus.');
        });
    });
  });
})();
