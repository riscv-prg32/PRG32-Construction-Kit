const CACHE_NAME = 'prg32-kit-v1';
const APP_SHELL = [
  '/',
  '/sprites',
  '/artifacts',
  '/publish',
  '/documentation',
  '/static/css/app.css',
  '/static/js/app.js',
  '/static/js/dashboard.js',
  '/static/js/blockly_blocks.js',
  '/static/js/simulator.js',
  '/static/js/editor.js',
  '/static/js/sprite_editor.js',
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
  if (event.request.method !== 'GET' || url.pathname.startsWith('/api/')) return;
  event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request).then(response => {
    const copy = response.clone();
    caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
    return response;
  }).catch(() => cached)));
});
