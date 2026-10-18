const CACHE_NAME = 'prg32-kit-v11';
// Only static files are kept. Pages show the signed-in student's name and
// projects, and a classroom computer is shared, so pages are never cached.
const APP_SHELL = [
  '/static/css/app.css',
  '/static/js/app.js',
  '/static/js/dashboard.js',
  '/static/js/blockly_blocks.js',
  '/static/js/simulator.js',
  '/static/js/editor.js',
  '/static/js/sprite_editor.js',
  '/static/js/prg32_runtime.js',
  '/static/js/player.js',
  '/static/js/prg32_debugger.js',
  '/static/wasm/prg32-core.js',
  '/static/wasm/prg32-core.wasm',
  '/static/img/prg32-icon.svg',
  '/static/manifest.webmanifest'
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  // Never keep pages, API answers or downloads: they belong to whoever is signed in.
  if (event.request.method !== 'GET' || url.origin !== self.location.origin || !url.pathname.startsWith('/static/')) return;
  // Network first, so classrooms get updates right away; the cache is the offline fallback.
  event.respondWith(fetch(event.request).then(response => {
    if (response.ok || response.type === 'opaque') {
      const copy = response.clone();
      caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
    }
    return response;
  }).catch(() => caches.match(event.request).then(cached => cached || Response.error())));
});
