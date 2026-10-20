(function () {
  let selectedProfileId = null;

  function loadProfiles() {
    return Kit.api('/api/publish_profiles').then(data => {
      if (!selectedProfileId && data.publish_profiles[0]) selectedProfileId = data.publish_profiles[0].id;
      $('#profileList').html(data.publish_profiles.map(profile => `
        <button class="list-group-item list-group-item-action profile-choice ${profile.id === selectedProfileId ? 'active' : ''}" data-id="${Kit.escape(profile.id)}">
          <div class="fw-semibold">${Kit.escape(profile.name)}</div>
          <div class="small ${profile.id === selectedProfileId ? '' : 'text-muted'}">${Kit.escape(profile.store_url)}${profile.has_token ? ' · token saved' + (profile.token_expires_on ? ' (works until ' + Kit.escape(profile.token_expires_on) + ')' : '') : ''}${profile.uses_sso ? ' · publishes as you (single sign-on)' : ''}</div>
        </button>`).join('') || '<div class="list-group-item text-muted">No profiles yet.</div>');
    });
  }

  function canPublishPage() { return $('#publishPage').data('can-publish') === true; }

  function loadBundles() {
    return Kit.api('/api/artifacts').then(data => {
      const bundles = data.artifacts.filter(a => a.kind === 'store_bundle' || a.kind === 'source_bundle');
      $('#bundleList').html(bundles.map(artifact => {
        const publishable = artifact.metadata && artifact.metadata.publishable;
        return `<div class="card border-0 bg-light">
          <div class="card-body d-flex flex-wrap justify-content-between align-items-center gap-3">
            <div>
              <div class="fw-semibold">${Kit.escape(artifact.name)}</div>
              <div class="small text-muted">${Kit.escape(artifact.id)} · ${Kit.escape(artifact.kind)}</div>
              <div>${publishable ? '<span class="badge text-bg-success">contains .prg32</span>' : '<span class="badge text-bg-warning">source-only</span>'}</div>
            </div>
            <div class="d-flex gap-2">
              <a class="btn btn-outline-primary btn-sm" href="/api/artifacts/${encodeURIComponent(artifact.id)}/download">Download</a>
              ${publishable && canPublishPage() ? `<button class="btn btn-primary btn-sm publish-bundle" data-id="${Kit.escape(artifact.id)}" ${selectedProfileId ? '' : 'disabled'}>Review &amp; publish</button>` : ''}
            </div>
          </div>
        </div>`;
      }).join('') || '<div class="alert alert-info">No bundles yet. Open a project and click Compile Cartridge.</div>');
    });
  }

  function refresh() {
    return loadProfiles().then(loadBundles).catch(err => Kit.toast(err.message, 'danger'));
  }

  $('#profileForm').on('submit', function (event) {
    event.preventDefault();
    const form = new FormData(this);
    Kit.api('/api/publish_profiles', { method: 'POST', body: { name: form.get('name'), store_url: form.get('store_url'), bearer_token: form.get('bearer_token') || '' } })
      .then(profile => { selectedProfileId = profile.id; Kit.toast('Profile saved', 'success'); refresh(); })
      .catch(err => Kit.toast(err.message, 'danger'));
  });

  $('#profileList').on('click', '.profile-choice', function () { selectedProfileId = $(this).data('id'); refresh(); });
  $('#refreshPublish').on('click', refresh);
  // Step 1: ask the server what exactly would be published (ADR-0009).
  let pendingReview = null;

  function reviewTable(summary) {
    const rows = summary.architectures.map(a => `<tr><td>${Kit.escape(a.id)}</td><td><code>${Kit.escape(a.file)}</code></td>
      <td class="text-end">${Number(a.bytes).toLocaleString()} bytes</td><td><code class="small">${Kit.escape(a.sha256)}</code></td></tr>`).join('');
    return `<dl class="row mb-3">
        <dt class="col-sm-3">Store</dt><dd class="col-sm-9"><code>${Kit.escape(summary.store.origin)}</code> (${Kit.escape(summary.store.authentication.replace(/_/g, ' '))})</dd>
        <dt class="col-sm-3">Cartridge</dt><dd class="col-sm-9">${Kit.escape(summary.cartridge.title)} <code>${Kit.escape(summary.cartridge.id)}</code></dd>
        <dt class="col-sm-3">Version</dt><dd class="col-sm-9">${Kit.escape(summary.cartridge.version)}</dd>
        <dt class="col-sm-3">Bundle</dt><dd class="col-sm-9">${Kit.escape(summary.bundle.name)}, ${Number(summary.bundle.bytes).toLocaleString()} bytes<br><code class="small">${Kit.escape(summary.bundle.sha256)}</code></dd>
        <dt class="col-sm-3">After upload</dt><dd class="col-sm-9">${Kit.escape(summary.after_upload)}</dd>
      </dl>
      <div class="table-responsive"><table class="table table-sm align-middle">
        <thead><tr><th>Target</th><th>File</th><th class="text-end">Size</th><th>SHA-256</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }

  $('#bundleList').on('click', '.publish-bundle', function () {
    const bundleId = $(this).data('id');
    if (!selectedProfileId) { Kit.toast('Choose a publish profile first', 'warning'); return; }
    const request = { profile_id: selectedProfileId, bundle_artifact_id: bundleId };
    Kit.api('/api/publish/review', { method: 'POST', body: request })
      .then(review => {
        pendingReview = Object.assign({}, request, { review_token: review.review_token });
        $('#reviewBody').html(reviewTable(review.summary));
        $('#reviewConfirm').prop('checked', false);
        $('#confirmPublish').prop('disabled', true);
        bootstrap.Modal.getOrCreateInstance(document.getElementById('reviewModal')).show();
      })
      .catch(err => { $('#publishLog').text(err.message); Kit.toast(err.message, 'danger'); });
  });

  $('#reviewConfirm').on('change', function () { $('#confirmPublish').prop('disabled', !this.checked); });

  // Step 2: the explicit confirmation, tied to the reviewed summary by its token.
  $('#confirmPublish').on('click', function () {
    if (!pendingReview || !$('#reviewConfirm').prop('checked')) return;
    $(this).prop('disabled', true);
    $('#publishLog').text('Sending the reviewed bundle to the Store...');
    Kit.api('/api/publish', { method: 'POST', body: Object.assign({ confirm: true }, pendingReview) })
      .then(result => {
        bootstrap.Modal.getOrCreateInstance(document.getElementById('reviewModal')).hide();
        $('#publishLog').text(JSON.stringify({ state: result.state, duplicate: result.duplicate, result: result.result }, null, 2));
        const ok = result.state === 'submitted';
        Kit.toast(ok ? (result.duplicate ? 'Already sent earlier: nothing sent again' : 'Sent: waiting for review at the Store')
          : 'The Store did not accept it: ' + (result.result && result.result.message || 'see the response'), ok ? 'success' : 'warning');
      })
      .catch(err => { $('#publishLog').text(err.message); Kit.toast(err.message + ' You can try again.', 'danger'); $(this).prop('disabled', false); });
  });

  refresh();
})();
