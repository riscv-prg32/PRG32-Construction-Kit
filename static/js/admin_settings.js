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
      const state = item.set ? 'A value is set; leave empty to keep it.' : 'Not set.';
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
      notes.push('<span class="badge text-bg-info">changed here</span>');
      notes.push(`<button type="button" class="btn btn-link btn-sm p-0 reset-setting" data-key="${item.key}">Back to the default</button>`);
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
    if (!Object.keys(changes).length) { Kit.toast('Nothing changed', 'secondary'); return Promise.resolve(); }
    return Kit.api('/api/admin/settings', { method: 'PUT', body: { settings: changes } }).then(data => {
      settings = data.settings;
      draw();
      Kit.toast('Saved: ' + data.changed.length + ' setting(s). Reload other pages to see them.', 'success');
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
      .then(data => Kit.toast('Test mail sent to ' + data.sent_to, 'success'))
      .catch(err => Kit.toast(err.message, 'danger'));
  });

  // /admin/settings#maintenance opens that tab (the maintenance banner links there).
  const wanted = window.location.hash.replace('#', '');
  if (wanted && document.getElementById('tab-' + wanted)) {
    bootstrap.Tab.getOrCreateInstance(document.getElementById('tab-' + wanted)).show();
  }
  load();
})();
