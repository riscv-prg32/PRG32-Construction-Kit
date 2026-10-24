(function () {
  function loadTokens() {
    return Kit.api('/auth/tokens').then(data => {
      $('#tokenList').html(data.tokens.map(token => `
        <div class="list-group-item d-flex justify-content-between align-items-center">
          <div><div class="fw-semibold">${Kit.escape(token.label)}</div>
            <div class="small text-muted">made ${Kit.escape(token.created_at)} · last used ${Kit.escape(token.last_used || 'never')}
              · may ${Kit.escape(token.scopes.join(', '))}${token.expires_at ? ' · expires ' + Kit.escape(token.expires_at) : ''}</div></div>
          <button class="btn btn-outline-danger btn-sm revoke-token" data-id="${Kit.escape(token.id)}">${Kit.escape(tr('js.account.revoke', 'Revoke'))}</button>
        </div>`).join('') || '<div class="list-group-item text-muted">' + Kit.escape(tr('js.account.no_tokens_yet', 'No tokens yet.')) + '</div>');
    }).catch(err => Kit.toast(err.message, 'danger'));
  }

  $('#tokenForm').on('submit', function (event) {
    event.preventDefault();
    const form = new FormData(this);
    const body = { label: form.get('label') || tr('js.account.api_token', 'API token'), scopes: form.getAll('scope') };
    if (form.get('expires')) body.expires_in_days = Number(form.get('expires'));
    Kit.api('/auth/tokens', { method: 'POST', body }).then(data => {
      // The full token is shown only this one time.
      $('#newToken').removeClass('d-none').html(Kit.escape(tr('js.account.copy_this_token_now', 'Copy this token now, it will not be shown again:')) + '<br><code></code>');
      $('#newToken code').text(data.token);
      this.reset();
      loadTokens();
    }).catch(err => Kit.toast(err.message, 'danger'));
  });

  const SIGN_IN = { login: tr('js.account.signed_in', 'signed in'), oidc_sign_in: tr('js.account.signed_in_with_the_school_account', 'signed in with the school account'),
    saml_sign_in: tr('js.account.signed_in_with_the_school_account', 'signed in with the school account'), login_new_address: tr('js.account.new_from_a_computer_or_network', 'NEW: from a computer or network not used before'),
    login_failed: tr('js.account.wrong_password', 'wrong password') };

  function loadSignIns() {
    return Kit.api('/auth/sessions/recent').then(data => {
      $('#recentSignIns').html(data.sign_ins.map(item => `
        <li class="list-group-item${item.action === 'login_new_address' ? ' list-group-item-warning' : ''}">
          ${Kit.escape(item.at)} · ${Kit.escape(SIGN_IN[item.action] || item.action)}${item.outcome === 'success' || item.action === 'login_failed' ? '' : ' (' + Kit.escape(item.outcome) + ')'}
          · <span class="text-muted">${Kit.escape(item.address || 'unknown address')}</span></li>`).join('')
        || '<li class="list-group-item text-muted">' + Kit.escape(tr('js.account.no_sign_ins_recorded_yet', 'No sign-ins recorded yet.')) + '</li>');
    }).catch(err => Kit.toast(err.message, 'danger'));
  }

  $('#tokenList').on('click', '.revoke-token', function () {
    Kit.api('/auth/tokens/' + encodeURIComponent($(this).data('id')), { method: 'DELETE' })
      .then(() => { Kit.toast(tr('js.account.token_revoked', 'Token revoked'), 'success'); loadTokens(); })
      .catch(err => Kit.toast(err.message, 'danger'));
  });

  $('#passwordForm').on('submit', function (event) {
    event.preventDefault();
    const form = new FormData(this);
    Kit.api('/auth/password', { method: 'POST', body: { current_password: form.get('current_password'), new_password: form.get('new_password') } })
      .then(() => { Kit.toast(tr('js.account.password_changed', 'Password changed'), 'success'); this.reset(); })
      .catch(err => Kit.toast(err.message, 'danger'));
  });

  // School accounts (ADR-0016): link one while signed in, unlink, see what is linked.
  function loadIdentities() {
    return Kit.api('/auth/identities').then(data => {
      $('#identityList').html(data.identities.map(item => `
        <li class="list-group-item d-flex justify-content-between align-items-center">
          <span><strong>${Kit.escape(item.provider)}</strong> <span class="small text-muted">${Kit.escape(item.email || '')}</span></span>
          <button class="btn btn-outline-danger btn-sm unlink-identity" data-id="${Kit.escape(item.id)}">${Kit.escape(tr('js.account.unlink', 'Unlink'))}</button></li>`).join('')
        || '<li class="list-group-item text-muted small">' + Kit.escape(tr('js.account.no_school_account_linked', 'No school account linked.')) + '</li>');
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
      .then(() => { Kit.toast(tr('js.account.school_account_unlinked', 'School account unlinked'), 'success'); loadIdentities(); })
      .catch(err => Kit.toast(err.message, 'danger'));
  });
  $('#signOutEverywhere').on('click', () => {
    if (!window.confirm(tr('js.account.sign_out_on_every_computer_this', 'Sign out on every computer, this one too?'))) return;
    Kit.api('/auth/sessions/revoke', { method: 'POST', body: {} })
      .then(() => { window.location.href = '/auth/login'; })
      .catch(err => Kit.toast(err.message, 'danger'));
  });

  loadTokens();
  loadIdentities();
  loadSignIns();
})();
