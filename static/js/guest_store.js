// Guest projects, kept in this browser only (ADR-0017, ADR-0023).
//
// - IndexedDB database "prg32-kit-guest" (version 2):
//   store "projects": {id, title, description, author, tags, blocks_json, game_json, version,
//                      audio: {document, version} or null, created_at, updated_at};
//                      backgrounds: [{id, name, kind: "background", data, version, ...}] (Backgrounds);
//   store "sprites":  {id, project_id, name, width, height, pixels, data_url, palette, created_at, updated_at}.
//   Version 1 had projects with a title and blocks only; they open with the other fields empty.
// - Nothing is stored on the server unless the student, signed in, moves the projects into
//   their account (moveToAccount): each project is created on the server first and deleted
//   here only after the server confirmed it. (The guest workspace asks the server to turn
//   blocks into C or to preview a sound, without the server keeping them: guest_api.js.)
// - Space: estimate() reports what the browser allows; persist() asks the browser not to
//   evict the data. A full disk keeps the old copy and says so (QuotaExceededError).
// - Files: exportFile() and importText() use the kit's project JSON
//   (prg32-construction-kit-project-1.0), which the dashboard's Import also reads.
window.PRG32GuestStore = (function () {
  'use strict';
  const DB_NAME = 'prg32-kit-guest';
  const STORE = 'projects';
  const SPRITES = 'sprites';
  const VERSION = 2;
  const LEGACY_KEY = 'prg32-offline-scratchpad';   // the old single scratchpad (localStorage)
  const FORMAT = 'prg32-construction-kit-project-1.0';
  let opened = null;

  function request(req) {
    return new Promise((resolve, reject) => {
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(friendly(req.error));
    });
  }

  function friendly(error) {
    if (error && error.name === 'QuotaExceededError') {
      const full = new Error('This browser has no space left for guest projects. Save your project as a file, '
        + 'then delete old ones here.');
      full.code = 'quota_exceeded';
      return full;
    }
    return error || new Error('This browser cannot keep guest projects (private window?).');
  }

  function open() {
    if (opened) return opened;
    opened = new Promise((resolve, reject) => {
      if (!window.indexedDB) return reject(new Error('This browser cannot keep guest projects.'));
      const req = indexedDB.open(DB_NAME, VERSION);
      req.onupgradeneeded = () => {
        if (!req.result.objectStoreNames.contains(STORE)) req.result.createObjectStore(STORE, { keyPath: 'id' });
        if (!req.result.objectStoreNames.contains(SPRITES)) {
          req.result.createObjectStore(SPRITES, { keyPath: 'id' }).createIndex('project_id', 'project_id');
        }
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(friendly(req.error));
    });
    return opened;
  }

  function store(mode, name) {
    return open().then(db => db.transaction(name || STORE, mode).objectStore(name || STORE));
  }

  function newId(prefix) {
    return prefix + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8);
  }

  function object(value) { return value && typeof value === 'object' && !Array.isArray(value) ? value : {}; }

  // A project row with every field, also for rows saved by version 1.
  function complete(row) {
    if (!row) return row;
    return {
      id: row.id,
      title: String(row.title || 'Untitled game').slice(0, 200),
      description: String(row.description || ''),
      author: String(row.author || ''),
      tags: Array.isArray(row.tags) ? row.tags : [],
      blocks_json: object(row.blocks_json),
      game_json: object(row.game_json),
      version: Number.isInteger(row.version) ? row.version : 0,
      audio: row.audio && typeof row.audio === 'object' ? row.audio : null,
      backgrounds: Array.isArray(row.backgrounds) ? row.backgrounds : [],
      created_at: row.created_at,
      updated_at: row.updated_at,
      deleted_at: null,
      owner_id: null,
    };
  }

  function done(transactionStore) {
    return new Promise((resolve, reject) => {
      transactionStore.transaction.oncomplete = () => resolve();
      transactionStore.transaction.onerror = () => reject(friendly(transactionStore.transaction.error));
      transactionStore.transaction.onabort = () => reject(friendly(transactionStore.transaction.error));
    });
  }

  function list() {
    return store('readonly').then(s => request(s.getAll()))
      .then(rows => rows.map(complete).sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at))));
  }

  function get(id) { return store('readonly').then(s => request(s.get(id))).then(complete); }

  // Save a project: the fields given replace the stored ones, the others are kept. Every save
  // raises "version" by one, as the server does (a stale window can then notice).
  function save(project) {
    const now = new Date().toISOString();
    const id = project.id || newId('guest-');
    return get(id).then(old => {
      const row = complete(Object.assign({}, old || { created_at: now }, project, { id, updated_at: now }));
      row.version = ((old && old.version) || 0) + 1;
      return store('readwrite').then(s => { s.put(row); return done(s); }).then(() => row);
    });
  }

  // Remove a project together with its sprites.
  function remove(id) {
    return listSprites(id).then(sprites => open().then(db => {
      const tx = db.transaction([STORE, SPRITES], 'readwrite');
      tx.objectStore(STORE).delete(id);
      sprites.forEach(sprite => tx.objectStore(SPRITES).delete(sprite.id));
      return new Promise((resolve, reject) => {
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(friendly(tx.error));
      });
    }));
  }

  function clear() {
    return open().then(db => {
      const tx = db.transaction([STORE, SPRITES], 'readwrite');
      tx.objectStore(STORE).clear();
      tx.objectStore(SPRITES).clear();
      return new Promise((resolve, reject) => { tx.oncomplete = () => resolve(); tx.onerror = () => reject(friendly(tx.error)); });
    });
  }

  // --- sprites (Sprite Lab) ------------------------------------------------------------------

  function completeSprite(row) {
    if (!row) return row;
    return {
      id: row.id, project_id: row.project_id || null, name: String(row.name || 'sprite').slice(0, 64),
      width: parseInt(row.width, 10) || 16, height: parseInt(row.height, 10) || 16,
      pixels: Array.isArray(row.pixels) ? row.pixels : [], data_url: String(row.data_url || ''),
      palette: row.palette && row.palette.mode === 'indexed' ? row.palette : {},
      created_at: row.created_at, updated_at: row.updated_at, owner_id: null,
    };
  }

  // Every sprite, or a project's sprites (projectId), newest first.
  function listSprites(projectId) {
    return store('readonly', SPRITES).then(s => request(s.getAll()))
      .then(rows => rows.map(completeSprite)
        .filter(row => projectId === undefined || row.project_id === projectId)
        .sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at))));
  }

  function getSprite(id) { return store('readonly', SPRITES).then(s => request(s.get(id))).then(completeSprite); }

  function saveSprite(sprite) {
    const now = new Date().toISOString();
    const id = sprite.id || newId('guest-sprite-');
    return getSprite(id).then(old => {
      const row = completeSprite(Object.assign({}, old || { created_at: now }, sprite, { id, updated_at: now }));
      return store('readwrite', SPRITES).then(s => { s.put(row); return done(s); }).then(() => row);
    });
  }

  function removeSprite(id) { return store('readwrite', SPRITES).then(s => { s.delete(id); return done(s); }); }

  function estimate() {
    if (!navigator.storage || !navigator.storage.estimate) return Promise.resolve(null);
    return navigator.storage.estimate().then(e => ({ usage: e.usage || 0, quota: e.quota || 0 }), () => null);
  }

  function persist() {
    if (!navigator.storage || !navigator.storage.persist) return Promise.resolve(false);
    return navigator.storage.persisted().then(already => already || navigator.storage.persist()).catch(() => false);
  }

  function exportFile(project) {
    return new Blob([JSON.stringify({ abi: FORMAT, project: { title: project.title, blocks_json: project.blocks_json } },
      null, 2)], { type: 'application/json' });
  }

  function importText(text) {
    const data = JSON.parse(text);
    const project = data && data.project ? data.project : data;
    const blocks = project && project.blocks_json ? project.blocks_json : project;
    if (!blocks || typeof blocks !== 'object' || Array.isArray(blocks)) throw new Error('This file is not a blocks project.');
    return { title: (project && project.title) || 'Imported game', blocks_json: blocks };
  }

  // The scratchpad of older kit versions becomes a guest project, once.
  function migrateScratchpad() {
    let old = null;
    try { old = JSON.parse(localStorage.getItem(LEGACY_KEY) || 'null'); } catch (_) { old = null; }
    if (!old) return Promise.resolve(null);
    return save({ title: 'Offline sketch', blocks_json: old }).then(row => {
      try { localStorage.removeItem(LEGACY_KEY); } catch (_) { /* nothing to remove */ }
      return row;
    });
  }

  // Signed in: create each guest project in the account, then delete it here.
  // createOnServer(project, sprites) -> Promise of the new server project: it creates the
  // project, its sound and its sprites (dashboard.js). Stops at the first failure. Sprites
  // that belong to no project move with moveSpritesToAccount.
  function moveToAccount(createOnServer) {
    const moved = [];
    return list().then(rows => rows.reduce((chain, row) => chain.then(() => listSprites(row.id)
      .then(sprites => createOnServer(row, sprites))
      .then(created => remove(row.id).then(() => moved.push({ guest: row.id, project: created.id })))), Promise.resolve())
      .then(() => ({ moved, left: rows.length - moved.length }))
      .catch(error => ({ moved, left: rows.length - moved.length, error })));
  }

  // createOnServer(sprite) -> Promise; the sprite is removed here once the server has it.
  function moveSpritesToAccount(createOnServer) {
    return listSprites().then(rows => rows.filter(row => !row.project_id).reduce((chain, row) =>
      chain.then(() => createOnServer(row).then(() => removeSprite(row.id))), Promise.resolve()));
  }

  return { list, get, save, remove, clear, estimate, persist, exportFile, importText, migrateScratchpad, moveToAccount,
    listSprites, getSprite, saveSprite, removeSprite, moveSpritesToAccount, FORMAT };
})();
