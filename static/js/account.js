(function () {
  function loadTokens() {
    return Kit.api('/auth/tokens').then(data => {
      $('#tokenList').html(data.tokens.map(token => `
        <div class="list-group-item d-flex justify-content-between align-items-center">
          <div><div class="fw-semibold">${Kit.escape(token.label)}</div>
            <div class="small text-muted">made ${Kit.escape(token.created_at)} · last used ${Kit.escape(token.last_used || 'never')}</div></div>
          <button class="btn btn-outline-danger btn-sm revoke-token" data-id="${Kit.escape(token.id)}">Revoke</button>
        </div>`).join('') || '<div class="list-group-item text-muted">No tokens yet.</div>');
    }).catch(err => Kit.toast(err.message, 'danger'));
  }

  $('#tokenForm').on('submit', function (event) {
    event.preventDefault();
    const label = new FormData(this).get('label') || 'API token';
    Kit.api('/auth/tokens', { method: 'POST', body: { label } }).then(data => {
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

  loadTokens();
})();
