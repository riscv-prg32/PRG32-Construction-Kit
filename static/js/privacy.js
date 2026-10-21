// Account page, "Your data" (ADR-0022): the person's own rights requests.
// Downloading uses the plain link (/api/me/privacy/export); this file sends and lists requests.
(function () {
  const KIND = {
    rectification: 'Correct', erasure: 'Delete my account', restriction: 'Pause the use of my data',
    objection: 'Objection', withdrawal: 'Withdraw a permission', access: 'Download', portability: 'Download'
  };

  function load() {
    return Kit.api('/api/me/privacy/requests').then(data => {
      $('#privacyRequests').html(data.requests.map(item => `
        <div class="list-group-item small">
          <div class="fw-semibold">${Kit.escape(KIND[item.kind] || item.kind)}: ${Kit.escape(item.status)}</div>
          <div class="text-muted">sent ${Kit.escape(item.received_at)} · answer due by ${Kit.escape(item.due_at)}
            ${item.completed_at ? ' · answered ' + Kit.escape(item.completed_at) : ''}</div>
        </div>`).join(''));
    }).catch(err => Kit.toast(err.message, 'danger'));
  }

  $('#privacyRequestForm').on('submit', function (event) {
    event.preventDefault();
    const form = new FormData(this);
    const kind = form.get('kind');
    if (kind === 'erasure' && !window.confirm('Ask the school to delete your account and everything in it? This cannot be undone once they do it.')) {
      return;
    }
    Kit.api('/api/me/privacy/requests', { method: 'POST', body: { kind, details: form.get('details') || '' } })
      .then(() => { Kit.toast('Request sent to the school', 'success'); this.reset(); load(); })
      .catch(err => Kit.toast(err.message, 'danger'));
  });

  if ($('#privacyRequests').length) load();
}());
