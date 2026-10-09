/* ============================================================
   MyFinance — charts.js
   Arus kas (bar) + porsi pengeluaran (donut) dengan animasi.
   ============================================================ */
(function () {
  'use strict';

  function getData() {
    var el = document.getElementById('mf-data');
    if (!el) return {};
    try { return JSON.parse(el.textContent); } catch (e) { return {}; }
  }

  function fmtIDR(v) {
    return 'Rp ' + Math.round(Math.abs(v || 0)).toLocaleString('id-ID');
  }
  function fmtCompact(v) {
    v = Number(v) || 0;
    if (v >= 1e9) return (v / 1e9).toLocaleString('id-ID', { maximumFractionDigits: 1 }) + 'M';
    if (v >= 1e6) return (v / 1e6).toLocaleString('id-ID', { maximumFractionDigits: 1 }) + ' jt';
    if (v >= 1e3) return (v / 1e3).toLocaleString('id-ID', { maximumFractionDigits: 0 }) + ' rb';
    return String(v);
  }

  function init() {
    if (!window.Chart) return;
    var data = getData();
    var charts = (data && data.charts) || {};

    Chart.defaults.font.family = "'Inter', system-ui, sans-serif";
    Chart.defaults.font.size = 12;
    Chart.defaults.color = '#667085';

    var cashEl = document.getElementById('cashflow-chart');
    if (cashEl && charts.cashflow && charts.cashflow.labels.length) {
      new Chart(cashEl, {
        type: 'bar',
        data: {
          labels: charts.cashflow.labels,
          datasets: [
            {
              label: 'Pemasukan',
              data: charts.cashflow.income,
              backgroundColor: 'rgba(34, 197, 94, .82)',
              hoverBackgroundColor: 'rgba(22, 163, 74, 1)',
              borderRadius: 8,
              borderSkipped: false,
              maxBarThickness: 22
            },
            {
              label: 'Pengeluaran',
              data: charts.cashflow.expense,
              backgroundColor: 'rgba(229, 72, 77, .65)',
              hoverBackgroundColor: 'rgba(229, 72, 77, .9)',
              borderRadius: 8,
              borderSkipped: false,
              maxBarThickness: 22
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: { duration: 900, easing: 'easeOutQuart' },
          interaction: { mode: 'index', intersect: false },
          plugins: {
            legend: {
              position: 'bottom',
              labels: { usePointStyle: true, pointStyle: 'circle', boxWidth: 8, boxHeight: 8, padding: 18 }
            },
            tooltip: {
              backgroundColor: '#232a35',
              titleColor: '#fff',
              bodyColor: '#e4e7ec',
              padding: 12,
              cornerRadius: 10,
              boxPadding: 6,
              usePointStyle: true,
              callbacks: {
                label: function (ctx) { return ' ' + ctx.dataset.label + ': ' + fmtIDR(ctx.parsed.y); }
              }
            }
          },
          scales: {
            x: { grid: { display: false }, border: { display: false } },
            y: {
              beginAtZero: true,
              grid: { color: '#eef1f5' },
              border: { display: false },
              ticks: { callback: function (v) { return fmtCompact(v); }, maxTicksLimit: 6 }
            }
          }
        }
      });
    }

    var spendEl = document.getElementById('spend-chart');
    if (spendEl && charts.spend && charts.spend.values.length) {
      new Chart(spendEl, {
        type: 'doughnut',
        data: {
          labels: charts.spend.labels,
          datasets: [{
            data: charts.spend.values,
            backgroundColor: charts.spend.colors,
            borderColor: '#ffffff',
            borderWidth: 3,
            hoverOffset: 10,
            hoverBorderColor: '#ffffff'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '68%',
          animation: { animateRotate: true, duration: 900, easing: 'easeOutQuart' },
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: '#232a35',
              titleColor: '#fff',
              bodyColor: '#e4e7ec',
              padding: 12,
              cornerRadius: 10,
              boxPadding: 6,
              usePointStyle: true,
              callbacks: {
                label: function (ctx) {
                  var total = ctx.dataset.data.reduce(function (a, b) { return a + b; }, 0);
                  var pct = total ? Math.round(ctx.parsed / total * 100) : 0;
                  return ' ' + fmtIDR(ctx.parsed) + ' (' + pct + '%)';
                }
              }
            }
          }
        }
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
