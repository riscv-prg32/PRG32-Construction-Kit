// Colour scheme "auto" (Settings page, Appearance): follow the computer's light or dark
// setting. Loaded in <head>, before the page is drawn, so the page never flashes the wrong one.
(function () {
  const root = document.documentElement;
  if (root.getAttribute('data-color-scheme') !== 'auto' || !window.matchMedia) return;
  const dark = window.matchMedia('(prefers-color-scheme: dark)');
  function apply() { root.setAttribute('data-bs-theme', dark.matches ? 'dark' : 'light'); }
  apply();
  if (dark.addEventListener) dark.addEventListener('change', apply);
})();
