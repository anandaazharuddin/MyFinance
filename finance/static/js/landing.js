/* ============================================================
   MyFinance — landing.js
   Interaksi landing page: nav scroll, reveal on scroll,
   count-up, parallax hero, dan tab pratinjau.
   ============================================================ */
(function () {
  'use strict';

  var $ = function (s, el) { return (el || document).querySelector(s); };
  var $$ = function (s, el) { return Array.prototype.slice.call((el || document).querySelectorAll(s)); };
  var REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- Navbar: shadow saat scroll ---------- */
  var nav = $('#l-nav');
  if (nav) {
    var onScroll = function () { nav.classList.toggle('is-scrolled', window.scrollY > 8); };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  /* ---------- Count-up angka ---------- */
  function fmtValue(v, format) {
    if (format === 'pct-int') return Math.round(v) + '%';
    if (format === 'int') return String(Math.round(v));
    /* idr */
    return 'Rp ' + Math.round(Math.abs(v)).toLocaleString('id-ID');
  }
  function countUp(el) {
    if (el._counted) return;
    el._counted = true;
    var to = Number(el.dataset.count) || 0;
    var format = el.dataset.format || 'int';
    if (REDUCED) { el.textContent = fmtValue(to, format); return; }
    var dur = 1000;
    var t0 = null;
    function frame(t) {
      if (t0 === null) t0 = t;
      var p = Math.min((t - t0) / dur, 1);
      var e = 1 - Math.pow(1 - p, 3); /* easeOutCubic */
      el.textContent = fmtValue(to * e, format);
      if (p < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  /* ---------- Reveal on scroll + trigger count-up & bars ---------- */
  var revealEls = $$('.reveal-s');
  var animated = [];
  if ('IntersectionObserver' in window && !REDUCED) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        $$('[data-count]', entry.target).forEach(countUp);
        io.unobserve(entry.target);
      });
    }, { threshold: 0.16 });
    revealEls.forEach(function (el) { io.observe(el); });

    var ioBars = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        ioBars.unobserve(entry.target);
      });
    }, { threshold: 0.4 });
    $$('.l-mock-bars, .l-demo-chart').forEach(function (el) { ioBars.observe(el); });
  } else {
    revealEls.forEach(function (el) {
      el.classList.add('is-visible');
      $$('[data-count]', el).forEach(countUp);
    });
    $$('.l-mock-bars, .l-demo-chart').forEach(function (el) { el.classList.add('is-visible'); });
  }

  /* Ring progres di mockup hero */
  var C = 2 * Math.PI * 19;
  $$('#hero-visual [data-ring]').forEach(function (el) {
    var p = Math.min(Math.max(Number(el.dataset.ring) || 0, 0), 1);
    setTimeout(function () { el.style.strokeDashoffset = String(C * (1 - p)); }, 600);
  });

  /* ---------- Parallax hero (pointer halus, subtle) ---------- */
  var hero = $('#hero-visual');
  var mockup = $('#mockup');
  var f1 = $('#float1');
  var f2 = $('#float2');
  if (hero && mockup && window.matchMedia('(pointer: fine)').matches && !REDUCED) {
    var fine = window.matchMedia('(pointer: fine)');
    hero.addEventListener('pointermove', function (e) {
      if (!fine.matches) return;
      var r = hero.getBoundingClientRect();
      var x = (e.clientX - r.left) / r.width - 0.5;
      var y = (e.clientY - r.top) / r.height - 0.5;
      mockup.style.transform = 'rotateY(' + (x * 5).toFixed(2) + 'deg) rotateX(' + (-y * 5).toFixed(2) + 'deg)';
      if (f1) f1.style.translate = (x * -16).toFixed(1) + 'px ' + (y * -12).toFixed(1) + 'px';
      if (f2) f2.style.translate = (x * 13).toFixed(1) + 'px ' + (y * 15).toFixed(1) + 'px';
    });
    hero.addEventListener('pointerleave', function () {
      mockup.style.transform = '';
      if (f1) f1.style.translate = '';
      if (f2) f2.style.translate = '';
    });
  }

  /* ---------- Tab pratinjau ---------- */
  var tabs = $$('.l-tab');
  var panels = $$('.l-tab-panel');
  tabs.forEach(function (tab) {
    tab.addEventListener('click', function () {
      tabs.forEach(function (t) {
        t.classList.remove('is-active');
        t.setAttribute('aria-selected', 'false');
      });
      tab.classList.add('is-active');
      tab.setAttribute('aria-selected', 'true');
      panels.forEach(function (p) { p.classList.remove('is-active'); });
      var panel = document.getElementById('panel-' + tab.dataset.tab);
      if (panel) panel.classList.add('is-active');
      /* animasikan bar chart saat tab dasbor dibuka */
      if (panel) {
        $$('[data-count]', panel).forEach(countUp);
        var chart = $('.l-demo-chart', panel);
        if (chart) {
          chart.classList.remove('is-visible');
          void chart.offsetWidth; /* reset animasi */
          chart.classList.add('is-visible');
        }
      }
    });
  });
})();
