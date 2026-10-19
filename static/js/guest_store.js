// Guest projects, kept in this browser only (ADR-0017).
//
// - IndexedDB database "prg32-kit-guest", store "projects": {id, title, blocks_json, created_at, updated_at}.
//   Nothing is ever sent to the server unless the student, signed in, moves the projects
//   into their account (moveToAccount): each project is created on the server first and
//   deleted here only after the server confirmed it.
// - Space: estimate() reports what the browser allows; persist() asks the browser not to
//   evict the data. A full disk keeps the old copy and says so (QuotaExceededError).
// - Files: exportFile() and importText() use the kit's project JSON
//   (prg32-construction-kit-project-1.0), which the dashboard's Import also reads.
window.PRG32GuestStore = (function () {
  'use strict';
  const DB_NAME = 'prg32-kit-guest';
  const STORE = 'projects';
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
      const req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = () => {
        if (!req.result.objectStoreNames.contains(STORE)) req.result.createObjectStore(STORE, { keyPath: 'id' });
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(friendly(req.error));
    });
    return opened;
  }

  function store(mode) {
    return open().then(db => db.transaction(STORE, mode).objectStore(STORE));
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
      .then(rows => rows.sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at))));
  }

  function get(id) { return store('readonly').then(s => request(s.get(id))); }

  function save(project) {
    const now = new Date().toISOString();
    const row = {
      id: project.id || 'guest-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8),
      title: String(project.title || 'Untitled game').slice(0, 200),
      blocks_json: project.blocks_json && typeof project.blocks_json === 'object' ? project.blocks_json : {},
      created_at: project.created_at || now,
      updated_at: now,
    };
    return store('readwrite').then(s => { s.put(row); return done(s); }).then(() => row);
  }

  function remove(id) { return store('readwrite').then(s => { s.delete(id); return done(s); }); }

  function clear() { return store('readwrite').then(s => { s.clear(); return done(s); }); }

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
  // createOnServer(project) -> Promise (Kit.api POST). Stops at the first failure.
  function moveToAccount(createOnServer) {
    const moved = [];
    return list().then(rows => rows.reduce((chain, row) => chain.then(() => createOnServer(row)
      .then(created => remove(row.id).then(() => moved.push({ guest: row.id, project: created.id })))), Promise.resolve())
      .then(() => ({ moved, left: rows.length - moved.length }))
      .catch(error => ({ moved, left: rows.length - moved.length, error })));
  }

  return { list, get, save, remove, clear, estimate, persist, exportFile, importText, migrateScratchpad, moveToAccount,
    FORMAT };
})();
