// The admin Settings page (templates/admin_settings.html, prg32_construction_kit/settings.py).
// The server describes every setting (kind, choices, limits, locked or not); this file draws
// one field per setting in its tab and saves only what was changed in that tab.
(function () {
  let settings = [];

  function fieldId(key) { return 'setting-' + key; }

  function input(item) {
    const id = fieldId(item.key);
    const disabled = item.locked ? ' disabled' : '';
    const value = item.value === null || item.value === undefined ? '' : item.value;
    if (item.kind === 'bool') {
      return `<div class="form-check form-switch">
        <input class="form-check-input" type="checkbox" role="switch" id="${id}" data-key="${item.key}"${value ? ' checked' : ''}${disabled}>
        <label class="form-check-label fw-semibold" for="${id}">${Kit.escape(item.label)}</label></div>`;
    }
    const label = `<label class="form-label fw-semibold mb-1" for="${id}">${Kit.escape(item.label)}</label>`;
    if (item.kind === 'choice') {
      const options = item.choices.map(choice =>
        `<option value="${Kit.escape(choice)}"${choice === value ? ' selected' : ''}>${Kit.escape(choice)}</option>`).join('');
      return label + `<select class="form-select" id="${id}" data-key="${item.key}"${disabled}>${options}</select>`;
    }
    if (item.kind === 'text') {
      return label + `<textarea class="form-control" rows="3" id="${id}" data-key="${item.key}"${disabled}>${Kit.escape(value)}</textarea>`;
    }
    if (item.kind === 'secret') {
      const state = item.set ? tr('js.admin_settings.a_value_is_set_leave_empty', 'A value is set; leave empty to keep it.') : tr('js.admin_settings.not_set', 'Not set.');
      return label + `<input class="form-control" type="password" autocomplete="new-password" id="${id}" data-key="${item.key}"
        placeholder="${Kit.escape(state)}"${disabled}>`;
    }
    if (item.kind === 'int' || item.kind === 'float') {
      const limits = (item.minimum !== null ? ` min="${item.minimum}"` : '') + (item.maximum !== null ? ` max="${item.maximum}"` : '');
      const step = item.kind === 'int' ? '1' : 'any';
      return label + `<input class="form-control" type="number" step="${step}"${limits} id="${id}" data-key="${item.key}" value="${Kit.escape(value)}"${disabled}>`;
    }
    const shown = Array.isArray(value) ? value.join(', ') : value;
    const type = item.kind === 'url' ? 'url' : 'text';
    return label + `<input class="form-control" type="${type}" id="${id}" data-key="${item.key}" value="${Kit.escape(shown)}"${disabled}>`;
  }

  function field(item) {
    const notes = [];
    if (item.locked) notes.push(`<span class="badge text-bg-secondary">set on the server: ${Kit.escape(item.env)}</span>`);
    else if (item.changed) {
      notes.push('<span class="badge text-bg-info">' + Kit.escape(tr('js.admin_settings.changed_here', 'changed here')) + '</span>');
      notes.push(`<button type="button" class="btn btn-link btn-sm p-0 reset-setting" data-key="${item.key}">${Kit.escape(tr('js.admin_settings.back_to_the_default', 'Back to the default'))}</button>`);
    }
    if (item.kind !== 'secret' && !item.locked && item.default !== undefined && item.default !== null && item.default !== '') {
      const shown = Array.isArray(item.default) ? item.default.join(', ')
        : item.kind === 'bool' ? (item.default ? 'on' : 'off') : String(item.default);
      notes.push(`<span class="text-muted">default: ${Kit.escape(shown)}</span>`);
    }
    return `<div class="settings-field" data-key="${item.key}">${input(item)}
      ${item.help ? `<div class="form-text">${Kit.escape(item.help)}</div>` : ''}
      <div class="small d-flex flex-wrap gap-2 align-items-center mt-1">${notes.join(' ')}</div></div>`;
  }

  function draw() {
    $('.settings-form').each(function () {
      const group = $(this).data('group');
      const items = settings.filter(item => item.group === group);
      $(this).find('.settings-fields').html(items.map(field).join(''));
    });
  }

  function load() {
    return Kit.api('/api/admin/settings').then(data => { settings = data.settings; draw(); })
      .catch(err => Kit.toast(err.message, 'danger'));
  }

  function currentValue(item, element) {
    if (item.kind === 'bool') return element.checked;
    const raw = $(element).val();
    if (item.kind === 'int') return raw === '' ? null : parseInt(raw, 10);
    if (item.kind === 'float') return raw === '' ? null : parseFloat(raw);
    if (item.kind === 'list') return String(raw).split(',').map(part => part.trim()).filter(Boolean);
    return raw;
  }

  function same(a, b) { return JSON.stringify(a ?? null) === JSON.stringify(b ?? null); }

  function save(changes) {
    if (!Object.keys(changes).length) { Kit.toast(tr('js.admin_settings.nothing_changed', 'Nothing changed'), 'secondary'); return Promise.resolve(); }
    return Kit.api('/api/admin/settings', { method: 'PUT', body: { settings: changes } }).then(data => {
      settings = data.settings;
      draw();
      Kit.toast(tr('js.admin_settings.saved', 'Saved: {count}', { count: data.changed.length }) + tr('js.admin_settings.setting_s_reload_other_pages_to', ' setting(s). Reload other pages to see them.'), 'success');
    }).catch(err => Kit.toast(err.message, 'danger'));
  }

  $(document).on('submit', '.settings-form', function (event) {
    event.preventDefault();
    const changes = {};
    $(this).find('[data-key]').filter('input, select, textarea').each(function () {
      const item = settings.find(entry => entry.key === $(this).data('key'));
      if (!item || item.locked) return;
      const value = currentValue(item, this);
      if (item.kind === 'secret') { if (value) changes[item.key] = value; return; }
      if (value === null) return;
      if (!same(value, item.value)) changes[item.key] = value;
    });
    save(changes);
  });

  $(document).on('click', '.reset-setting', function () {
    save({ [$(this).data('key')]: null });
  });

  $(document).on('click', '#smtpTest', function () {
    Kit.api('/api/admin/settings/smtp_test', { method: 'POST', body: {} })
      .then(data => Kit.toast(data.status === 'sent'
        ? tr('js.admin_settings.test_mail_sent_to', 'Test mail sent to {sent_to}', { sent_to: data.sent_to })
        : tr('js.admin_settings.test_mail_queued_for', 'Test mail for {sent_to} is waiting in the queue', { sent_to: data.sent_to }), 'success'))
      .catch(err => Kit.toast(err.message, 'danger'))
      .then(loadMail);
  });

  // The email sending queue (mail_queue.py): counts, the latest messages, a retry for failed ones.
  // It refreshes itself every few seconds while the Email tab is open.
  let mailStatus = '';
  const MAIL_STATES = {
    queued: ['text-bg-secondary', 'bi-hourglass', () => tr('js.admin_settings.mail_state_queued', 'to send')],
    sending: ['text-bg-info', 'bi-send', () => tr('js.admin_settings.mail_state_sending', 'sending')],
    sent: ['text-bg-success', 'bi-check2', () => tr('js.admin_settings.mail_state_sent', 'sent')],
    failed: ['text-bg-danger', 'bi-x-octagon', () => tr('js.admin_settings.mail_state_failed', 'failed')],
  };

  function mailRow(item) {
    const [badge, icon, label] = MAIL_STATES[item.status] || ['text-bg-light', 'bi-question', () => item.status];
    const when = new Date(item.created_at).toLocaleString();
    const note = item.status === 'queued' && item.attempts > 0 && item.next_attempt_at
      ? `<div class="small text-muted">${Kit.escape(tr('js.admin_settings.mail_next_try', 'next try {when}', { when: new Date(item.next_attempt_at).toLocaleTimeString() }))}</div>` : '';
    const error = item.last_error ? `<div class="small text-danger">${Kit.escape(item.last_error)}</div>` : '';
    const retry = item.status === 'failed'
      ? `<button type="button" class="btn btn-sm btn-outline-primary mail-retry" data-id="${item.id}"><i class="bi bi-arrow-repeat" aria-hidden="true"></i> ${Kit.escape(tr('js.admin_settings.mail_retry', 'Send again'))}</button>` : '';
    return `<tr><td><span class="badge ${badge}"><i class="bi ${icon}" aria-hidden="true"></i> ${Kit.escape(label())}</span></td>
      <td><code>${Kit.escape(item.recipient)}</code></td><td>${Kit.escape(item.subject)}${error}</td>
      <td class="small">${Kit.escape(when)}${note}</td><td>${item.attempts}</td><td>${retry}</td></tr>`;
  }

  function loadMail() {
    if (!$('#mailQueue').length) return Promise.resolve();
    return Kit.api('/api/admin/mail?status=' + encodeURIComponent(mailStatus)).then(data => {
      const counts = data.counts;
      $('#mailLimit').text(tr('js.admin_settings.mail_limit', 'At most {limit} at the same time.', { limit: data.limit }));
      Object.keys(counts).forEach(state => $(`[data-count="${state}"]`).text(counts[state]));
      $('[data-count="all"]').text(Object.values(counts).reduce((a, b) => a + b, 0));
      $('#mailRows').html(data.messages.length ? data.messages.map(mailRow).join('')
        : `<tr><td colspan="6" class="text-muted">${Kit.escape(tr('js.admin_settings.mail_none', 'No messages.'))}</td></tr>`);
    }).catch(err => $('#mailRows').html(`<tr><td colspan="6" class="text-danger">${Kit.escape(err.message)}</td></tr>`));
  }

  $(document).on('click', '#mailFilter [data-status]', function () {
    mailStatus = $(this).data('status');
    $('#mailFilter [data-status]').removeClass('active');
    $(this).addClass('active');
    loadMail();
  });
  $(document).on('click', '#mailRefresh', loadMail);
  $(document).on('click', '.mail-retry', function () {
    Kit.api(`/api/admin/mail/${$(this).data('id')}/retry`, { method: 'POST', body: {} })
      .then(() => { Kit.toast(tr('js.admin_settings.mail_requeued', 'Back in the queue'), 'success'); loadMail(); })
      .catch(err => Kit.toast(err.message, 'danger'));
  });
  $(document).on('shown.bs.tab', '#tab-email', loadMail);
  setInterval(() => { if ($('#pane-email').hasClass('active') && !document.hidden) loadMail(); }, 5000);

  // /admin/settings#maintenance opens that tab (the maintenance banner links there).
  const wanted = window.location.hash.replace('#', '');
  if (wanted && document.getElementById('tab-' + wanted)) {
    bootstrap.Tab.getOrCreateInstance(document.getElementById('tab-' + wanted)).show();
  }
  load();
  loadMail();
})();
