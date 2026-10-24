// The guest workspace (ADR-0023, docs/guest_mode.md): the kit's pages, without an account.
//
// The pages talk to the kit through Kit.api('/api/...'). For a visitor without an account,
// app.js hands those calls to PRG32GuestApi.request instead, and this file answers them from
// this browser (guest_store.js: IndexedDB), in the same shape the server would. So the editor,
// the IDE, Sprite Lab and AudioStudio work unchanged, and the games never leave the browser.
//
// A few answers need the server, which works on what the browser sends and keeps nothing
// (prg32_construction_kit/guest_api.py): turning blocks into C and assembly, checking and
// previewing a sound, turning a sprite into C, and copying an example game.
//
// Building a cartridge, publishing, classes, samples and history need an account: those calls
// open the "Sign in to keep going" dialog (Kit.signInNeeded) and are refused.
window.PRG32GuestApi = (function () {
  'use strict';
  const store = window.PRG32GuestStore;

  function fail(message, status, code, data) {
    const error = new Error(message);
    error.status = status;
    error.code = code;
    error.data = data || { error: message, code };
    return Promise.reject(error);
  }

  function notFound() { return fail(tr('js.guest_api.not_found_in_this_browser', 'Not found in this browser'), 404, 'not_found'); }

  function needsAccount(what) {
    if (window.Kit && Kit.signInNeeded) Kit.signInNeeded(what);
    return fail(what + tr('js.guest_api.needs_an_account_sign_in_first', ' needs an account: sign in first. Your games here stay in this browser.'), 401, 'sign_in_required');
  }

  // A real request to the guest API on the server (stateless).
  function server(path, body) {
    const options = { method: body === undefined ? 'GET' : 'POST', headers: { 'X-PRG32-Kit': '1' } };
    if (body !== undefined) {
      options.headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(body);
    }
    return fetch(path, options).then(async response => {
      const binary = (response.headers.get('content-type') || '').includes('application/octet-stream');
      const data = binary && response.ok ? await response.arrayBuffer() : await response.json().catch(() => ({}));
      if (!response.ok) return fail((data && data.error) || response.statusText, response.status, data && data.code, data);
      return data;
    });
  }

  // --- projects ------------------------------------------------------------------------------

  const PROJECT_FIELDS = ['title', 'description', 'author', 'tags', 'blocks_json', 'game_json'];

  function pick(body, fields) {
    const out = {};
    fields.forEach(field => { if (body && body[field] !== undefined) out[field] = body[field]; });
    return out;
  }

  function project(row) {
    if (!row) return row;
    const copy = Object.assign({}, row);
    delete copy.audio;
    return copy;
  }

  function listProjects(query) {
    if (query.get('deleted')) return Promise.resolve({ projects: [] });   // no "Recently deleted" here
    return store.list().then(rows => ({ projects: rows.map(project) }));
  }

  function createProject(body) {
    return store.save(Object.assign({ title: 'Untitled PRG32 Game', author: 'Student' }, pick(body, PROJECT_FIELDS)))
      .then(project);
  }

  function getProject(id) { return store.get(id).then(row => row ? project(row) : notFound()); }

  // Blocks, C, assembly or Python: chosen when the game is made, never changed by a save (ADR-0024, ADR-0026).
  function projectType(game) {
    const mode = game && typeof game === 'object' ? game.source_mode : null;
    return mode === 'c' || mode === 'asm' || mode === 'python' ? mode : 'blocks';
  }

  function typeLocked(row) {
    return fail(tr('js.guest_api.this_game_s_type_cannot_change', 'This game\'s type cannot change. A Blocks game can be converted to C or assembly once (Convert).'),
      409, 'type_locked', { code: 'type_locked', project_type: projectType(row.game_json) });
  }

  function putProject(id, body) {
    return store.get(id).then(row => {
      if (!row) return notFound();
      if (body.game_json !== undefined && projectType(body.game_json) !== projectType(row.game_json)) return typeLocked(row);
      const expected = body.expected_version;
      if (expected !== undefined && expected !== null && expected !== row.version) {
        return fail(tr('js.guest_api.this_game_was_saved_in_another', 'This game was saved in another window after you opened it.'), 409, 'version_conflict',
          { error: tr('js.guest_api.saved_elsewhere', 'saved elsewhere'), code: 'version_conflict', current: project(row) });
      }
      return store.save(Object.assign({ id }, pick(body, PROJECT_FIELDS))).then(project);
    });
  }

  function deleteProject(id) { return store.remove(id).then(() => ({ deleted: true })); }

  function duplicate(id, body) {
    return store.get(id).then(row => {
      if (!row) return notFound();
      const copy = Object.assign(pick(row, PROJECT_FIELDS), { audio: row.audio, title: (body && body.title) || row.title + ' (copy)' });
      return store.save(copy).then(created => store.listSprites(id)
        .then(sprites => Promise.all(sprites.map(sprite => store.saveSprite(Object.assign({}, sprite, { id: undefined, project_id: created.id })))))
        .then(() => project(created)));
    });
  }

  // One way: the server writes the Blocks game as code (and keeps nothing); it is stored here.
  function convertTo(id, body) {
    return store.get(id).then(row => {
      if (!row) return notFound();
      if (projectType(row.game_json) !== 'blocks') return typeLocked(row);
      const language = body && body.language;
      return server('/api/guest/convert_to', { project: pick(row, ['title', 'blocks_json']), language,
        audio_studio: row.audio ? row.audio.document : null })
        .then(answer => store.save({ id, game_json: answer.game_json })).then(project);
    });
  }

  function convert(id, body) {
    return store.get(id).then(row => {
      if (!row) return notFound();
      return server('/api/guest/convert', {
        project: pick(row, ['title', 'blocks_json', 'game_json']),
        audio_studio: row.audio ? row.audio.document : null,
        source_language: (body && body.source_language) || 'c',
      }).then(result => {
        const kept = { id: 'in this browser', name: tr('js.guest_api.not_saved_on_the_server', 'not saved on the server') };
        return Object.assign({ project: project(row), artifact: kept, artifacts: [kept], asm_artifact: kept }, result);
      });
    });
  }

  // Run: the server builds the game for the simulator and keeps nothing (/api/guest/run).
  function runGame(id) {
    return store.get(id).then(row => row ? server('/api/guest/run', {
      project: pick(row, ['title', 'blocks_json', 'game_json']),
      audio_studio: row.audio ? row.audio.document : null,
    }).then(answer => {
      if (answer.debug && answer.debug.cartridge) answer.debug.cartridge.project_id = id;   // breakpoints per game
      return answer;
    }) : notFound());
  }

  // A project file chosen on the Projects page: a blocks project (.json) opens here; an archive
  // (.zip, with sprites and sounds) needs an account.
  function importProject(form) {
    const file = form && form.get ? form.get('file') : null;
    if (!file) return fail(tr('js.guest_api.choose_a_file', 'Choose a file'), 400);
    if (!/\.json$/i.test(file.name || '')) return needsAccount(tr('js.guest_api.opening_a_project_archive_zip', 'Opening a project archive (.zip)'));
    return file.text().then(text => store.save(store.importText(text))).then(project);
  }

  function importExample(slug) {
    return server('/api/guest/examples/' + encodeURIComponent(slug))
      .then(data => store.save(pick(data.project, PROJECT_FIELDS))).then(project);
  }

  // --- sound (AudioStudio) -------------------------------------------------------------------

  function audioAnswer(row, answer) {
    return Object.assign({ version: row.audio ? row.audio.version : 0, asset_id: null }, answer);
  }

  function getAudio(id) {
    return store.get(id).then(row => row ? server('/api/guest/audio', { document: row.audio ? row.audio.document : null })
      .then(answer => audioAnswer(row, answer)) : notFound());
  }

  function putAudio(id, body) {
    return store.get(id).then(row => {
      if (!row) return notFound();
      const current = row.audio ? row.audio.version : 0;
      if (body.expected_version !== undefined && body.expected_version !== null && body.expected_version !== current) {
        return fail(tr('js.guest_api.this_game_s_sound_was_saved', 'This game\'s sound was saved in another window after you opened it.'), 409, 'audio_version_conflict',
          { code: 'audio_version_conflict', current: row.audio });
      }
      return server('/api/guest/audio', { document: body.document }).then(answer => {
        const audio = { document: answer.document, version: current + 1 };
        return store.save({ id, audio }).then(saved => audioAnswer(saved, answer));
      });
    });
  }

  function previewAudio(id, body) {
    return store.get(id).then(row => {
      if (!row) return notFound();
      const document = body && body.document ? body.document : (row.audio ? row.audio.document : null);
      return server('/api/guest/audio/preview', { document, muted: (body && body.muted) || [] });
    });
  }

  function importAudio(id, body) {
    const exported = body && body.export;
    const document = exported && exported.document ? exported.document : exported;
    return putAudio(id, { document, expected_version: body ? body.expected_version : undefined });
  }

  // --- sprites (Sprite Lab) ------------------------------------------------------------------

  const SPRITE_FIELDS = ['project_id', 'name', 'width', 'height', 'pixels', 'data_url'];

  function listSprites(query) {
    const projectId = query.get('project_id');
    return store.listSprites(projectId === null ? undefined : projectId).then(sprites => ({ sprites }));
  }

  function getSprite(id) { return store.getSprite(id).then(row => row || notFound()); }

  function saveSprite(id, body) { return store.saveSprite(Object.assign(pick(body, SPRITE_FIELDS), id ? { id } : {})); }

  function convertSprite(id) {
    return store.getSprite(id).then(sprite => sprite ? server('/api/guest/sprites/convert', { sprite })
      .then(result => Object.assign({ sprite, artifact: null }, result)) : notFound());
  }

  // --- the route table -------------------------------------------------------------------------

  const ID = '([A-Za-z0-9_-]{1,64})';
  const ROUTES = [
    ['GET', /^\/api\/projects$/, (m, q) => listProjects(q)],
    ['POST', /^\/api\/projects$/, (m, q, body) => createProject(body)],
    ['POST', /^\/api\/projects\/import$/, (m, q, body) => importProject(body)],
    ['GET', new RegExp('^/api/projects/' + ID + '$'), m => getProject(m[1])],
    ['PUT', new RegExp('^/api/projects/' + ID + '$'), (m, q, body) => putProject(m[1], body || {})],
    ['DELETE', new RegExp('^/api/projects/' + ID + '$'), m => deleteProject(m[1])],
    ['POST', new RegExp('^/api/projects/' + ID + '/duplicate$'), (m, q, body) => duplicate(m[1], body)],
    ['POST', new RegExp('^/api/projects/' + ID + '/convert$'), (m, q, body) => convert(m[1], body)],
    ['POST', new RegExp('^/api/projects/' + ID + '/convert_to$'), (m, q, body) => convertTo(m[1], body)],
    ['POST', new RegExp('^/api/projects/' + ID + '/check$'), () => Promise.resolve({ available: false, guest: true })],
    ['POST', new RegExp('^/api/projects/' + ID + '/package$'), () => needsAccount(tr('js.guest_api.making_a_cartridge_to_download', 'Making a cartridge to download'))],
    ['POST', new RegExp('^/api/projects/' + ID + '/run$'), m => runGame(m[1])],
    ['GET', new RegExp('^/api/projects/' + ID + '/revisions$'), () => Promise.resolve({ revisions: [] })],
    ['GET', new RegExp('^/api/projects/' + ID + '/audio$'), m => getAudio(m[1])],
    ['PUT', new RegExp('^/api/projects/' + ID + '/audio$'), (m, q, body) => putAudio(m[1], body || {})],
    ['POST', new RegExp('^/api/projects/' + ID + '/audio/preview$'), (m, q, body) => previewAudio(m[1], body)],
    ['POST', new RegExp('^/api/projects/' + ID + '/audio/import$'), (m, q, body) => importAudio(m[1], body)],
    ['POST', new RegExp('^/api/projects/' + ID + '/audio/samples$'), () => needsAccount(tr('js.guest_api.recording_samples', 'Recording samples'))],
    ['GET', /^\/api\/sprites$/, (m, q) => listSprites(q)],
    ['POST', /^\/api\/sprites$/, (m, q, body) => saveSprite(null, body || {})],
    ['GET', new RegExp('^/api/sprites/' + ID + '$'), m => getSprite(m[1])],
    ['PUT', new RegExp('^/api/sprites/' + ID + '$'), (m, q, body) => saveSprite(m[1], body || {})],
    ['DELETE', new RegExp('^/api/sprites/' + ID + '$'), m => store.removeSprite(m[1]).then(() => ({ deleted: true }))],
    ['POST', new RegExp('^/api/sprites/' + ID + '/convert$'), m => convertSprite(m[1])],
    ['GET', /^\/api\/artifacts$/, () => Promise.resolve({ artifacts: [] })],
    ['GET', /^\/api\/builds$/, () => Promise.resolve({ builds: [] })],
    ['GET', /^\/api\/cloud$/, () => Promise.resolve({ providers: [] })],
    ['GET', /^\/api\/examples$/, () => server('/api/examples')],
    ['GET', /^\/api\/starters\/(blocks|c|asm|python)$/, (m, q) => server('/api/starters/' + m[1] + '?title=' + encodeURIComponent(q.get('title') || ''))],
    ['POST', /^\/api\/examples\/([A-Za-z0-9_-]{1,64})\/import$/, m => importExample(m[1])],
  ];

  // Kit.api(path, options) for a guest: the answer, or an Error like the server's.
  function request(path, options) {
    const opts = options || {};
    const method = (opts.method || 'GET').toUpperCase();
    const url = new URL(path, window.location.origin);
    for (const [routeMethod, pattern, handle] of ROUTES) {
      const match = routeMethod === method && url.pathname.match(pattern);
      if (match) return Promise.resolve().then(() => handle(match, url.searchParams, opts.body));
    }
    if (/^\/api\/publish/.test(url.pathname)) return needsAccount(tr('js.guest_api.publishing', 'Publishing'));
    if (/^\/api\/classes/.test(url.pathname)) return needsAccount(tr('common.classes', 'Classes'));
    return needsAccount(tr('js.guest_api.this', 'This'));
  }

  // Downloads a page would take from the server (Kit.download): made here from this browser.
  function download(path) {
    const url = new URL(path, window.location.origin);
    const projectExport = url.pathname.match(new RegExp('^/api/projects/' + ID + '/export$'));
    const audioExport = url.pathname.match(new RegExp('^/api/projects/' + ID + '/audio/export$'));
    const id = (projectExport || audioExport || [])[1];
    if (!id) return needsAccount(tr('js.guest_api.this_download', 'This download')).catch(() => undefined);
    return store.get(id).then(row => {
      if (!row) return;
      const body = projectExport
        ? { abi: store.FORMAT, project: pick(row, PROJECT_FIELDS) }
        : { schema: 'prg32-kit-audio-export-1', document: row.audio ? row.audio.document : null, sounds: {} };
      const link = document.createElement('a');
      link.href = URL.createObjectURL(new Blob([JSON.stringify(body, null, 1)], { type: 'application/json' }));
      link.download = (row.title || 'game').replace(/[^A-Za-z0-9_-]+/g, '-') + (projectExport ? '.blocks.json' : '.prg32audio.json');
      link.click();
      setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    });
  }

  return { request, download };
})();
