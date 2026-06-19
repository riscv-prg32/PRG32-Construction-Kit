window.Kit = {
  api(path, options) {
    const opts = options || {};
    opts.headers = opts.headers || {};
    if (opts.body && !(opts.body instanceof FormData)) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(opts.body);
    }
    return fetch(path, opts).then(async response => {
      const contentType = response.headers.get('content-type') || '';
      const data = contentType.includes('application/json') ? await response.json() : await response.text();
      if (!response.ok) {
        const message = data && data.error ? data.error : response.statusText;
        throw new Error(message);
      }
      return data;
    });
  },
  toast(message, variant) {
    const id = 'toast-' + Date.now();
    const kind = variant || 'primary';
    const html = `
      <div id="${id}" class="toast align-items-center text-bg-${kind} border-0" role="status" aria-live="polite" aria-atomic="true">
        <div class="d-flex"><div class="toast-body"></div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>
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

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/static/service-worker.js').catch(() => {}));
}
