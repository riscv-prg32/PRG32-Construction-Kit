(function () {
  function loadTokens() {
    return Kit.api('/auth/tokens').then(data => {
      $('#tokenList').html(data.tokens.map(token => `
        <div class="list-group-item d-flex justify-content-between align-items-center">
          <div><div class="fw-semibold">${Kit.escape(token.label)}</div>
            <div class="small text-muted">made ${Kit.escape(token.created_at)} · last used ${Kit.escape(token.last_used || 'never')}
              · may ${Kit.escape(token.scopes.join(', '))}${token.expires_at ? ' · expires ' + Kit.escape(token.expires_at) : ''}</div></div>
          <button class="btn btn-outline-danger btn-sm revoke-token" data-id="${Kit.escape(token.id)}">Revoke</button>
        </div>`).join('') || '<div class="list-group-item text-muted">No tokens yet.</div>');
    }).catch(err => Kit.toast(err.message, 'danger'));
  }

  $('#tokenForm').on('submit', function (event) {
    event.preventDefault();
    const form = new FormData(this);
    const body = { label: form.get('label') || 'API token', scopes: form.getAll('scope') };
    if (form.get('expires')) body.expires_in_days = Number(form.get('expires'));
    Kit.api('/auth/tokens', { method: 'POST', body }).then(data => {
      // The full token is shown only this one time.
      $('#newToken').removeClass('d-none').html('Copy this token now, it will not be shown again:<br><code></code>');
      $('#newToken code').text(data.token);
      this.reset();
      loadTokens();
    }).catch(err => Kit.toast(err.message, 'danger'));
  });

  $('#tokenList').on('click', '.revoke-token', function () {
    Kit.api('/auth/tokens/' + encodeURIComponent($(this).data('id')), { method: 'DELETE' })
      .then(() => { Kit.toast('Token revoked', 'success'); loadTokens(); })
      .catch(err => Kit.toast(err.message, 'danger'));
  });

  $('#passwordForm').on('submit', function (event) {
    event.preventDefault();
    const form = new FormData(this);
    Kit.api('/auth/password', { method: 'POST', body: { current_password: form.get('current_password'), new_password: form.get('new_password') } })
      .then(() => { Kit.toast('Password changed', 'success'); this.reset(); })
      .catch(err => Kit.toast(err.message, 'danger'));
  });

  // School accounts (ADR-0016): link one while signed in, unlink, see what is linked.
  function loadIdentities() {
    return Kit.api('/auth/identities').then(data => {
      $('#identityList').html(data.identities.map(item => `
        <li class="list-group-item d-flex justify-content-between align-items-center">
          <span><strong>${Kit.escape(item.provider)}</strong> <span class="small text-muted">${Kit.escape(item.email || '')}</span></span>
          <button class="btn btn-outline-danger btn-sm unlink-identity" data-id="${Kit.escape(item.id)}">Unlink</button></li>`).join('')
        || '<li class="list-group-item text-muted small">No school account linked.</li>');
      $('#identityProviders').html(data.providers.map(item => `
        <button class="btn btn-outline-primary btn-sm link-identity" data-slug="${Kit.escape(item.slug)}">Link ${Kit.escape(item.name)}</button>`).join(''));
    }).catch(err => Kit.toast(err.message, 'danger'));
  }

  $('#identityProviders').on('click', '.link-identity', function () {
    Kit.api('/auth/identities/' + encodeURIComponent($(this).data('slug')) + '/link', { method: 'POST', body: {} })
      .then(data => { window.location.href = data.redirect; })
      .catch(err => Kit.toast(err.message, 'danger'));
  });
  $('#identityList').on('click', '.unlink-identity', function () {
    Kit.api('/auth/identities/' + encodeURIComponent($(this).data('id')), { method: 'DELETE' })
      .then(() => { Kit.toast('School account unlinked', 'success'); loadIdentities(); })
      .catch(err => Kit.toast(err.message, 'danger'));
  });
  $('#signOutEverywhere').on('click', () => {
    if (!window.confirm('Sign out on every computer, this one too?')) return;
    Kit.api('/auth/sessions/revoke', { method: 'POST', body: {} })
      .then(() => { window.location.href = '/auth/login'; })
      .catch(err => Kit.toast(err.message, 'danger'));
  });

  loadTokens();
  loadIdentities();
})();
