// The "Cookies & storage" note at the bottom of every page (docs/privacy/notices/storage.md).
// The kit sets no tracking or advertising cookies, so there is nothing to accept or refuse:
// the note only tells the visitor what is kept, once per notice version. Pressing OK is
// remembered in this browser (localStorage), never on the server.
(function () {
  const KEY = 'prg32-kit-storage-notice';
  const notice = document.getElementById('storageNotice');
  if (!notice) return;
  const version = notice.getAttribute('data-version') || '1';
  let seen = null;
  try { seen = localStorage.getItem(KEY); } catch (_) { /* private window: show it every time */ }
  if (seen === version) return;
  notice.hidden = false;
  const ok = document.getElementById('storageNoticeOk');
  ok.addEventListener('click', function () {
    try { localStorage.setItem(KEY, version); } catch (_) { /* private window */ }
    notice.hidden = true;
  });
})();
