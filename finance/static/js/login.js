/* MyFinance — login.js
   Micro-interactions halaman login: toggle kata sandi,
   fokus awal, dan animasi error. */
(function () {
  'use strict';

  /* Toggle tampilkan/sembunyikan PIN/kata sandi */
  var toggle = document.getElementById('pw-toggle');
  var pw = document.getElementById('id_pin') || document.getElementById('id_password');
  if (toggle && pw) {
    toggle.addEventListener('click', function () {
      var shown = pw.type === 'password';
      pw.type = shown ? 'text' : 'password';
      toggle.classList.toggle('is-shown', shown);
      toggle.setAttribute('aria-label', shown ? 'Sembunyikan kata sandi' : 'Tampilkan kata sandi');
      pw.focus({ preventScroll: true });
    });
  }

  /* Fokus awal ke nama pengguna (jika masih kosong) */
  var username = document.getElementById('id_username');
  if (username && !username.value) {
    setTimeout(function () { username.focus({ preventScroll: true }); }, 450);
  }
})();
