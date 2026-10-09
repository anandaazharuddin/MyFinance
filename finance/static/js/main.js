/* ============================================================
   MyFinance — main.js
   Micro-interactions: sidebar, dropdown, modal, count-up,
   progress, toast, fetch mutations. Subtle & cepat.
   ============================================================ */
(function () {
  'use strict';

  var $ = function (s, el) { return (el || document).querySelector(s); };
  var $$ = function (s, el) { return Array.prototype.slice.call((el || document).querySelectorAll(s)); };

  var MF_DATA = (function () {
    var el = document.getElementById('mf-data');
    if (!el) return {};
    try { return JSON.parse(el.textContent); } catch (e) { return {}; }
  })();
  var PAGE = MF_DATA.page || '';
  var CSRF = (document.querySelector('meta[name="csrf-token"]') || {}).content || '';
  var REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- Format ---------- */
  function fmtIDR(value) {
    var v = Math.round(Math.abs(Number(value) || 0));
    return 'Rp ' + v.toLocaleString('id-ID');
  }
  function fmtSignedIDR(value) {
    var v = Number(value) || 0;
    return (v < 0 ? '−' : '') + fmtIDR(v);
  }
  function fmtPct(value) {
    return (Number(value) || 0).toLocaleString('id-ID', { maximumFractionDigits: 1 }) + '%';
  }

  /* ---------- Sidebar (drawer mobile) ---------- */
  var menuToggle = $('#menu-toggle');
  var overlay = $('#sidebar-overlay');
  function setSidebar(open) {
    document.body.classList.toggle('sidebar-open', open);
  }
  if (menuToggle) {
    menuToggle.addEventListener('click', function () {
      setSidebar(!document.body.classList.contains('sidebar-open'));
    });
  }
  if (overlay) overlay.addEventListener('click', function () { setSidebar(false); });

  /* ---------- Dropdown ---------- */
  $$('.dropdown').forEach(function (dd) {
    var toggle = dd.querySelector('[data-dropdown-toggle]');
    if (!toggle) return;
    toggle.addEventListener('click', function (e) {
      e.stopPropagation();
      var wasOpen = dd.classList.contains('is-open');
      closeAllDropdowns();
      if (!wasOpen) {
        dd.classList.add('is-open');
        toggle.setAttribute('aria-expanded', 'true');
      }
    });
  });
  function closeAllDropdowns() {
    $$('.dropdown.is-open').forEach(function (dd) {
      dd.classList.remove('is-open');
      var t = dd.querySelector('[data-dropdown-toggle]');
      if (t) t.setAttribute('aria-expanded', 'false');
    });
  }
  document.addEventListener('click', function (e) {
    if (!e.target.closest('.dropdown')) closeAllDropdowns();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      closeAllDropdowns();
      $$('.modal.is-open').forEach(closeModal);
    }
  });

  /* ---------- Modal ---------- */
  var lastFocus = null;
  function openModal(id) {
    var m = document.getElementById(id);
    if (!m) return;
    lastFocus = document.activeElement;
    m.classList.add('is-open');
    m.setAttribute('aria-hidden', 'false');
    document.body.classList.add('modal-open');
    var focusEl = m.querySelector('input:not([type=hidden]), select, button.btn-primary');
    if (focusEl) {
      setTimeout(function () { focusEl.focus({ preventScroll: true }); }, 120);
    }
  }
  function closeModal(m) {
    if (!m || !m.classList.contains('is-open')) return;
    m.classList.remove('is-open');
    m.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('modal-open');
    if (lastFocus && typeof lastFocus.focus === 'function') {
      lastFocus.focus({ preventScroll: true });
    }
  }
  $$('[data-open]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var id = btn.dataset.open;
      var prefill = btn.dataset.prefill;
      if (id === 'budget-modal' && prefill) {
        openBudgetModal(null, JSON.parse(prefill));
      } else if (id === 'budget-modal') {
        openBudgetModal(null);
      } else if (id === 'contribute-modal') {
        openContributeModal(btn);
      } else {
        openModal(id);
      }
    });
  });
  $$('[data-close-modal]').forEach(function (el) {
    el.addEventListener('click', function () {
      closeModal(el.closest('.modal'));
    });
  });

  /* ---------- Toast ---------- */
  var TOAST_ICONS = {
    success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M8.5 12.5l2.5 2.5 4.5-5"/></svg>',
    danger: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v5"/><circle cx="12" cy="16.2" r=".4" fill="currentColor"/></svg>',
    info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><circle cx="12" cy="8" r=".4" fill="currentColor"/></svg>'
  };
  function toast(message, tone) {
    tone = tone || 'success';
    var stack = $('#toast-stack');
    if (!stack) return;
    var t = document.createElement('div');
    t.className = 'toast toast--' + tone;
    t.innerHTML = (TOAST_ICONS[tone] || TOAST_ICONS.success) + '<span></span>';
    t.querySelector('span').textContent = message;
    stack.appendChild(t);
    requestAnimationFrame(function () {
      requestAnimationFrame(function () { t.classList.add('is-show'); });
    });
    setTimeout(function () {
      t.classList.remove('is-show');
      t.classList.add('is-hide');
      setTimeout(function () { t.remove(); }, 320);
    }, 3400);
  }

  /* ---------- Confirm modal ---------- */
  var confirmResolver = null;
  function askConfirm(opts) {
    return new Promise(function (resolve) {
      confirmResolver = resolve;
      $('#confirm-title').textContent = opts.title || 'Yakin?';
      $('#confirm-text').textContent = opts.text || 'Tindakan ini tidak dapat dibatalkan.';
      $('#confirm-ok').textContent = opts.okLabel || 'Hapus';
      openModal('confirm-modal');
    });
  }
  function settleConfirm(value) {
    var r = confirmResolver;
    confirmResolver = null;
    closeModal($('#confirm-modal'));
    if (r) r(value);
  }
  var confirmOk = $('#confirm-ok');
  var confirmCancel = $('#confirm-cancel');
  if (confirmOk) confirmOk.addEventListener('click', function () { settleConfirm(true); });
  if (confirmCancel) confirmCancel.addEventListener('click', function () { settleConfirm(false); });

  /* ---------- Count-up angka ---------- */
  function formatValue(v, format) {
    if (format === 'pct') return fmtPct(v);
    return fmtSignedIDR(v);
  }
  function animateNumber(el, to, format) {
    to = Number(to) || 0;
    format = format || el.dataset.format || 'idr';
    if (REDUCED) {
      el.textContent = formatValue(to, format);
      el._val = to;
      return;
    }
    var from = Number(el._val || 0);
    var dur = 750;
    var t0 = null;
    el._val = to;
    function frame(t) {
      if (t0 === null) t0 = t;
      var p = Math.min((t - t0) / dur, 1);
      var e = 1 - Math.pow(1 - p, 3); /* easeOutCubic */
      el.textContent = formatValue(from + (to - from) * e, format);
      if (p < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }
  function refreshStats(stats) {
    if (!stats) return;
    ['balance', 'income_mtd', 'expense_mtd', 'savings_rate'].forEach(function (key) {
      var s = stats[key];
      if (!s) return;
      var el = document.querySelector('[data-stat="' + key + '"]');
      if (el) animateNumber(el, s.value, el.dataset.format || 'idr');
      var d = document.querySelector('[data-stat-delta="' + key + '"]');
      if (d && s.delta_text) {
        d.textContent = s.delta_text;
        d.className = 'stat-card__delta delta--' + (s.delta_tone || 'neutral');
      }
    });
  }

  /* ---------- Progress bars & rings ---------- */
  function animateProgress(scope) {
    $$('[data-progress]', scope || document).forEach(function (el) {
      var pct = Math.min(Math.max(Number(el.dataset.progress) || 0, 0), 100);
      requestAnimationFrame(function () {
        requestAnimationFrame(function () { el.style.width = pct + '%'; });
      });
    });
  }
  function animateRings(scope) {
    var C = 2 * Math.PI * 19; /* r=19 */
    $$('[data-ring]', scope || document).forEach(function (el) {
      var p = Math.min(Math.max(Number(el.dataset.ring) || 0, 0), 1);
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          el.style.strokeDashoffset = String(C * (1 - p));
        });
      });
    });
  }

  /* ---------- Fetch helper ---------- */
  function toLogin() {
    window.location.href = '/login/?next=' + encodeURIComponent(window.location.pathname + window.location.search);
  }
  async function post(url, formData) {
    var res = await fetch(url, {
      method: 'POST',
      headers: { 'X-CSRFToken': CSRF, 'Accept': 'application/json' },
      body: formData
    });
    if (res.status === 401) { toLogin(); return { ok: false, data: {} }; }
    var data = {};
    try { data = await res.json(); } catch (e) { /* noop */ }
    return { ok: res.ok && data.ok !== false, data: data };
  }
  function setBusy(btn, busy) {
    if (!btn) return;
    btn.disabled = busy;
    btn.style.opacity = busy ? '.65' : '';
  }
  function showErrors(box, errors) {
    if (!box) return;
    if (!errors) { box.hidden = true; box.innerHTML = ''; return; }
    var msgs = [];
    Object.keys(errors).forEach(function (k) {
      (errors[k] || []).forEach(function (m) { msgs.push(m); });
    });
    box.innerHTML = '<ul></ul>';
    msgs.forEach(function (m) {
      var li = document.createElement('li');
      li.textContent = m;
      box.querySelector('ul').appendChild(li);
    });
    box.hidden = false;
  }

  /* ---------- Baris transaksi (template) ---------- */
  function buildTxRow(tx) {
    var tpl = document.getElementById('tpl-tx');
    if (!tpl) return null;
    var li = tpl.content.firstElementChild.cloneNode(true);
    li.dataset.id = tx.id;
    var icon = li.querySelector('.tx__icon');
    icon.style.setProperty('--c', tx.category.color || '#64748b');
    icon.textContent = tx.category.icon || '💳';
    li.querySelector('.tx__desc').textContent = tx.description || tx.category.name;
    li.querySelector('.tx__meta').textContent = (tx.category.name || '') + ' · ' + (tx.date_label || '');
    var amt = li.querySelector('.tx__amount');
    amt.textContent = (tx.type === 'income' ? '+' : '−') + fmtIDR(tx.amount);
    amt.classList.add(tx.type === 'income' ? 'is-income' : 'is-expense');
    var del = li.querySelector('[data-delete-tx]');
    del.dataset.deleteTx = tx.id;
    return li;
  }
  function prependTx(tx) {
    var list = $('#tx-list');
    if (!list) return;
    var row = buildTxRow(tx);
    if (!row) return;
    var emptyNote = list.querySelector('.empty-note');
    if (emptyNote) emptyNote.remove();
    list.prepend(row);
    /* batasi panjang list di dasbor */
    if (PAGE === 'dashboard' && list.children.length > 8) {
      list.lastElementChild.remove();
    }
  }
  function removeTxRow(id) {
    var row = document.querySelector('.tx[data-id="' + id + '"]');
    if (!row) return;
    row.classList.add('tx--leaving');
    setTimeout(function () {
      row.remove();
      var list = row.closest('.tx-list');
      if (list && !list.querySelector('.tx')) {
        var note = document.createElement('li');
        note.className = 'empty-note empty-note--center';
        note.textContent = 'Tidak ada transaksi untuk filter ini.';
        list.appendChild(note);
      }
    }, 200);
  }

  /* ---------- Ringkasan halaman transaksi ---------- */
  async function refreshTxSummary() {
    if (PAGE !== 'transactions') return;
    var params = new URLSearchParams(location.search);
    var res = await fetch('/api/transactions/summary/?' + params.toString(), { headers: { 'Accept': 'application/json' } });
    if (res.status === 401) { toLogin(); return; }
    var s = await res.json();
    var map = {
      income: s.income_label,
      expense: s.expense_label,
      net: s.net_label,
      count: String(s.count)
    };
    Object.keys(map).forEach(function (k) {
      var el = document.querySelector('[data-summary="' + k + '"]');
      if (el) el.textContent = map[k];
    });
  }
  function matchesCurrentFilter(tx) {
    var params = new URLSearchParams(location.search);
    var t = params.get('type');
    var m = params.get('month');
    if (t && tx.type !== t) return false;
    if (m && (tx.date || '').slice(0, 7) !== m) return false;
    return true;
  }

  /* ---------- Form transaksi ---------- */
  var txForm = $('#tx-form');
  var txCategory = $('#tx-category');
  var txDate = $('#tx-date');

  function syncCategoryOptions() {
    if (!txCategory) return;
    var type = (txForm.querySelector('input[name="type"]:checked') || {}).value || 'expense';
    var selected = txCategory.value;
    var firstValid = null;
    $$('option', txCategory).forEach(function (opt) {
      var match = opt.dataset.type === type;
      opt.hidden = !match;
      if (match && !firstValid) firstValid = opt.value;
    });
    if (firstValid && (!selected || txCategory.querySelector('option:checked').hidden)) {
      txCategory.value = firstValid;
    }
  }
  if (txForm) {
    $$('input[name="type"]', txForm).forEach(function (r) {
      r.addEventListener('change', syncCategoryOptions);
    });
    syncCategoryOptions();

    txForm.addEventListener('submit', async function (e) {
      e.preventDefault();
      if (!txForm.reportValidity()) return;
      var btn = txForm.querySelector('[type="submit"]');
      setBusy(btn, true);
      var out = await post('/api/transactions/', new FormData(txForm));
      setBusy(btn, false);
      if (!out.ok) {
        showErrors($('#tx-errors'), out.data.errors);
        return;
      }
      showErrors($('#tx-errors'), null);
      toast(out.data.message, 'success');
      if (matchesCurrentFilter(out.data.tx) || PAGE === 'dashboard') {
        prependTx(out.data.tx);
      }
      refreshStats(out.data.stats);
      refreshTxSummary();
      txForm.reset();
      txDate.value = new Date().toISOString().slice(0, 10);
      syncCategoryOptions();
      closeModal($('#tx-modal'));
    });
  }

  /* ---------- Kategori baru (inline di form transaksi) ---------- */
  function currentTxType() {
    if (!txForm) return 'expense';
    var r = txForm.querySelector('input[name="type"]:checked');
    return (r && r.value) || 'expense';
  }
  var txCatNewToggle = $('#tx-cat-new-toggle');
  var txCatNew = $('#tx-cat-new');
  var txCatNewType = $('#tx-cat-new-type');
  function syncNewCatType() {
    if (txCatNewType) {
      txCatNewType.textContent = currentTxType() === 'income' ? 'Pemasukan' : 'Pengeluaran';
    }
  }
  if (txCatNewToggle && txCatNew) {
    syncNewCatType();
    if (txForm) {
      txForm.addEventListener('change', function (e) {
        if (e.target && e.target.name === 'type') syncNewCatType();
      });
    }
    txCatNewToggle.addEventListener('click', function () {
      var show = txCatNew.hidden;
      txCatNew.hidden = !show;
      txCatNewToggle.setAttribute('aria-expanded', show ? 'true' : 'false');
      if (show) {
        var n = $('#tx-cat-name');
        if (n) n.focus();
      }
    });
    var catCancel = $('#tx-cat-new-cancel');
    if (catCancel) {
      catCancel.addEventListener('click', function () {
        txCatNew.hidden = true;
        txCatNewToggle.setAttribute('aria-expanded', 'false');
      });
    }
    var catSave = $('#tx-cat-new-save');
    if (catSave) {
      catSave.addEventListener('click', async function () {
        var nameEl = $('#tx-cat-name');
        var name = nameEl ? nameEl.value.trim() : '';
        if (!name) { if (nameEl) nameEl.focus(); return; }
        setBusy(catSave, true);
        var fd = new FormData();
        fd.append('name', name);
        fd.append('type', currentTxType());
        var iconEl = $('#tx-cat-icon');
        var colorEl = $('#tx-cat-color');
        fd.append('icon', (iconEl && iconEl.value) || '💳');
        fd.append('color', (colorEl && colorEl.value) || '#16a34a');
        var out = await post('/api/categories/', fd);
        setBusy(catSave, false);
        if (!out.ok) {
          showErrors($('#tx-cat-errors'), out.data.errors);
          return;
        }
        showErrors($('#tx-cat-errors'), null);
        var cat = out.data.category;
        if (txCategory && cat) {
          var opt = document.createElement('option');
          opt.value = String(cat.id);
          opt.dataset.type = cat.type;
          opt.textContent = (cat.icon ? cat.icon + ' ' : '') + cat.name;
          txCategory.appendChild(opt);
          txCategory.value = opt.value;
        }
        txCatNew.hidden = true;
        txCatNewToggle.setAttribute('aria-expanded', 'false');
        if (nameEl) nameEl.value = '';
        toast(out.data.message || 'Kategori baru berhasil dibuat.', 'success');
        var amt = $('#tx-amount');
        if (amt) amt.focus();
      });
    }
  }

  /* ---------- Hapus transaksi (delegated) ---------- */
  document.addEventListener('click', async function (e) {
    var btn = e.target.closest('[data-delete-tx]');
    if (!btn) return;
    var ok = await askConfirm({
      title: 'Hapus transaksi?',
      text: 'Transaksi ini akan dihapus permanen dari catatanmu.',
      okLabel: 'Hapus'
    });
    if (!ok) return;
    var out = await post('/api/transactions/' + btn.dataset.deleteTx + '/delete/', new FormData());
    if (out.ok) {
      removeTxRow(btn.dataset.deleteTx);
      refreshStats(out.data.stats);
      refreshTxSummary();
      toast(out.data.message, 'success');
    }
  });

  /* ---------- Kartu anggaran (template) ---------- */
  function fillBudgetCard(card, b) {
    card.dataset.budgetId = b.id;
    var icon = card.querySelector('.tx__icon');
    icon.style.setProperty('--c', b.color || '#64748b');
    icon.textContent = b.icon || '💳';
    card.querySelector('.budget-card__name').textContent = b.name;
    var chip = card.querySelector('.chip');
    chip.className = 'chip chip--' + b.state;
    chip.textContent = b.state_label;
    var monthEl = card.querySelector('.budget-card__month');
    if (monthEl) monthEl.textContent = b.month_label || MF_DATA.month_label || '';
    card.querySelector('.budget-card__spent').textContent = b.spent_label;
    card.querySelector('.budget-card__limit').textContent = 'dari ' + b.limit_label;
    var fill = card.querySelector('.progress__fill');
    fill.className = 'progress__fill progress__fill--' + b.state;
    fill.dataset.progress = b.pct;
    var prog = card.querySelector('.progress');
    if (prog) {
      prog.setAttribute('aria-valuenow', b.pct);
      prog.setAttribute('aria-label', 'Realisasi anggaran ' + b.name);
    }
    var remaining = card.querySelector('.budget-card__foot small');
    remaining.textContent = b.remaining_label;
    remaining.className = b.state === 'over' ? 'text-danger' : 'text-muted';
    var edit = card.querySelector('[data-edit-budget]');
    edit.dataset.editBudget = b.id;
    edit.dataset.categoryId = b.category_id;
    edit.dataset.limit = b.limit;
    var del = card.querySelector('[data-delete-budget]');
    del.dataset.deleteBudget = b.id;
    del.dataset.budgetName = b.name;
  }
  function buildBudgetCard(b) {
    var tpl = document.getElementById('tpl-budget');
    if (!tpl) return null;
    var card = tpl.content.firstElementChild.cloneNode(true);
    fillBudgetCard(card, b);
    return card;
  }
  function renderBudget(b) {
    var grid = $('.budget-grid');
    if (!grid) return;
    var existing = grid.querySelector('[data-budget-id="' + b.id + '"]');
    var card = buildBudgetCard(b);
    if (existing) {
      existing.replaceWith(card);
    } else {
      grid.prepend(card);
      var emptyCard = grid.querySelector('.empty-note-card');
      if (emptyCard) emptyCard.remove();
    }
    animateProgress(card);
  }
  function removeBudgetCard(id) {
    var card = $('.budget-grid [data-budget-id="' + id + '"]');
    if (!card) return;
    card.classList.add('tx--leaving');
    setTimeout(function () {
      card.remove();
      /* kembalikan ke daftar "tanpa anggaran" */
      var catId = card.querySelector('[data-delete-budget]').dataset.categoryId || '';
      addUnbudgetedChip(catId);
      if (!$('.budget-grid .budget-card')) {
        var grid = $('.budget-grid');
        var note = document.createElement('div');
        note.className = 'card empty-note-card';
        note.innerHTML = '<p class="empty-note">Belum ada anggaran bulanan.</p>';
        grid.appendChild(note);
      }
    }, 200);
  }
  function addUnbudgetedChip(categoryId) {
    var list = $('.unbudgeted__list');
    if (!list) return;
    var sel = $('#budget-category');
    var opt = sel && sel.querySelector('option[value="' + categoryId + '"]');
    if (!opt) return;
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'chip chip--clickable';
    btn.dataset.addBudget = categoryId;
    btn.title = 'Atur anggaran untuk ' + opt.textContent.trim();
    var icon = document.createElement('i');
    icon.className = 'tx__icon tx__icon--sm';
    var m = opt.textContent.match(/^\S+\s/);
    icon.textContent = m ? m[0].trim() : '💳';
    var plus = document.createElement('span');
    plus.className = 'chip__plus';
    plus.textContent = '+';
    btn.appendChild(icon);
    btn.appendChild(document.createTextNode(' ' + opt.textContent.trim().replace(/^\S+\s/, '')));
    btn.appendChild(plus);
    list.appendChild(btn);
  }

  /* ---------- Modal anggaran ---------- */
  function openBudgetModal(budgetId, prefill) {
    var form = $('#budget-form');
    if (!form) return;
    form.reset();
    showErrors($('#budget-errors'), null);
    $('#budget-id').value = budgetId || '';
    $('#budget-modal-title').textContent = budgetId ? 'Ubah Anggaran' : 'Tambah Anggaran';
    if (prefill) {
      if (prefill.categoryId) $('#budget-category').value = prefill.categoryId;
      if (prefill.limit) $('#budget-limit').value = prefill.limit;
    }
    openModal('budget-modal');
  }
  document.addEventListener('click', function (e) {
    var edit = e.target.closest('[data-edit-budget]');
    if (edit) {
      openBudgetModal(edit.dataset.editBudget, {
        categoryId: edit.dataset.categoryId,
        limit: edit.dataset.limit
      });
      return;
    }
    var add = e.target.closest('[data-add-budget]');
    if (add) openBudgetModal(null, { categoryId: add.dataset.addBudget });
  });

  var budgetForm = $('#budget-form');
  if (budgetForm) {
    budgetForm.addEventListener('submit', async function (e) {
      e.preventDefault();
      if (!budgetForm.reportValidity()) return;
      var btn = budgetForm.querySelector('[type="submit"]');
      setBusy(btn, true);
      var out = await post('/api/budgets/', new FormData(budgetForm));
      setBusy(btn, false);
      if (!out.ok) {
        showErrors($('#budget-errors'), out.data.errors);
        return;
      }
      renderBudget(out.data.budget);
      toast(out.data.message, 'success');
      closeModal($('#budget-modal'));
    });
  }
  document.addEventListener('click', async function (e) {
    var btn = e.target.closest('[data-delete-budget]');
    if (!btn) return;
    var ok = await askConfirm({
      title: 'Hapus anggaran ' + (btn.dataset.budgetName || '') + '?',
      text: 'Batas bulanan untuk kategori ini akan dihapus.',
      okLabel: 'Hapus'
    });
    if (!ok) return;
    var out = await post('/api/budgets/' + btn.dataset.deleteBudget + '/delete/', new FormData());
    if (out.ok) {
      removeBudgetCard(btn.dataset.deleteBudget);
      toast(out.data.message, 'success');
    }
  });

  /* ---------- Kartu tujuan (template) ---------- */
  function fillGoalCard(card, g) {
    card.dataset.goalId = g.id;
    if (g.done) card.classList.add('goal-card--done');
    var ring = card.querySelector('.ring__fill');
    ring.dataset.ring = g.ring_p;
    card.querySelector('.ring__label').textContent = g.pct + '%';
    card.querySelector('.goal-card__name').textContent = g.name;
    var amounts = card.querySelector('.goal-card__amounts');
    amounts.querySelector('b').textContent = g.current_label;
    amounts.querySelector('span').textContent = '/ ' + g.target_label;
    var meta = card.querySelector('.goal-card__meta');
    meta.innerHTML = '';
    if (g.done) {
      var chip = document.createElement('span');
      chip.className = 'chip chip--ok';
      chip.textContent = 'Tercapai 🎉';
      card.querySelector('.goal-card__top').appendChild(chip);
    }
    if (g.deadline_label) {
      var d = document.createElement('span');
      d.className = 'chip chip--info';
      d.textContent = '📅 ' + g.deadline_label;
      meta.appendChild(d);
    } else {
      var c2 = document.createElement('span');
      c2.className = 'chip';
      c2.textContent = 'Tanpa target waktu';
      meta.appendChild(c2);
    }
    var contrib = card.querySelector('[data-contribute]');
    contrib.dataset.contribute = g.id;
    contrib.dataset.goalName = g.name;
    contrib.dataset.remaining = g.remaining;
    contrib.dataset.remainingLabel = g.remaining_label;
    var del = card.querySelector('[data-delete-goal]');
    del.dataset.deleteGoal = g.id;
    del.dataset.goalName = g.name;
  }
  function renderGoal(g, prependIt) {
    var grid = $('.goal-grid');
    if (!grid) return;
    var tpl = document.getElementById('tpl-goal');
    if (!tpl) return;
    var card = tpl.content.firstElementChild.cloneNode(true);
    fillGoalCard(card, g);
    var emptyCard = grid.querySelector('.empty-note-card');
    if (emptyCard) emptyCard.remove();
    if (prependIt) grid.prepend(card); else grid.appendChild(card);
    animateRings(card);
  }
  function updateGoal(g) {
    var grid = $('.goal-grid');
    var existing = grid && grid.querySelector('[data-goal-id="' + g.id + '"]');
    if (!existing) { renderGoal(g, true); return; }
    existing.classList.toggle('goal-card--done', g.done);
    var ring = existing.querySelector('.ring__fill');
    ring.dataset.ring = g.ring_p;
    animateRings(existing);
    existing.querySelector('.ring__label').textContent = g.pct + '%';
    var amounts = existing.querySelector('.goal-card__amounts');
    amounts.querySelector('b').textContent = g.current_label;
    var contrib = existing.querySelector('[data-contribute]');
    contrib.dataset.remaining = g.remaining;
    contrib.dataset.remainingLabel = g.remaining_label;
    var top = existing.querySelector('.goal-card__top');
    if (g.done && !top.querySelector('.chip')) {
      var chip = document.createElement('span');
      chip.className = 'chip chip--ok';
      chip.textContent = 'Tercapai 🎉';
      top.appendChild(chip);
    }
  }

  /* ---------- Modal tujuan ---------- */
  var goalForm = $('#goal-form');
  if (goalForm) {
    goalForm.addEventListener('submit', async function (e) {
      e.preventDefault();
      if (!goalForm.reportValidity()) return;
      var btn = goalForm.querySelector('[type="submit"]');
      setBusy(btn, true);
      var out = await post('/api/goals/', new FormData(goalForm));
      setBusy(btn, false);
      if (!out.ok) {
        showErrors($('#goal-errors'), out.data.errors);
        return;
      }
      renderGoal(out.data.goal, false);
      toast(out.data.message, 'success');
      closeModal($('#goal-modal'));
    });
  }

  /* ---------- Modal kontribusi ---------- */
  function openContributeModal(btn) {
    var form = $('#contribute-form');
    if (!form) return;
    form.reset();
    showErrors($('#contribute-errors'), null);
    $('#contribute-context').textContent =
      btn.dataset.goalName + ' · sisa ' + (btn.dataset.remainingLabel || '');
    var hint = $('#contribute-hint');
    hint.textContent = Number(btn.dataset.remaining) > 0
      ? 'Maksimal ' + (btn.dataset.remainingLabel || '') + ' untuk mencapai target.'
      : 'Target sudah tercapai — tambahan akan dibatasi.';
    openModal('contribute-modal');
    /* simpan goal id lewat data button */
    form.dataset.goalId = btn.dataset.contribute;
  }
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-contribute]');
    if (btn) openContributeModal(btn);
  });

  var contributeForm = $('#contribute-form');
  if (contributeForm) {
    contributeForm.addEventListener('submit', async function (e) {
      e.preventDefault();
      if (!contributeForm.reportValidity()) return;
      var btn = contributeForm.querySelector('[type="submit"]');
      setBusy(btn, true);
      var goalId = contributeForm.dataset.goalId;
      var out = await post('/api/goals/' + goalId + '/contribute/', new FormData(contributeForm));
      setBusy(btn, false);
      if (!out.ok) {
        showErrors($('#contribute-errors'), out.data.errors);
        return;
      }
      updateGoal(out.data.goal);
      toast(out.data.message, 'success');
      closeModal($('#contribute-modal'));
    });
  }

  /* ---------- Hapus tujuan ---------- */
  document.addEventListener('click', async function (e) {
    var btn = e.target.closest('[data-delete-goal]');
    if (!btn) return;
    var ok = await askConfirm({
      title: 'Hapus tujuan ' + (btn.dataset.goalName || '') + '?',
      text: 'Progres yang tersimpan akan ikut terhapus.',
      okLabel: 'Hapus'
    });
    if (!ok) return;
    var out = await post('/api/goals/' + btn.dataset.deleteGoal + '/delete/', new FormData());
    if (out.ok) {
      var card = $('.goal-grid [data-goal-id="' + btn.dataset.deleteGoal + '"]');
      if (card) {
        card.classList.add('tx--leaving');
        setTimeout(function () { card.remove(); }, 200);
      }
      toast(out.data.message, 'success');
    }
  });

  /* ---------- Seed demo (empty state) ---------- */
  var seedBtn = $('#seed-demo');
  if (seedBtn) {
    seedBtn.addEventListener('click', async function () {
      setBusy(seedBtn, true);
      var out = await post('/api/seed/', new FormData());
      setBusy(seedBtn, false);
      if (out.ok) {
        toast(out.data.message, 'info');
        setTimeout(function () { location.reload(); }, 700);
      } else {
        toast(out.data.message || 'Gagal memuat data contoh.', 'danger');
      }
    });
  }

  /* ---------- Filter bulan (halaman transaksi) ---------- */
  var monthFilter = $('#month-filter');
  if (monthFilter) {
    monthFilter.addEventListener('change', function () {
      var url = new URL(location.href);
      if (monthFilter.value) url.searchParams.set('month', monthFilter.value);
      else url.searchParams.delete('month');
      location.href = url.toString();
    });
  }

  /* ---------- Telegram: tarik update bot (hanya saat token terpasang) ----------
     Server memanggil getUpdates; transaksi baru & pertanyaan kategori
     dibalas dengan toast + pembaruan pill status di topbar. */
  var MF_TG = (function () {
    var el = document.getElementById('mf-telegram');
    if (!el) return null;
    try { return JSON.parse(el.textContent); } catch (e) { return null; }
  })();
  var tgPill = $('.tg-pill');
  function setTgPill(status) {
    if (!tgPill || !status) return;
    tgPill.className = 'tg-pill tg-pill--' + status.state;
    tgPill.title = status.label;
    tgPill.setAttribute('aria-label', status.label);
  }
  async function pollTelegram() {
    if (!MF_TG || document.hidden) return; // hemat: lewati saat tab latar
    var res;
    try {
      res = await fetch('/api/telegram/poll/', { headers: { 'Accept': 'application/json' } });
    } catch (e) { return; } // offline / server belum siap — coba lagi nanti
    if (res.status === 401) { toLogin(); return; }
    var out = {};
    try { out = await res.json(); } catch (e) { return; }
    if (!out || out.ok === false) return;
    if (out.status) setTgPill(out.status);
    (out.new_tx || []).forEach(function (tx) {
      var icon = (tx.category && tx.category.icon) || '💳';
      var jenis = tx.type === 'income' ? 'Pemasukan' : 'Pengeluaran';
      toast('📥 Via Telegram: ' + icon + ' ' + tx.description + ' — ' +
            tx.amount_label + ' (' + jenis + ')', 'success');
    });
    (out.new_budgets || []).forEach(function (b) {
      if (PAGE === 'budgets') {
        // Kartu langsung muncul tanpa reload.
        var grid = $('.budget-grid');
        if (grid) {
          var empty = grid.querySelector('.empty-note-card');
          if (empty) empty.remove();
          grid.prepend(buildBudgetCard(b));
        }
      }
      toast('📋 Anggaran "' + b.name + '" dibuat — ' + b.limit_label + '/bulan', 'success');
    });
    (out.events || []).forEach(function (ev) {
      if (ev.kind === 'ask_category') {
        toast('Bot Telegram bertanya kategori “' + ev.category +
              '” — balas di Telegram: simpan / bulanan / batal', 'info');
      } else if (ev.kind === 'ask_budget') {
        toast('Bot Telegram bertanya batas bulanan “' + ev.category +
              '” — balas dengan angka atau “lewat”', 'info');
      } else if (ev.kind === 'unauthorized') {
        toast('Chat baru menghubungi bot MyFinance — verifikasi di ' +
              'menu Akun & Keamanan', 'info');
      }
    });
  }
  if (MF_TG && MF_TG.state !== 'off') {
    setTimeout(pollTelegram, 1500);
    setInterval(pollTelegram, 25000);
  }

  /* ---------- Init ---------- */
  function init() {
    $$('[data-count]').forEach(function (el) {
      animateNumber(el, el.dataset.count, el.dataset.format || 'idr');
    });
    animateProgress();
    animateRings();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
