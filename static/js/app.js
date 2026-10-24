window.Kit = {
  // No account (the guest workspace, ADR-0023): the pages' API calls are answered in this
  // browser by guest_api.js, and nothing is saved on the server.
  guest: $('meta[name="prg32-guest"]').attr('content') === '1',
  api(path, options) {
    if (Kit.guest && window.PRG32GuestApi) return PRG32GuestApi.request(path, options);
    const opts = options || {};
    opts.headers = opts.headers || {};
    // Tells the server this request comes from the kit's own pages (blocks cross-site form posts).
    opts.headers['X-PRG32-Kit'] = '1';
    // The account this window was opened as. If somebody signs in as another
    // user in a different window, the server refuses instead of saving or
    // building with the wrong account.
    const user = $('meta[name="prg32-user"]').attr('content');
    if (user) opts.headers['X-PRG32-User'] = user;
    if (opts.body && !(opts.body instanceof FormData)) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(opts.body);
    }
    return fetch(path, opts).then(async response => {
      const contentType = response.headers.get('content-type') || '';
      // JSON, raw bytes (an ArrayBuffer, e.g. an audio block) or text.
      const data = contentType.includes('application/json') ? await response.json()
        : contentType.includes('application/octet-stream') && response.ok ? await response.arrayBuffer()
        : await response.text();
      if (response.status === 401) {
        window.location.href = '/auth/login?next=' + encodeURIComponent(window.location.pathname);
      }
      if (response.status === 409 && data && data.code === 'user_changed') {
        Kit.userChanged(data.error);
      }
      if (!response.ok) {
        // A message the server wrote with its catalog key (messages.py) is shown in the reader's
        // language; the English the server sent is the fallback.
        const english = data && data.error ? data.error : response.statusText;
        const message = data && data.message_key ? Kit.serverMessage(data, english) : english;
        const error = new Error(message);
        error.status = response.status;   // e.g. 409 version_conflict, 413 quota_exceeded (ADR-0017)
        error.code = data && data.code;
        error.data = data;
        throw error;
      }
      return data;
    });
  },
  // The text of a server message ({error, message_key, params}) in the reader's language. A message
  // about a place in the source ("Line 6: ...") keeps that place in front.
  serverMessage(data, english) {
    const translated = tr(data.message_key, english.replace(/^Line \d+: /, ''), data.params || {});
    const line = /^Line (\d+): /.exec(english);
    return line ? tr('js.ide.line_n', 'Line {line}: ', { line: line[1] }) + translated : translated;
  },
  // Download a file the server makes (an export). For a guest, it is made in this browser.
  download(path) {
    if (Kit.guest && window.PRG32GuestApi) return PRG32GuestApi.download(path);
    window.location.href = path;
    return Promise.resolve();
  },
  // Something a guest tried needs an account (building, publishing, samples...). The work stays
  // in this browser; signing in offers to move it into the account (Projects page).
  signInNeeded(what) {
    $('#signInNeeded').remove();
    const back = encodeURIComponent(window.location.pathname);
    const dialog = $(`<div class="modal" id="signInNeeded" tabindex="-1" role="dialog" aria-modal="true" aria-labelledby="signInNeededTitle">
      <div class="modal-dialog"><div class="modal-content">
        <div class="modal-header"><h2 class="modal-title h5" id="signInNeededTitle">${tr('js.app.sign_in_to_keep_going', 'Sign in to keep going')}</h2>
          <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="${tr('common.close', 'Close')}"></button></div>
        <div class="modal-body"><p class="what-needs"></p>
          <p class="mb-0">${tr('js.app.your_games_are_safe_after_sign_in', 'Your games are safe in this browser. After you sign in, the Projects page offers to move them into your account, so you can build real cartridges and share them.')}</p></div>
        <div class="modal-footer">
          <a class="btn btn-primary" href="/auth/login?next=${back}">${tr('common.sign_in', 'Sign in')}</a>
          <a class="btn btn-outline-secondary" href="/auth/register">${tr('common.create_an_account', 'Create an account')}</a>
          <button type="button" class="btn btn-link" data-bs-dismiss="modal">${tr('js.app.not_now', 'Not now')}</button>
        </div></div></div></div>`);
    dialog.find('.what-needs').text(tr('js.app.what_needs_an_account', '{what} needs an account.', { what }));
    $('body').append(dialog);
    new bootstrap.Modal(dialog[0]).show();
  },
  // A save refused because the project was saved elsewhere after this window loaded it
  // (409 version_conflict, ADR-0017). Nothing was overwritten; the student chooses.
  // choices: {copy(): Promise, reload(), overwrite(currentVersion): Promise}
  versionConflict(error, choices) {
    $('#versionConflict').remove();
    const current = (error.data && error.data.current) || {};
    const dialog = $(`<div class="modal" id="versionConflict" tabindex="-1" role="dialog" aria-modal="true" aria-labelledby="versionConflictTitle">
      <div class="modal-dialog"><div class="modal-content">
        <div class="modal-header"><h2 class="modal-title h5" id="versionConflictTitle">${tr('js.app.saved_somewhere_else', 'Saved somewhere else')}</h2></div>
        <div class="modal-body"><p></p>
          <p class="small text-muted mb-0 when-saved"></p></div>
        <div class="modal-footer flex-wrap">
          <button type="button" class="btn btn-primary" data-choice="copy">${tr('js.app.keep_mine_as_a_copy', 'Keep mine as a copy')}</button>
          <button type="button" class="btn btn-outline-secondary" data-choice="reload">${tr('js.app.load_the_saved_version', 'Load the saved version')}</button>
          <button type="button" class="btn btn-outline-danger" data-choice="overwrite">${tr('js.app.save_mine_over_it', 'Save mine over it')}</button>
        </div></div></div></div>`);
    dialog.find('.modal-body p').first().text(error.message);
    dialog.find('.when-saved').text(tr('js.app.saved_there_changes_not_lost', 'Saved there: {when}. Your changes in this window are not lost yet.', { when: current.updated_at ? Kit.when(current.updated_at) : tr('js.app.just_now', 'just now') }));
    $('body').append(dialog);
    const modal = new bootstrap.Modal(dialog[0], { backdrop: 'static', keyboard: false });
    dialog.on('click', '[data-choice]', function () {
      const choice = $(this).data('choice');
      modal.hide();
      if (choice === 'reload') return choices.reload();
      const done = choice === 'copy' ? choices.copy() : choices.overwrite(current.version);
      Promise.resolve(done).catch(err => Kit.toast(err.message, 'danger'));
    });
    modal.show();
  },
  userChanged(message) {
    if ($('#userChangedBanner').length) return;
    const banner = $('<div id="userChangedBanner" class="alert alert-warning m-0 rounded-0 text-center" role="alert"></div>');
    banner.text(message + ' ');
    banner.append($('<button type="button" class="btn btn-sm btn-warning ms-2"></button>').text(tr('js.app.reload_this_window', 'Reload this window')).on('click', () => window.location.reload()));
    $('body').prepend(banner);
  },
  toast(message, variant) {
    const id = 'toast-' + Date.now();
    const kind = variant || 'primary';
    const html = `
      <div id="${id}" class="toast align-items-center text-bg-${kind} border-0" role="status" aria-live="polite" aria-atomic="true">
        <div class="d-flex"><div class="toast-body"></div><button type="button" class="btn-close btn-close-white me-2 m-auto" aria-label="${tr('common.close', 'Close')}" data-bs-dismiss="toast"></button></div>
      </div>`;
    $('#toastArea').append(html);
    $('#' + id + ' .toast-body').text(message);
    const toast = new bootstrap.Toast(document.getElementById(id), { delay: 3600 });
    toast.show();
    document.getElementById(id).addEventListener('hidden.bs.toast', () => $('#' + id).remove());
  },
  escape(text) {
    return $('<div>').text(text == null ? '' : String(text)).html();
  },
  // A saved time (ISO 8601, from the server or this browser) as the student's local date and time.
  when(value) {
    const time = Date.parse(value);
    if (!value || Number.isNaN(time)) return value || '';
    // In the reader's interface language (ADR-0027), not only the browser's.
    return new Date(time).toLocaleString(window.PRG32I18n ? PRG32I18n.locale : undefined, { dateStyle: 'medium', timeStyle: 'short' });
  },
  tags(value) {
    if (!Array.isArray(value)) return '';
    return value.map(tag => `<span class="tag-pill">${Kit.escape(tag)}</span>`).join('');
  }
};

