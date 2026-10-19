// School sign-in providers (ADR-0016), for administrators.
(function () {
  'use strict';
  let editing = null;

  function load() {
    return Kit.api('/api/admin/identity_providers').then(data => {
      $('#providerList').html(data.providers.map(item => `
        <li class="list-group-item d-flex justify-content-between align-items-start gap-2">
          <div><strong>${Kit.escape(item.name)}</strong> <code>${Kit.escape(item.slug)}</code>
            ${item.enabled ? '' : '<span class="badge text-bg-secondary">off</span>'}
            ${item.from_environment ? '<span class="badge text-bg-info">from PRG32_OIDC_*</span>' : ''}
            <div class="small text-muted">${Kit.escape(item.issuer)} · client ${Kit.escape(item.client_id)} ·
              secret ${Kit.escape(item.client_secret_ref || 'none (public client)')}</div></div>
          ${item.from_environment ? '' : `<div class="text-nowrap">
            <button class="btn btn-outline-primary btn-sm edit-provider" data-slug="${Kit.escape(item.slug)}">Edit</button>
            <button class="btn btn-outline-secondary btn-sm toggle-provider" data-slug="${Kit.escape(item.slug)}" data-enabled="${item.enabled ? 1 : 0}">${item.enabled ? 'Switch off' : 'Switch on'}</button>
            <button class="btn btn-outline-danger btn-sm delete-provider" data-slug="${Kit.escape(item.slug)}">Delete</button></div>`}
        </li>`).join('') || '<li class="list-group-item text-muted">No school sign-in yet.</li>');
      $('#providerList').data('providers', data.providers);
    }).catch(err => Kit.toast(err.message, 'danger'));
  }

  $('#providerForm').on('submit', function (event) {
    event.preventDefault();
    const form = new FormData(this);
    let roleMap = {};
    try { roleMap = form.get('role_map') ? JSON.parse(form.get('role_map')) : {}; } catch (_) {
      return Kit.toast('The role map must be JSON, like {"faculty": "teacher"}', 'warning');
    }
    const body = { name: form.get('name'), issuer: form.get('issuer'), client_id: form.get('client_id'),
      client_secret_ref: form.get('client_secret_ref'), role_claim: form.get('role_claim'), role_map: roleMap,
      allowed_domains: String(form.get('allowed_domains') || '').split(/\s+/).filter(Boolean) };
    if (!editing) body.slug = form.get('slug');
    Kit.api(editing ? '/api/admin/identity_providers/' + encodeURIComponent(editing) : '/api/admin/identity_providers',
      { method: editing ? 'PUT' : 'POST', body })
      .then(() => { Kit.toast('Provider saved', 'success'); editing = null; this.reset(); $('#pSlug').prop('disabled', false);
        $('#providerFormTitle').text('New provider'); load(); })
      .catch(err => Kit.toast(err.message, 'danger'));
  });
  $('#providerList').on('click', '.edit-provider', function () {
    const item = $('#providerList').data('providers').find(p => p.slug === $(this).data('slug'));
    editing = item.slug;
    const form = $('#providerForm')[0];
    for (const key of ['slug', 'name', 'issuer', 'client_id', 'client_secret_ref', 'role_claim']) form.elements[key].value = item[key] || '';
    form.elements.role_map.value = JSON.stringify(item.role_map || {});
    form.elements.allowed_domains.value = (item.allowed_domains || []).join(' ');
    $('#pSlug').prop('disabled', true);
    $('#providerFormTitle').text('Edit ' + item.slug);
  }).on('click', '.toggle-provider', function () {
    Kit.api('/api/admin/identity_providers/' + encodeURIComponent($(this).data('slug')),
      { method: 'PUT', body: { enabled: !Number($(this).data('enabled')) } }).then(load)
      .catch(err => Kit.toast(err.message, 'danger'));
  }).on('click', '.delete-provider', function () {
    if (!window.confirm('Delete this provider? Linked accounts stay; they sign in another way.')) return;
    Kit.api('/api/admin/identity_providers/' + encodeURIComponent($(this).data('slug')), { method: 'DELETE' })
      .then(load).catch(err => Kit.toast(err.message, 'danger'));
  });

  load();
})();
