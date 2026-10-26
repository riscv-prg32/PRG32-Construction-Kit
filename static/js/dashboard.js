(function () {
  const starterBlocks = () => ({
    blocks: {
      languageVersion: 0,
      blocks: [
        { type: 'prg32_on_start', id: 'start', x: 20, y: 20, inputs: { DO: { block: { type: 'prg32_set_state', id: 'setx', fields: { VAR: 'player_x', VALUE: '150' }, next: { block: { type: 'prg32_set_state', id: 'sety', fields: { VAR: 'player_y', VALUE: '180' } } } } } } },
        { type: 'prg32_update', id: 'update', x: 320, y: 20, inputs: { DO: { block: { type: 'prg32_if_button', id: 'left', fields: { BUTTON: 'LEFT' }, inputs: { DO: { block: { type: 'prg32_change_state', id: 'mlx', fields: { VAR: 'player_x', DELTA: '-3' } } } }, next: { block: { type: 'prg32_if_button', id: 'right', fields: { BUTTON: 'RIGHT' }, inputs: { DO: { block: { type: 'prg32_change_state', id: 'mrx', fields: { VAR: 'player_x', DELTA: '3' } } } } } } } } } },
        { type: 'prg32_draw', id: 'draw', x: 620, y: 20, inputs: { DO: { block: { type: 'prg32_clear_screen', id: 'clear', fields: { COLOR: 'BLACK' }, next: { block: { type: 'prg32_draw_rect', id: 'rect', fields: { X: 'player_x', Y: 'player_y', W: '16', H: '16', COLOR: 'YELLOW' } } } } } } }
      ]
    }
  });

  // Blocks, C, assembly or Python: fixed when the project is made (ADR-0024, ADR-0026).
  const TYPE_NAMES = { blocks: tr('common.blocks', 'Blocks'), c: 'C', asm: tr('js.dashboard.assembly', 'Assembly'), python: tr('js.dashboard.python', 'Python') };
  function projectType(project) {
    const mode = project.game_json && project.game_json.source_mode;
    return mode === 'c' || mode === 'asm' || mode === 'python' ? mode : 'blocks';
  }

  // Open, Sprite Lab, AudioStudio and Player work on this project, like the top menu once it is open.
  // The two tools' names are names, the same in every language.
  const TOOL_NAMES = { sprites: 'Sprite Lab', sound: 'AudioStudio' };
  function card(project) {
    const ide = '/ide/' + encodeURIComponent(project.id);
    return `<div class="col-md-6 col-xl-4">
      <div class="card project-card h-100">
        <div class="project-icon"></div>
        <div class="card-body">
          <h3 class="h5">${Kit.escape(project.title)}
            <span class="badge rounded-pill text-bg-secondary align-middle fs-6 fw-normal">${TYPE_NAMES[projectType(project)]}</span></h3>
          <p class="text-muted small mb-2">${Kit.escape(project.description || tr('js.dashboard.no_summary_yet', 'No summary yet.'))}</p>
          <div class="mb-3">${Kit.tags(project.tags)}</div>
          <div class="d-flex flex-wrap gap-2">
            <a class="btn btn-primary btn-sm" href="${ide}"><i class="bi bi-pencil-square"></i> ${tr('js.dashboard.open', 'Open')}</a>
            <a class="btn btn-outline-primary btn-sm" href="${ide}#sprites"><i class="bi bi-brush" aria-hidden="true"></i> ${TOOL_NAMES.sprites}</a>
            <a class="btn btn-outline-primary btn-sm" href="${ide}#sound"><i class="bi bi-music-note-beamed" aria-hidden="true"></i> ${TOOL_NAMES.sound}</a>
            <a class="btn btn-outline-success btn-sm" href="/player?project=${encodeURIComponent(project.id)}" title="${Kit.escape(tr('js.dashboard.play_the_compiled_cartridge', 'Play the compiled cartridge'))}"><i class="bi bi-cpu" aria-hidden="true"></i> ${tr('base.player', 'Player')}</a>
            <button class="btn btn-outline-secondary btn-sm cloud-project cloud-only" data-id="${Kit.escape(project.id)}" data-title="${Kit.escape(project.title)}" aria-label="${Kit.escape(tr('js.dashboard.cloud_copy_of', 'Cloud copy of {title}', { title: project.title }))}"><i class="bi bi-cloud"></i></button>
            <button class="btn btn-outline-danger btn-sm delete-project" data-id="${Kit.escape(project.id)}" aria-label="${Kit.escape(tr('js.dashboard.delete_title', 'Delete {title}', { title: project.title }))}"><i class="bi bi-trash" aria-hidden="true"></i></button>
          </div>
        </div>
        <div class="card-footer small text-muted">${Kit.escape(tr('js.dashboard.updated_when', 'Updated {when}', { when: Kit.when(project.updated_at) }))}</div>
      </div>
    </div>`;
  }

  function load() {
    Promise.all([
      Kit.api('/api/projects'), Kit.api('/api/sprites'), Kit.api('/api/artifacts'), Kit.api('/api/builds')
    ]).then(([projects, sprites, artifacts, builds]) => {
      $('#projectCount').text(projects.projects.length);
      $('#spriteCount').text(sprites.sprites.length);
      $('#artifactCount').text(artifacts.artifacts.length);
      $('#buildCount').text(builds.builds.length);
      $('#projectGrid').html(projects.projects.map(card).join('') || `<div class="col"><div class="alert alert-info">${tr('js.dashboard.create_your_first_project', 'Create your first project.')}</div></div>`);
    }).catch(err => Kit.toast(err.message, 'danger'));
    loadDeleted();
  }

  // "Recently deleted": a deleted project can be restored; only an admin can delete it for good.
  const isAdmin = $('#deletedSection').data('admin') === true;
  function deletedRow(project) {
    const purge = isAdmin ? `<button class="btn btn-outline-danger btn-sm purge-project" data-id="${Kit.escape(project.id)}">${tr('js.dashboard.delete_for_good', 'Delete for good')}</button>` : '';
    return `<div class="list-group-item d-flex gap-2 align-items-center justify-content-between">
      <div><strong>${Kit.escape(project.title)}</strong><div class="small text-muted">${Kit.escape(tr('js.dashboard.deleted_when', 'Deleted {when}', { when: Kit.when(project.deleted_at) }))}</div></div>
      <div class="text-nowrap"><button class="btn btn-outline-primary btn-sm restore-project" data-id="${Kit.escape(project.id)}"><i class="bi bi-arrow-counterclockwise"></i> ${tr('js.ide.restore', 'Restore')}</button> ${purge}</div>
    </div>`;
  }
  function loadDeleted() {
    Kit.api('/api/projects?deleted=1').then(data => {
      $('#deletedList').html(data.projects.map(deletedRow).join('') || `<div class="list-group-item small text-muted">${tr('js.dashboard.nothing_here', 'Nothing here.')}</div>`);
    }).catch(err => Kit.toast(err.message, 'danger'));
  }
  $('#deletedList').on('click', '.restore-project', function () {
    Kit.api('/api/projects/' + encodeURIComponent($(this).data('id')) + '/restore', { method: 'POST', body: {} })
      .then(() => { Kit.toast(tr('js.dashboard.project_restored', 'Project restored'), 'success'); load(); })
      .catch(err => Kit.toast(err.message, 'danger'));
  });
  $('#deletedList').on('click', '.purge-project', function () {
    if (!confirm(tr('js.dashboard.delete_this_project_for_good_its', 'Delete this project for good? Its history goes too. This cannot be undone.'))) return;
    Kit.api('/api/projects/' + encodeURIComponent($(this).data('id')) + '?purge=1', { method: 'DELETE' })
      .then(load).catch(err => Kit.toast(err.message, 'danger'));
  });

  function loadExamples() {
    Kit.api('/api/examples').then(data => {
      const badge = example => example.kind === 'game'
        ? `<span class="badge text-bg-success ms-2">${tr('js.dashboard.complete_game', 'complete game')}</span>`
        : example.kind === 'python' ? '<span class="badge text-bg-info ms-2">Python</span>'
          : `<span class="badge text-bg-secondary ms-2">${tr('js.dashboard.sketch', 'sketch')}</span>`;
      $('#exampleList').html(data.examples.map(example => `<div class="list-group-item d-flex gap-3 align-items-center justify-content-between"><div><strong>${Kit.escape(example.title)}</strong>${badge(example)}<div class="small text-muted">${Kit.escape(example.description)}</div></div><button class="btn btn-primary btn-sm import-example" data-slug="${Kit.escape(example.slug)}">${tr('js.dashboard.add', 'Add')}</button></div>`).join(''));
    }).catch(err => $('#exampleList').html(`<div class="alert alert-danger">${Kit.escape(err.message)}</div>`));
  }

  // New Project: Blocks, C or assembly. The summary and tags follow the choice until the
  // student changes them; C and assembly start from the kit's starter game (/api/starters).
  const KIND_DEFAULTS = {
    blocks: { description: 'A block-built PRG32 cartridge.', tags: 'blocks,classroom' },
    c: { description: 'A PRG32 cartridge written in C.', tags: 'c,classroom' },
    asm: { description: 'A PRG32 cartridge written in RISC-V assembly.', tags: 'assembly,classroom' },
    python: { description: 'A PRG32 cartridge written in PRG32 Python.', tags: 'python,classroom' },
  };
  let kindShown = 'blocks';
  $('#newProjectKinds').on('change', 'input[name=kind]', function () {
    const before = KIND_DEFAULTS[kindShown];
    const after = KIND_DEFAULTS[this.value];
    const summary = $('#newProjectSummary');
    const tags = $('#newProjectTags');
    if (summary.val() === before.description) summary.val(after.description);
    if (tags.val() === before.tags) tags.val(after.tags);
    kindShown = this.value;
  });

  $('#newProjectForm').on('submit', function (event) {
    event.preventDefault();
    const form = new FormData(this);
    const kind = form.get('kind') || 'blocks';
    const title = form.get('title');
    const tags = String(form.get('tags') || '').split(',').map(t => t.trim()).filter(Boolean);
    const starter = kind === 'blocks' ? Promise.resolve({ blocks_json: starterBlocks(), game_json: {} })
      : Kit.api('/api/starters/' + encodeURIComponent(kind) + '?title=' + encodeURIComponent(title));
    starter.then(start => Kit.api('/api/projects', { method: 'POST', body: { title, author: form.get('author'),
      description: form.get('description'), tags, blocks_json: start.blocks_json, game_json: start.game_json } }))
      // C and assembly are written in the IDE (Monaco); Blocks open in the editor as before.
      .then(project => { Kit.toast(tr('js.dashboard.project_created', 'Project created'), 'success');
        window.location.href = '/ide/' + encodeURIComponent(project.id); })
      .catch(err => Kit.toast(err.message, 'danger'));
  });

  $('#projectGrid').on('click', '.delete-project', function () {
    const id = $(this).data('id');
    if (!confirm(tr('js.dashboard.move_this_project_to_recently_deleted', 'Move this project to Recently deleted? You can restore it from there.'))) return;
    Kit.api('/api/projects/' + encodeURIComponent(id), { method: 'DELETE' }).then(load).catch(err => Kit.toast(err.message, 'danger'));
  });

  $('#exampleList').on('click', '.import-example', function () {
    const button = $(this);
    button.prop('disabled', true);
    Kit.api('/api/examples/' + encodeURIComponent(button.data('slug')) + '/import', { method: 'POST', body: {} })
      .then(project => { window.location.href = '/ide/' + encodeURIComponent(project.id); })
      .catch(err => { button.prop('disabled', false); Kit.toast(err.message, 'danger'); });
  });

  $('#importProjectFile').on('change', function () {
    const file = this.files[0];
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    Kit.api('/api/projects/import', { method: 'POST', body: form })
      .then(project => {
        const ignored = project.ignored_files || [];
        Kit.toast(ignored.length ? tr('js.dashboard.project_imported_skipped_files_it_does', 'Project imported. Skipped files it does not use: {join}', { join: ignored.join(', ') }) : tr('js.dashboard.project_imported', 'Project imported'), 'success');
        // Leave time to read the list of skipped files before the editor opens.
        setTimeout(() => { window.location.href = '/ide/' + encodeURIComponent(project.id); }, ignored.length ? 3000 : 0);
      })
      .catch(err => Kit.toast(err.message, 'danger'));
  });

  // Games made in this browser without an account (ADR-0017): offer to move them in.
  // Each one is created on the server first and removed from the browser only after that.
  function checkGuestProjects() {
    // A guest's projects are the ones on this page already: nothing to move yet.
    if (!window.PRG32GuestStore || Kit.guest) return Promise.resolve();
    return PRG32GuestStore.list().then(rows => {
      const games = rows.filter(row => (row.blocks_json && Object.keys(row.blocks_json).length)
        || (row.game_json && Object.keys(row.game_json).length) || row.audio);
      $('#guestProjectsBanner').prop('hidden', !games.length);
      $('#guestProjectsCount').text(games.length === 1 ? '1 game' : games.length + ' games');
    }).catch(() => { /* this browser cannot keep guest games: nothing to move */ });
  }

  // One guest game into the account: the project, then its sound, then its sprites.
  function moveOne(row, sprites) {
    return Kit.api('/api/projects', { method: 'POST', body: { title: row.title, description: row.description,
      author: row.author, tags: row.tags, blocks_json: row.blocks_json, game_json: row.game_json } })
      .then(created => (row.audio && row.audio.document
        ? Kit.api('/api/projects/' + encodeURIComponent(created.id) + '/audio', { method: 'PUT',
          body: { document: row.audio.document, expected_version: 0 } })
        : Promise.resolve())
        .then(() => Promise.all(sprites.map(sprite => moveSprite(Object.assign({}, sprite, { project_id: created.id })))))
        .then(() => Promise.all((row.backgrounds || []).map(item => Kit.api('/api/assets', { method: 'POST', body: {
          project_id: created.id, kind: 'background', name: item.name, content_type: 'application/json', data: item.data } }))))
        .then(() => created));
  }

  function moveSprite(sprite) {
    return Kit.api('/api/sprites', { method: 'POST', body: { project_id: sprite.project_id, name: sprite.name,
      width: sprite.width, height: sprite.height, pixels: sprite.pixels, data_url: sprite.data_url, palette: sprite.palette || {} } });
  }

  $('#moveGuestProjects').on('click', function () {
    $(this).prop('disabled', true);
    PRG32GuestStore.moveToAccount(moveOne)
      .then(result => PRG32GuestStore.moveSpritesToAccount(moveSprite).then(() => result, error => Object.assign(result, { error })))
      .then(result => {
        if (result.error) Kit.toast(tr('js.dashboard.moved_some_left', 'Moved {moved}; {left} stay in this browser: {error}', { moved: result.moved.length, left: result.left, error: result.error.message }), 'warning');
        else Kit.toast(tr('js.dashboard.moved_into_account', 'Moved {count} into your account', { count: result.moved.length }), 'success');
        return Promise.all([load(), checkGuestProjects()]);
      })
      .finally(() => $(this).prop('disabled', false));
  });

  $('#refreshProjects').on('click', load);
  $('#examplesModal').on('show.bs.modal', loadExamples);
  load();
  checkGuestProjects();
})();
