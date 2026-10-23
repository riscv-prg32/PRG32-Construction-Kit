// Account page, "Your data" (ADR-0022): the person's own rights requests.
// Downloading uses the plain link (/api/me/privacy/export); this file sends and lists requests.
(function () {
  const KIND = {
    rectification: tr('js.privacy.correct', 'Correct'), erasure: tr('js.privacy.delete_my_account', 'Delete my account'), restriction: tr('js.privacy.pause_the_use_of_my_data', 'Pause the use of my data'),
    objection: tr('js.privacy.objection', 'Objection'), withdrawal: tr('js.privacy.withdraw_a_permission', 'Withdraw a permission'), access: tr('js.privacy.download', 'Download'), portability: tr('js.privacy.download', 'Download')
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
    if (kind === 'erasure' && !window.confirm(tr('js.privacy.ask_the_school_to_delete_your', 'Ask the school to delete your account and everything in it? This cannot be undone once they do it.'))) {
      return;
    }
    Kit.api('/api/me/privacy/requests', { method: 'POST', body: { kind, details: form.get('details') || '' } })
      .then(() => { Kit.toast(tr('js.privacy.request_sent_to_the_school', 'Request sent to the school'), 'success'); this.reset(); load(); })
      .catch(err => Kit.toast(err.message, 'danger'));
  });

  if ($('#privacyRequests').length) load();
}());
