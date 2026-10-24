// The colour scheme, Day or Night. Loaded in <head>, before the page is drawn, so the page never
// flashes the wrong one:
// - the reader's own choice with the Day/Night switch in the menu bar (app.js), kept in this
//   browser (localStorage prg32-kit-color-scheme, listed on /privacy#storage);
// - else the Settings page's choice (Appearance); "auto" follows the computer's light or dark setting.
(function () {
  const root = document.documentElement;
  let chosen = null;
  try { chosen = localStorage.getItem('prg32-kit-color-scheme'); } catch (_) { /* private window */ }
  if (chosen === 'day' || chosen === 'night') {
    root.setAttribute('data-bs-theme', chosen === 'night' ? 'dark' : 'light');
    return;
  }
  if (root.getAttribute('data-color-scheme') !== 'auto' || !window.matchMedia) return;
  const dark = window.matchMedia('(prefers-color-scheme: dark)');
  function apply() { root.setAttribute('data-bs-theme', dark.matches ? 'dark' : 'light'); }
  apply();
  if (dark.addEventListener) dark.addEventListener('change', apply);
})();
