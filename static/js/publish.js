(function () {
  let selectedProfileId = null;

  function loadProfiles() {
    return Kit.api('/api/publish_profiles').then(data => {
      if (!selectedProfileId && data.publish_profiles[0]) selectedProfileId = data.publish_profiles[0].id;
      $('#profileList').html(data.publish_profiles.map(profile => `
        <button class="list-group-item list-group-item-action profile-choice ${profile.id === selectedProfileId ? 'active' : ''}" data-id="${profile.id}">
          <div class="fw-semibold">${Kit.escape(profile.name)}</div>
          <div class="small ${profile.id === selectedProfileId ? '' : 'text-muted'}">${Kit.escape(profile.store_url)}</div>
        </button>`).join('') || '<div class="list-group-item text-muted">No profiles yet.</div>');
    });
  }

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
              <a class="btn btn-outline-primary btn-sm" href="/api/artifacts/${artifact.id}/download">Download</a>
              <button class="btn btn-primary btn-sm publish-bundle" data-id="${artifact.id}" ${selectedProfileId ? '' : 'disabled'}>Publish</button>
            </div>
          </div>
        </div>`;
      }).join('') || '<div class="alert alert-info">No bundles yet. Open a project and click Prepare Cartridge.</div>');
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
  $('#bundleList').on('click', '.publish-bundle', function () {
    const bundleId = $(this).data('id');
    if (!selectedProfileId) { Kit.toast('Choose a publish profile first', 'warning'); return; }
    $('#publishLog').text('Sending bundle ' + bundleId + ' to selected Cartridge Store profile...');
    Kit.api('/api/publish', { method: 'POST', body: { profile_id: selectedProfileId, bundle_artifact_id: bundleId } })
      .then(result => { $('#publishLog').text(JSON.stringify(result, null, 2)); Kit.toast(result.result.ok ? 'Publish request accepted' : 'Publish request returned an error', result.result.ok ? 'success' : 'warning'); })
      .catch(err => { $('#publishLog').text(err.message); Kit.toast(err.message, 'danger'); });
  });

  refresh();
})();
