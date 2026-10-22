// Cloud storage (ADR-0019): connect on the Account page, save/get on the dashboard.
// Nothing here runs offline or for guests; the server decides every conflict.
(function () {
  const PERMISSIONS = {
    google: 'only the files the kit creates in your Google Drive (it cannot see your other files)',
    onedrive: "only the kit's own folder in your OneDrive (Apps), plus your account's name and id",
    github: 'only the GitHub repositories I install the kit\'s GitHub App on (to read and write their files), plus my GitHub name'
  };

  // GitHub (ADR-0025): choose the repository (one the kit's GitHub App is installed on) and the branch.
  function githubChooser(item) {
    return `<div class="mt-2 small github-repo" data-provider="github">
      <div class="d-flex flex-wrap gap-2 align-items-end">
        <div><label class="form-label mb-1" for="githubRepository">Repository</label>
          <select class="form-select form-select-sm" id="githubRepository"><option value="">Loading…</option></select></div>
        <div><label class="form-label mb-1" for="githubBranch">Branch</label>
          <input class="form-control form-control-sm" id="githubBranch" value="${Kit.escape(item.branch || '')}" placeholder="main"></div>
        <button class="btn btn-primary btn-sm github-choose" type="button">Use this repository</button>
      </div>
      <p class="mb-0 mt-1 text-muted">Not in the list? <a href="${Kit.escape(item.install_url || 'https://github.com')}" target="_blank" rel="noopener">Install
        the kit's GitHub App</a> on the repository first, then reload this page.</p></div>`;
  }

  function loadRepositories(item) {
    Kit.api('/api/cloud/github/repositories').then(data => {
      $('#githubRepository').html(data.repositories.map(repo => `<option value="${Kit.escape(repo.full_name)}"
        ${repo.full_name === data.repository ? 'selected' : ''}>${Kit.escape(repo.full_name)}${repo.private ? ' (private)' : ''}</option>`).join('')
        || '<option value="">No repository yet: install the App first</option>');
      if (!$('#githubBranch').val()) $('#githubBranch').val(data.branch || '');
    }).catch(err => $('#githubRepository').html(`<option value="">${Kit.escape(err.message)}</option>`));
  }

  // --- Account page -----------------------------------------------------------------
  function providerBlock(item) {
    const name = Kit.escape(item.name);
    if (item.connected && !item.needs_reconnect) {
      return `<div class="border rounded p-2" data-provider="${name}">
        <div class="d-flex justify-content-between align-items-center">
          <span><strong>${Kit.escape(item.title)}</strong> <span class="small text-muted">${Kit.escape(item.account_name)}</span></span>
          <button class="btn btn-outline-danger btn-sm cloud-disconnect" data-provider="${name}" type="button">Disconnect</button>
        </div>
        ${item.name === 'github' ? githubChooser(item) : ''}
        <ul class="list-group list-group-flush small mt-2 cloud-files" data-provider="${name}"></ul></div>`;
    }
    const warning = item.needs_reconnect
      ? '<div class="alert alert-warning small py-1 mb-2">The connection has ended. Connect again to keep syncing.</div>' : '';
    return `<div class="border rounded p-2" data-provider="${name}">
      <strong>${Kit.escape(item.title)}</strong>${warning}
      <div class="form-check small mt-1">
        <input class="form-check-input cloud-consent" type="checkbox" id="consent-${name}" data-provider="${name}">
        <label class="form-check-label" for="consent-${name}">I allow the kit to use ${Kit.escape(PERMISSIONS[item.name] || item.scopes.join(', '))}.
          I can disconnect at any time.</label>
      </div>
      <button class="btn btn-primary btn-sm mt-2 cloud-connect" data-provider="${name}" type="button" disabled>Connect ${Kit.escape(item.title)}</button></div>`;
  }

  function loadFiles(provider) {
    const list = $(`.cloud-files[data-provider="${provider}"]`);
    Kit.api(`/api/cloud/${encodeURIComponent(provider)}/files`).then(data => {
      list.html(data.files.map(file => `<li class="list-group-item d-flex justify-content-between align-items-center gap-2 px-0">
        <span class="text-truncate">${Kit.escape(file.name)}${file.project_id ? ' <span class="badge text-bg-light">linked</span>' : ''}</span>
        <span class="text-nowrap"><button class="btn btn-outline-primary btn-sm cloud-open" data-provider="${provider}" data-file="${Kit.escape(file.file_id)}" type="button">Open as new project</button>
        <button class="btn btn-outline-danger btn-sm cloud-trash" data-provider="${provider}" data-file="${Kit.escape(file.file_id)}" data-revision="${Kit.escape(file.revision)}" type="button" aria-label="Move ${Kit.escape(file.name)} to the trash"><i class="bi bi-trash"></i></button></span></li>`).join('')
        || '<li class="list-group-item text-muted px-0">No projects saved here yet.</li>');
    }).catch(err => list.html(`<li class="list-group-item text-danger px-0">${Kit.escape(err.message)}</li>`));
  }

  function loadAccount() {
    Kit.api('/api/cloud').then(data => {
      if (!data.providers.length) return;
      $('#cloud').removeClass('d-none');
      $('#cloudProviders').html(data.providers.map(providerBlock).join(''));
      data.providers.filter(item => item.connected && !item.needs_reconnect).forEach(item => {
        if (item.name === 'github') {
          loadRepositories(item);
          if (!item.repository) return;     // no repository chosen yet: nothing to list
        }
        loadFiles(item.name);
      });
    }).catch(err => Kit.toast(err.message, 'danger'));
  }

  if ($('#cloud').length) {
    $('#cloudProviders')
      .on('click', '.github-choose', () => {
        Kit.api('/api/cloud/github/repository', { method: 'PUT',
          body: { repository: $('#githubRepository').val(), branch: $('#githubBranch').val() } })
          .then(chosen => { Kit.toast(`Projects go to ${chosen.repository} (${chosen.branch})`, 'success'); loadFiles('github'); })
          .catch(err => Kit.toast(err.message, 'danger'));
      })
      .on('change', '.cloud-consent', function () {
        $(`.cloud-connect[data-provider="${$(this).data('provider')}"]`).prop('disabled', !this.checked);
      })
      .on('click', '.cloud-connect', function () {
        Kit.api(`/api/cloud/${encodeURIComponent($(this).data('provider'))}/connect`, { method: 'POST', body: { consent: true } })
          .then(data => { window.location.href = data.redirect; })
          .catch(err => Kit.toast(err.message, 'danger'));
      })
      .on('click', '.cloud-disconnect', function () {
        if (!window.confirm('Disconnect? Your files stay in the cloud; the kit forgets its permission.')) return;
        Kit.api(`/api/cloud/${encodeURIComponent($(this).data('provider'))}/disconnect`, { method: 'POST', body: {} })
          .then(data => { Kit.toast(data.note || 'Disconnected', data.note ? 'warning' : 'success'); loadAccount(); })
          .catch(err => Kit.toast(err.message, 'danger'));
      })
      .on('click', '.cloud-open', function () {
        Kit.api(`/api/cloud/${encodeURIComponent($(this).data('provider'))}/files/${encodeURIComponent($(this).data('file'))}/open`,
          { method: 'POST', body: {} })
          .then(data => { window.location.href = '/ide/' + encodeURIComponent(data.project.id); })
          .catch(err => Kit.toast(err.message, 'danger'));
      })
      .on('click', '.cloud-trash', function () {
        if (!window.confirm('Move this file to the cloud trash? You can get it back from there.')) return;
        const provider = $(this).data('provider');
        Kit.api(`/api/cloud/${encodeURIComponent(provider)}/files/${encodeURIComponent($(this).data('file'))}?revision=${encodeURIComponent($(this).data('revision'))}`,
          { method: 'DELETE' })
          .then(() => { Kit.toast('Moved to the cloud trash', 'success'); loadFiles(provider); })
          .catch(err => { Kit.toast(err.message, 'danger'); loadFiles(provider); });
      });
    loadAccount();
  }

  // --- Dashboard ---------------------------------------------------------------------
  if (!$('#cloudModal').length) return;
  let project = null;          // {id, title}
  let conflict = null;         // {from: 'push'|'pull', data}

  function status(text, kind) {
    $('#cloudStatus').attr('class', 'small text-' + (kind || 'body')).text(text);
  }

  function showConflict(from, err) {
    conflict = { from, data: err.data };
    const choices = err.data.choices || [];
    $('#cloudConflictText').text(err.message);
    $('#cloudConflict [data-choice]').each(function () { $(this).toggleClass('d-none', !choices.includes($(this).data('choice'))); });
    $('#cloudConflict').removeClass('d-none');
  }

  function refused(from) {
    return err => {
      if (err.status === 409 && err.data && Array.isArray(err.data.choices) && err.data.choices.length) return showConflict(from, err);
      if (err.code === 'reconnect' || err.code === 'not_connected') return status(err.message + ' (Account page)', 'danger');
      status(err.message + (err.data && err.data.retryable ? ' Nothing was changed; you can try again.' : ''), 'danger');
    };
  }

  const MESSAGES = { created: 'Saved as a new cloud file.', saved: 'Saved to the cloud.', in_sync: 'The cloud copy is already up to date.',
    overwritten: 'The cloud copy now has your version.', taken: 'You now have the cloud version; your version is in History.',
    nothing_new: 'Nothing new in the cloud.', copied: 'The cloud version is now a new project.' };

  function send(action, body) {
    $('#cloudConflict').addClass('d-none');
    status('Working...', 'muted');
    const provider = $('#cloudProvider').val();
    return Kit.api(`/api/projects/${encodeURIComponent(project.id)}/cloud/${encodeURIComponent(provider)}/${action}`,
      { method: 'POST', body: body || {} })
      .then(data => {
        status(MESSAGES[data.result] || 'Done.', 'success');
        if (data.result === 'copied') window.location.href = '/ide/' + encodeURIComponent(data.project.id);
      })
      .catch(refused(action));
  }

  Kit.api('/api/cloud').then(data => {
    const connected = data.providers.filter(item => item.connected && !item.needs_reconnect);
    $('#cloudProvider').html(connected.map(item => `<option value="${Kit.escape(item.name)}">${Kit.escape(item.title)} (${Kit.escape(item.account_name)})</option>`).join(''));
    $('body').toggleClass('cloud-ready', connected.length > 0);
  }).catch(() => {});   // no cloud: the buttons stay hidden

  $('#projectGrid').on('click', '.cloud-project', function () {
    project = { id: $(this).data('id'), title: $(this).data('title') };
    $('#cloudProjectTitle').text(project.title);
    $('#cloudConflict').addClass('d-none');
    status('');
    bootstrap.Modal.getOrCreateInstance(document.getElementById('cloudModal')).show();
  });
  $('#cloudPush').on('click', () => send('push'));
  $('#cloudPull').on('click', () => send('pull'));
  $('#cloudConflict').on('click', '[data-choice]', function () {
    const choice = $(this).data('choice');
    const data = conflict.data;
    if (choice === 'copy') return send(conflict.from, { choice: 'copy' });
    if (choice === 'take_remote') {
      if (!window.confirm('Replace your version here with the cloud version? Yours stays in History.')) return;
      return send('pull', { choice: 'take_remote', expected_version: data.local.version });
    }
    if (!window.confirm('Replace the cloud copy with your version here?')) return;
    return send('push', { choice: 'overwrite', expected_remote_revision: data.remote.revision });
  });
})();