// The editor, the IDE and AudioStudio carry the open project's id: remember it so the
// AudioStudio menu item can offer it first (localStorage, listed on /privacy#storage).
$(function () {
  const projectId = $('#projectId').val();
  if (!projectId) return;
  try { localStorage.setItem('prg32-kit-last-project', projectId); } catch (_) { /* private window */ }
});

// The top menu of an open project (base.html): which of Editor, Sprite Lab, AudioStudio, Debug
// and Deploy is shown now.
Kit.projectMenu = {
  mark(item) {
    $('[data-ide-tool]').removeClass('active').removeAttr('aria-current');
    $('[data-ide-tool="' + item + '"]').addClass('active').attr('aria-current', 'page');
  },
};
$(function () {
  if (!$('#navCloseProject').length) return;
  const hash = window.location.hash.slice(1);
  const page = { '/player': 'player', '/deploy': 'deploy', '/evaluate': 'evaluate' }[window.location.pathname];
  Kit.projectMenu.mark(page || (hash === 'sprites' || hash === 'sound' ? hash : 'editor'));
});

// The Day/Night switch (base.html): this reader's colours, kept in this browser; theme.js applies
// them before the next page is drawn. Pages that draw their own colours listen for kit:color-scheme.
$(function () {
  const button = $('#schemeSwitch');
  if (!button.length) return;
  const root = document.documentElement;
  function show() {
    const night = root.getAttribute('data-bs-theme') === 'dark';
    button.attr('aria-pressed', String(night))
      .attr('title', night ? tr('base.day_light_colours', 'Day: light colours') : tr('base.night_dark_colours', 'Night: dark colours'));
    button.find('i').attr('class', night ? 'bi bi-sun' : 'bi bi-moon-stars');
  }
  show();
  button.on('click', () => {
    const night = root.getAttribute('data-bs-theme') !== 'dark';
    root.setAttribute('data-bs-theme', night ? 'dark' : 'light');
    try { localStorage.setItem('prg32-kit-color-scheme', night ? 'night' : 'day'); } catch (_) { /* private window */ }
    show();
    $(document).trigger('kit:color-scheme', [night]);
  });
});

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    // Served from the root so it covers every page (it caches static files only).
    navigator.serviceWorker.register('/service-worker.js', { scope: '/' }).catch(() => {});
    // Older versions registered it under /static/, where it could not cover the pages.
    navigator.serviceWorker.getRegistrations().then(registrations => registrations
      .filter(registration => new URL(registration.scope).pathname === '/static/')
      .forEach(registration => registration.unregister())).catch(() => {});
  });
}
