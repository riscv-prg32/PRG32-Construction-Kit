// The admin Statistics page (templates/admin_statistics.html, prg32_construction_kit/usage_stats.py).
// The server sends every table for the chosen days; this file draws the tiles, four SVG charts
// (one axis each, a legend for two series, a tooltip on hover) and the tables, and asks the
// server for the CSV files. Colours come from css/admin_stats.css, never from here.
(function () {
  const SVG = 'http://www.w3.org/2000/svg';
  const W = 640, H = 240, M = { top: 12, right: 12, bottom: 28, left: 44 };
  let data = null;

  function isoDay(date) { return date.toISOString().slice(0, 10); }
  function number(value) { return Number(value || 0).toLocaleString(); }

  function query(extra) {
    const params = new URLSearchParams();
    ['from', 'to'].forEach(name => { const value = $(`#statsFilter [name="${name}"]`).val(); if (value) params.set(name, value); });
    if ($('#statsNames').is(':checked')) params.set('names', '1');
    Object.entries(extra || {}).forEach(([key, value]) => params.set(key, value));
    return params.toString();
  }

  // --- tiny SVG helpers ----------------------------------------------------------------------
  function el(name, attrs, parent) {
    const node = document.createElementNS(SVG, name);
    Object.entries(attrs || {}).forEach(([key, value]) => node.setAttribute(key, value));
    if (parent) parent.appendChild(node);
    return node;
  }

  // The top of the axis: 4, 8, 20, 40, 80, 200 ... so the four grid steps are whole numbers.
  function niceMax(value) {
    let power = 1;
    while (true) {
      const found = [4, 8, 20].map(step => step * power).find(step => step >= value);
      if (found) return found;
      power *= 10;
    }
  }

  function frame(container, max, height) {
    container.empty();
    const svg = el('svg', { viewBox: `0 0 ${W} ${height || H}`, preserveAspectRatio: 'xMidYMid meet' });
    container[0].appendChild(svg);
    const plotH = (height || H) - M.top - M.bottom;
    const grid = el('g', { class: 'grid' }, svg);
    const axis = el('g', { class: 'axis' }, svg);
    for (let index = 0; index <= 4; index++) {
      const y = M.top + plotH - (plotH * index) / 4;
      el('line', { x1: M.left, x2: W - M.right, y1: y, y2: y }, grid);
      el('text', { x: M.left - 6, y: y + 4, 'text-anchor': 'end' }, axis).textContent = number((max * index) / 4);
    }
    return { svg, axis, plotH, y: value => M.top + plotH - (plotH * value) / max };
  }

  function tooltip(container) {
    let tip = container.find('.stats-tip');
    if (!tip.length) tip = $('<div class="stats-tip d-none" role="status"></div>').appendTo(container);
    return {
      show(html, x, y) {
        const box = container[0].getBoundingClientRect();
        const scale = box.width / W;
        tip.html(html).removeClass('d-none');
        const left = Math.min(Math.max(0, x * scale + 12), box.width - tip.outerWidth());
        tip.css({ left: left + 'px', top: Math.max(0, y * scale - tip.outerHeight() - 8) + 'px' });
      },
      hide() { tip.addClass('d-none'); },
    };
  }

  function xLabels(axis, labels, xOf, plotBottom) {
    const every = Math.max(1, Math.ceil(labels.length / 8));
    labels.forEach((label, index) => {
      if (index % every) return;
      el('text', { x: xOf(index), y: plotBottom + 18, 'text-anchor': 'middle' }, axis).textContent = label;
    });
  }

  function swatch(kind) { return `<span class="stats-legend"><span class="swatch swatch-${kind}"></span></span>`; }

  // Two lines on one axis: accounts and visitor-days per day, with a crosshair tooltip.
  function lineChart(container, rows, series) {
    const max = niceMax(Math.max(1, ...rows.flatMap(row => series.map(item => row[item.key]))));
    const { svg, axis, plotH, y } = frame(container, max);
    const step = rows.length > 1 ? (W - M.left - M.right) / (rows.length - 1) : 0;
    const xOf = index => M.left + index * step;
    series.forEach(item => {
      const path = rows.map((row, index) => `${index ? 'L' : 'M'}${xOf(index)},${y(row[item.key])}`).join(' ');
      el('path', { d: path, class: `line series-${item.kind}` }, svg);
      if (rows.length <= 45) rows.forEach((row, index) => el('circle', { cx: xOf(index), cy: y(row[item.key]), r: 3, class: `marker series-${item.kind}` }, svg));
    });
    xLabels(axis, rows.map(row => row.day.slice(5)), xOf, M.top + plotH);
    const cross = el('line', { class: 'crosshair d-none', y1: M.top, y2: M.top + plotH }, svg);
    const tip = tooltip(container);
    const hit = el('rect', { class: 'hit', x: M.left - step / 2, y: M.top, width: W - M.left - M.right + step, height: plotH }, svg);
    hit.addEventListener('mousemove', event => {
      const point = event.offsetX / (container[0].getBoundingClientRect().width / W);
      const index = Math.max(0, Math.min(rows.length - 1, Math.round((point - M.left) / (step || 1))));
      cross.setAttribute('x1', xOf(index)); cross.setAttribute('x2', xOf(index)); cross.classList.remove('d-none');
      tip.show(`<strong>${Kit.escape(rows[index].day)}</strong>` + series.map(item =>
        `<div>${swatch(item.kind)}${Kit.escape(item.label)}: <strong>${number(rows[index][item.key])}</strong></div>`).join(''),
        xOf(index), M.top + 20);
    });
    hit.addEventListener('mouseleave', () => { cross.classList.add('d-none'); tip.hide(); });
  }

  // Vertical bars; with two series they are stacked (accounts below, visitors on top).
  function barChart(container, rows, labelKey, series, labelOf, extraTip) {
    const max = niceMax(Math.max(1, ...rows.map(row => series.reduce((sum, item) => sum + row[item.key], 0))));
    const { svg, axis, plotH, y } = frame(container, max);
    const slot = (W - M.left - M.right) / rows.length;
    const width = Math.max(2, slot - 2);
    const xOf = index => M.left + index * slot + slot / 2;
    const tip = tooltip(container);
    rows.forEach((row, index) => {
      let base = 0;
      series.forEach(item => {
        const value = row[item.key];
        if (value > 0) {
          const top = y(base + value), height = Math.max(1, y(base) - top - (base ? 1 : 0));
          el('rect', { x: xOf(index) - width / 2, y: top, width, height, rx: Math.min(3, width / 3), class: `bar series-${item.kind}` }, svg);
        }
        base += value;
      });
      const hit = el('rect', { class: 'hit', x: xOf(index) - slot / 2, y: M.top, width: slot, height: plotH }, svg);
      hit.addEventListener('mousemove', () => tip.show(`<strong>${Kit.escape(labelOf(row))}</strong>` + series.map(item =>
        `<div>${series.length > 1 ? swatch(item.kind) : ''}${Kit.escape(item.label)}: <strong>${number(row[item.key])}</strong></div>`).join('')
        + (extraTip ? extraTip(row) : ''), xOf(index), y(base)));
      hit.addEventListener('mouseleave', () => tip.hide());
    });
    xLabels(axis, rows.map(row => String(row[labelKey]).slice(-5)), xOf, M.top + plotH);
  }

  // Horizontal bars with the value written at the end (what people do).
  function hBarChart(container, rows) {
    container.empty();
    const top = rows.slice(0, 12);
    const rowH = 22, left = 120, height = top.length * rowH + 8;
    const svg = el('svg', { viewBox: `0 0 ${W} ${Math.max(height, 40)}` });
    container[0].appendChild(svg);
    const max = Math.max(1, ...top.map(row => row.requests));
    const labels = el('g', { class: 'label' }, svg);
    const tip = tooltip(container);
    top.forEach((row, index) => {
      const y = 4 + index * rowH;
      const width = ((W - left - 70) * row.requests) / max;
      el('text', { x: left - 8, y: y + 14, 'text-anchor': 'end' }, labels).textContent = row.category;
      el('rect', { x: left, y: y + 3, width: Math.max(2, width), height: rowH - 8, rx: 3, class: 'bar series-accounts' }, svg);
      el('text', { x: left + width + 6, y: y + 14 }, labels).textContent = number(row.requests);
      const hit = el('rect', { class: 'hit', x: 0, y, width: W, height: rowH }, svg);
      hit.addEventListener('mousemove', () => tip.show(`<strong>${Kit.escape(row.category)}</strong>
        <div>${Kit.escape(tr('js.admin_statistics.requests', 'Requests'))}: <strong>${number(row.requests)}</strong></div>
        <div>${Kit.escape(tr('js.admin_statistics.accounts', 'Accounts'))}: ${number(row.users)} · ${Kit.escape(tr('js.admin_statistics.visitor_days', 'Visitor-days'))}: ${number(row.guest_visitor_days)}</div>
        <div>${Kit.escape(tr('js.admin_statistics.average', 'Average'))}: ${number(row.avg_ms)} ms</div>`, left + width, y));
      hit.addEventListener('mouseleave', () => tip.hide());
    });
    if (!top.length) container.html(`<p class="text-muted small mb-0">${Kit.escape(tr('js.admin_statistics.no_data', 'No data for these days.'))}</p>`);
  }

  // --- tiles and tables ------------------------------------------------------------------------
  function tiles(summary) {
    const items = [
      [tr('js.admin_statistics.active_accounts', 'Active accounts'), summary.active_users, tr('js.admin_statistics.of_accounts', 'of {count} accounts', { count: number(summary.accounts) })],
      [tr('js.admin_statistics.visitor_days', 'Visitor-days'), summary.guest_visitor_days, tr('js.admin_statistics.visitors_without_account', 'visitors without an account')],
      [tr('js.admin_statistics.requests', 'Requests'), summary.requests, tr('js.admin_statistics.page_views', '{count} page views', { count: number(summary.page_views) })],
      [tr('js.admin_statistics.builds', 'Builds'), summary.builds, tr('js.admin_statistics.publications', '{count} published', { count: number(summary.publications) })],
      [tr('js.admin_statistics.server_errors', 'Server errors'), summary.server_errors, tr('js.admin_statistics.refused', '{count} refused', { count: number(summary.refused_requests) })],
      [tr('js.admin_statistics.response_time', 'Response time'), summary.avg_ms + ' ms', tr('js.admin_statistics.p95', '95% under {ms} ms', { ms: number(summary.p95_ms) })],
    ];
    $('#tiles').html(items.map(([label, value, detail]) => `<div class="col-6 col-md-4 col-xl-2"><div class="card stats-tile h-100"><div class="card-body py-2">
      <div class="small text-muted">${Kit.escape(label)}</div><div class="stats-value">${Kit.escape(typeof value === 'number' ? number(value) : value)}</div>
      <div class="small text-muted">${Kit.escape(detail)}</div></div></div></div>`).join(''));
  }

  function table(rows, columns) {
    if (!rows.length) return `<p class="text-muted small mb-0">${Kit.escape(tr('js.admin_statistics.no_data', 'No data for these days.'))}</p>`;
    const head = columns.map(column => `<th scope="col">${Kit.escape(column)}</th>`).join('');
    const body = rows.map(row => '<tr>' + columns.map(column => {
      const value = row[column];
      return typeof value === 'number' ? `<td class="text-end font-monospace">${number(value)}</td>` : `<td>${Kit.escape(value === null || value === undefined ? '' : String(value))}</td>`;
    }).join('') + '</tr>').join('');
    return `<table class="table table-sm table-striped mb-0"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
  }

  function countTable(counts) {
    const rows = Object.entries(counts || {}).sort((a, b) => b[1] - a[1]).map(([name, count]) => ({ name, count }));
    return table(rows, ['name', 'count']);
  }

  function draw() {
    const accounts = tr('js.admin_statistics.accounts', 'Accounts');
    tiles(data.summary);
    lineChart($('#chartPeople'), data.daily, [
      { key: 'active_users', kind: 'accounts', label: accounts },
      { key: 'guest_visitors', kind: 'visitors', label: tr('js.admin_statistics.visitor_days', 'Visitor-days') }]);
    barChart($('#chartRequests'), data.daily, 'day', [{ key: 'requests', kind: 'accounts', label: tr('js.admin_statistics.requests', 'Requests') }],
      row => row.day, row => `<div>${Kit.escape(tr('js.admin_statistics.compiles', 'Compiles'))}: ${number(row.compiles)} · ${Kit.escape(tr('js.admin_statistics.server_errors', 'Server errors'))}: ${number(row.errors)}</div>`);
    barChart($('#chartHours'), data.hours, 'hour', [
      { key: 'user_requests', kind: 'accounts', label: accounts },
      { key: 'guest_requests', kind: 'visitors', label: tr('js.admin_statistics.visitors', 'Visitors') }],
      row => tr('js.admin_statistics.hour_utc', '{hour}:00 UTC', { hour: String(row.hour).padStart(2, '0') }));
    hBarChart($('#chartCategories'), data.categories);
    $('#rolesTable').html(countTable(data.summary.accounts_by_role));
    $('#kitRolesTable').html(countTable(data.summary.accounts_by_kit_role));
    $('#buildsTable').html(countTable(data.summary.builds_by_status));
    const summaryRows = Object.entries(data.summary).filter(([, value]) => typeof value !== 'object').map(([metric, value]) => ({ metric, value }));
    $('.stats-table[data-table="summary"]').html(table(summaryRows, ['metric', 'value']));
    $('.stats-table[data-table="daily"]').html(table(data.daily, Object.keys(data.daily[0] || {})));
    $('.stats-table[data-table="hours"]').html(table(data.hours, ['hour', 'user_requests', 'guest_requests']));
    $('.stats-table[data-table="categories"]').html(table(data.categories, ['category', 'requests', 'users', 'guest_visitor_days', 'errors', 'avg_ms']));
    $('.stats-table[data-table="per_user"]').html(table(data.per_user, ['user', 'role', 'kit_role', 'requests', 'active_days', 'page_views',
      'project_saves', 'compiles', 'runs', 'errors', 'projects_owned', 'builds', 'builds_ok', 'last_seen']));
  }

  function load() {
    return Kit.api('/api/admin/statistics?' + query()).then(answer => { data = answer; draw(); })
      .catch(err => Kit.toast(err.message, 'danger'));
  }

  function range(days) {
    const today = new Date();
    $('#statsTo').val(isoDay(today));
    $('#statsFrom').val(isoDay(new Date(today.getTime() - (days - 1) * 86400000)));
  }

  $('#statsFilter').on('submit', event => { event.preventDefault(); load(); });
  $('#statsNames').on('change', load);
  $('#quickRange [data-days]').on('click', function () { range(Number($(this).data('days'))); load(); });
  $(document).on('click', '.csv-download', function () {
    Kit.download(`/api/admin/statistics/${$(this).data('table')}.csv?` + query());
  });
  let resizeTimer = null;
  $(window).on('resize', () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => data && draw(), 200); });

  range(30);
  load();
})();
