/* MyFinance — verify.js
   Langkah 2FA biometrik: memanggil WebAuthn (sidik jari / Face ID di HP),
   lalu mengirim assertion ke server untuk diverifikasi. */
(function () {
  'use strict';

  var btn = document.getElementById('verify-btn');
  var statusEl = document.getElementById('verify-status');
  var dataEl = document.getElementById('wa-data');
  if (!btn || !dataEl) return;

  var options;
  try {
    options = JSON.parse(dataEl.textContent);
  } catch (e) {
    options = null;
  }
  var csrf = document.querySelector('meta[name="csrf-token"]');

  /* ---------- util base64url <-> Uint8Array ---------- */
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
    statusEl.className = 'verify-status' + (tone ? ' verify-status--' + tone : '');
  }

  if (!window.PublicKeyCredential) {
    setStatus('Perangkat atau browser ini tidak mendukung biometrik WebAuthn. ' +
      'Gunakan browser modern di HP (Chrome/Safari) dan https untuk login dengan sidik jari.', 'error');
    btn.disabled = true;
    return;
  }
  if (!options) {
    setStatus('Opsi verifikasi tidak tersedia. Silakan login ulang.', 'error');
    btn.disabled = true;
    return;
  }

  btn.addEventListener('click', function () {
    btn.disabled = true;
    setStatus('Menunggu sidik jari / Face ID di perangkat kamu…', 'info');

    /* Salin opsi lalu ubah field base64url menjadi Uint8Array (syarat WebAuthn). */
    var pk = JSON.parse(JSON.stringify(options));
    if (pk.challenge) pk.challenge = b64uToBytes(pk.challenge);
    (pk.allowCredentials || []).forEach(function (c) {
      c.id = b64uToBytes(c.id);
    });

    navigator.credentials.get({ publicKey: pk })
      .then(function (cred) {
        setStatus('Memverifikasi di server…', 'info');
        var assertion = {
          id: cred.id,
          rawId: bytesToB64u(cred.rawId),
          type: cred.type,
          response: {
            clientDataJSON: bytesToB64u(cred.response.clientDataJSON),
            authenticatorData: bytesToB64u(cred.response.authenticatorData),
            signature: bytesToB64u(cred.response.signature)
          }
        };
        if (cred.response.userHandle) {
          assertion.response.userHandle = bytesToB64u(cred.response.userHandle);
        }
        return fetch(window.location.pathname, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrf ? csrf.content : ''
          },
          body: JSON.stringify({ assertion: assertion })
        });
      })
      .then(function (resp) {
        if (resp.ok && resp.headers.get('content-type').indexOf('json') !== -1) {
          return resp.json().then(function (j) {
            if (j && j.ok) {
              setStatus('Berhasil! Mengalihkan…', 'ok');
              window.location.href = j.redirect || '/dashboard/';
            } else {
              window.location.reload(); /* server kirim ulang halaman dgn challenge baru */
            }
          });
        }
        /* Respons HTML = server tampilkan ulang halaman (challenge baru + pesan error). */
        window.location.reload();
      })
      .catch(function (err) {
        var msg = (err && err.name === 'NotAllowedError')
          ? 'Sidik jari dibatalkan. Coba lagi.'
          : 'Gagal: ' + (err && err.message ? err.message : 'kesalahan tidak diketahui');
        setStatus(msg, 'error');
        btn.disabled = false;
      });
  });
})();
