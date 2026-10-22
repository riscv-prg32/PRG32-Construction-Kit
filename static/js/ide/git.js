// The IDE's Git tool window (ADR-0025, docs/github.md): this project in a GitHub repository.
// Commit & push saves the project, then commits its files (with the student's message) to its
// folder in the repository chosen on the Account page; Pull takes the repository's version;
// the list shows the folder's latest commits. When both sides changed, the student chooses:
// keep both (a new copy), take GitHub's version, or put this version on GitHub.
(function () {
  'use strict';
  const projectId = $('#projectId').val();
  const api = '/api/projects/' + encodeURIComponent(projectId) + '/cloud/github';
  const box = $('#ideGit');
  let conflict = null;

  const MESSAGES = { created: 'Committed: the project is now a folder in the repository.', saved: 'Committed and pushed.',
    in_sync: 'GitHub already has this version.', overwritten: 'GitHub now has your version.',
    taken: 'You now have the GitHub version; your version is in History.', nothing_new: 'Nothing new on GitHub.' };

  function note(html) { box.html(`<p class="small mb-0">${html}</p>`); }

  function log(text, kind) { if (window.PRG32Ide && PRG32Ide.log) PRG32Ide.log('Git: ' + text, kind); }

  function render(github, history) {
    box.html(`<div class="d-flex flex-wrap gap-3 align-items-start">
      <form class="d-flex flex-wrap gap-2 align-items-end" id="gitCommitForm">
        <div><label class="form-label small mb-1" for="gitMessage">Commit message</label>
          <input class="form-control form-control-sm" id="gitMessage" maxlength="200" placeholder="What did you change?" required></div>
        <button class="btn btn-success btn-sm" type="submit"><i class="bi bi-cloud-upload" aria-hidden="true"></i> Commit &amp; push</button>
        <button class="btn btn-outline-primary btn-sm" type="button" id="gitPull"><i class="bi bi-cloud-download" aria-hidden="true"></i> Pull</button>
      </form>
      <div class="small text-muted align-self-center">${Kit.escape(github.repository)} · ${Kit.escape(github.branch || 'main')}
        ${history.linked ? ' · folder <code>' + Kit.escape(history.folder) + '</code>' : ' · not committed yet'}</div>
    </div>
    <div class="alert alert-warning small py-2 mt-2 mb-0" id="gitConflict" hidden>
      <p class="mb-2" id="gitConflictText"></p>
      <button class="btn btn-outline-secondary btn-sm" type="button" data-choice="copy">Keep both (a new copy)</button>
      <button class="btn btn-outline-primary btn-sm" type="button" data-choice="take_remote">Take GitHub's version</button>
      <button class="btn btn-outline-danger btn-sm" type="button" data-choice="overwrite">Put my version on GitHub</button>
    </div>
    <div class="small mt-2" id="gitStatus" role="status"></div>
    <ol class="list-unstyled small mt-2 mb-0" id="gitHistory" aria-label="Latest commits">${history.commits.map(commit => `
      <li><code>${Kit.escape(commit.sha)}</code> ${Kit.escape(commit.message)}
        <span class="text-muted">${Kit.escape(commit.date)}</span>
        ${commit.url ? `<a href="${Kit.escape(commit.url)}" target="_blank" rel="noopener">on GitHub</a>` : ''}</li>`).join('')
      || '<li class="text-muted">No commits yet.</li>'}</ol>`);
  }

  function load() {
    if (Kit.guest) return note('GitHub needs an account: <a href="/auth/login">sign in</a>, and your games come with you.');
    return Kit.api('/api/cloud').then(data => {
      const github = data.providers.find(item => item.name === 'github');
      if (!github) return note('GitHub is not set up on this kit. Your teacher can turn it on (docs/github.md).');
      if (!github.connected || github.needs_reconnect) {
        return note('Connect your GitHub account on the <a href="/account#cloud">Account page</a> first.');
      }
      if (!github.repository) return note('Choose the repository for your projects on the <a href="/account#cloud">Account page</a>.');
      return Kit.api(api + '/commits').then(history => render(github, history));
    }).catch(err => note(Kit.escape(err.message)));
  }

  function status(text, kind) { $('#gitStatus').attr('class', 'small mt-2 text-' + (kind || 'body')).text(text); }

  function send(action, body) {
    $('#gitConflict').prop('hidden', true);
    status('Working…', 'muted');
    const saved = action === 'push' && PRG32Ide.dirty ? PRG32Ide.save({ noCheck: true, quiet: true }) : Promise.resolve();
    return saved.then(() => Kit.api(api + '/' + action, { method: 'POST', body: body || {} }))
      .then(data => {
        status(MESSAGES[data.result] || 'Done.', 'success');
        log(MESSAGES[data.result] || 'done.', 'ok');
        if (data.result === 'taken') { window.location.reload(); return; }
        if (data.result === 'copied') { window.location.href = '/ide/' + encodeURIComponent(data.project.id); return; }
        const message = $('#gitMessage').val();
        return load().then(() => { if (action !== 'push') $('#gitMessage').val(message); });
      })
      .catch(err => {
        if (err.status === 409 && err.data && Array.isArray(err.data.choices) && err.data.choices.length) {
          conflict = { from: action, data: err.data, body: body || {} };
          $('#gitConflictText').text(err.message);
          $('#gitConflict [data-choice]').each(function () { $(this).prop('hidden', !err.data.choices.includes($(this).data('choice'))); });
          $('#gitConflict').prop('hidden', false);
          status('');
          return;
        }
        status(err.message, 'danger');
        log(err.message, 'error');
      });
  }

  box.on('submit', '#gitCommitForm', event => {
    event.preventDefault();
    send('push', { message: $('#gitMessage').val() });
  }).on('click', '#gitPull', () => send('pull'))
    .on('click', '#gitConflict [data-choice]', function () {
      const choice = $(this).data('choice');
      const data = conflict.data;
      if (choice === 'copy') return send(conflict.from === 'push' ? 'push' : 'pull', { choice: 'copy' });
      if (choice === 'take_remote') {
        if (!window.confirm("Replace your version here with GitHub's? Yours stays in History.")) return;
        return send('pull', { choice: 'take_remote', expected_version: data.local.version });
      }
      if (!window.confirm('Replace the version on GitHub with yours?')) return;
      return send('push', Object.assign({}, conflict.body, { choice: 'overwrite', expected_remote_revision: data.remote.revision }));
    });

  // Loaded the first time the Git tab is shown.
  let loaded = false;
  $('#panelTab-git').on('click focus', () => { if (!loaded) { loaded = true; load(); } });
  window.PRG32Git = { load };
})();
