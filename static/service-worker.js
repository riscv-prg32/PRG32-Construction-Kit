// PRG32-Construction-Kit service worker, served at /service-worker.js so it covers the whole kit.
//
// Rules (AGENTS.md, ADR-0012):
// - only static files are cached; signed-in pages, API answers and downloads never are
//   (a classroom computer is shared, and pages show the signed-in student's projects);
// - when a page cannot be loaded because the server is unreachable, the static offline
//   page is shown instead (a blocks scratchpad and a player for local .prg32 files);
// - bump CACHE_NAME whenever a file in APP_SHELL changes.
const CACHE_NAME = 'prg32-kit-v16';
const OFFLINE_PAGE = '/static/offline.html';
const APP_SHELL = [
  '/static/offline.html',
  '/static/offline-player.html',
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
  '/static/js/guest_store.js',
  '/static/js/offline.js',
  '/static/js/offline_player.js',
  '/static/js/csp_nonce.js',
  '/static/wasm/prg32-core.js',
  '/static/wasm/prg32-core.wasm',
  '/static/img/prg32-icon.svg',
  '/static/manifest.webmanifest',
  '/static/vendor/bootstrap/5.3.3/css/bootstrap.min.css',
  '/static/vendor/bootstrap/5.3.3/js/bootstrap.bundle.min.js',
  '/static/vendor/bootstrap-icons/1.11.3/font/bootstrap-icons.min.css',
  '/static/vendor/bootstrap-icons/1.11.3/font/fonts/bootstrap-icons.woff2',
  '/static/vendor/bootstrap-icons/1.11.3/font/fonts/bootstrap-icons.woff',
  '/static/vendor/jquery/3.7.1/jquery.min.js',
  '/static/vendor/blockly/11.2.1/blockly.min.js',
  '/static/vendor/blockly/11.2.1/media/sprites.png',
  '/static/vendor/blockly/11.2.1/media/sprites.svg',
  '/static/vendor/blockly/11.2.1/media/dropdown-arrow.svg',
  '/static/vendor/blockly/11.2.1/media/delete-icon.svg',
  '/static/vendor/blockly/11.2.1/media/foldout-icon.svg',
  '/static/vendor/blockly/11.2.1/media/resize-handle.svg',
  '/static/vendor/blockly/11.2.1/media/handopen.cur',
  '/static/vendor/blockly/11.2.1/media/handclosed.cur',
  '/static/vendor/blockly/11.2.1/media/handdelete.cur',
  '/static/vendor/blockly/11.2.1/media/1x1.gif'
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;
  if (request.mode === 'navigate' && !url.pathname.startsWith('/static/')) {
    // A page: always from the network and never stored. Offline: the static offline page.
    event.respondWith(fetch(request).catch(() => caches.match(OFFLINE_PAGE)));
    return;
  }
  if (!url.pathname.startsWith('/static/')) return;  // API answers and downloads: never cached
  // Static files: network first, so classrooms get updates at once; the cache is the offline fallback.
  event.respondWith(fetch(request).then(response => {
    if (response.ok) {
      const copy = response.clone();
      caches.open(CACHE_NAME).then(cache => cache.put(request, copy));
    }
    return response;
  }).catch(() => caches.match(request).then(cached => cached || Response.error())));
});
