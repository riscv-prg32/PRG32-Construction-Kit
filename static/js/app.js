window.Kit = {
  api(path, options) {
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
        const message = data && data.error ? data.error : response.statusText;
        const error = new Error(message);
        error.status = response.status;   // e.g. 409 version_conflict, 413 quota_exceeded (ADR-0017)
        error.code = data && data.code;
        error.data = data;
        throw error;
      }
      return data;
    });
  },
  // A save refused because the project was saved elsewhere after this window loaded it
  // (409 version_conflict, ADR-0017). Nothing was overwritten; the student chooses.
  // choices: {copy(): Promise, reload(), overwrite(currentVersion): Promise}
  versionConflict(error, choices) {
    $('#versionConflict').remove();
    const current = (error.data && error.data.current) || {};
    const dialog = $(`<div class="modal" id="versionConflict" tabindex="-1" role="dialog" aria-modal="true" aria-labelledby="versionConflictTitle">
      <div class="modal-dialog"><div class="modal-content">
        <div class="modal-header"><h2 class="modal-title h5" id="versionConflictTitle">Saved somewhere else</h2></div>
        <div class="modal-body"><p></p>
          <p class="small text-muted mb-0">Saved there: <span class="when"></span>. Your changes in this window are not lost yet.</p></div>
        <div class="modal-footer flex-wrap">
          <button type="button" class="btn btn-primary" data-choice="copy">Keep mine as a copy</button>
          <button type="button" class="btn btn-outline-secondary" data-choice="reload">Load the saved version</button>
          <button type="button" class="btn btn-outline-danger" data-choice="overwrite">Save mine over it</button>
        </div></div></div></div>`);
    dialog.find('.modal-body p').first().text(error.message);
    dialog.find('.when').text(current.updated_at || 'just now');
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
    banner.append($('<button type="button" class="btn btn-sm btn-warning ms-2">Reload this window</button>').on('click', () => window.location.reload()));
    $('body').prepend(banner);
  },
  toast(message, variant) {
    const id = 'toast-' + Date.now();
    const kind = variant || 'primary';
    const html = `
      <div id="${id}" class="toast align-items-center text-bg-${kind} border-0" role="status" aria-live="polite" aria-atomic="true">
        <div class="d-flex"><div class="toast-body"></div><button type="button" class="btn-close btn-close-white me-2 m-auto" aria-label="Close" data-bs-dismiss="toast"></button></div>
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
