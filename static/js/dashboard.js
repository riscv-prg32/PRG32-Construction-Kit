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

  function card(project) {
    return `<div class="col-md-6 col-xl-4">
      <div class="card project-card h-100">
        <div class="project-icon"></div>
        <div class="card-body">
          <h3 class="h5">${Kit.escape(project.title)}</h3>
          <p class="text-muted small mb-2">${Kit.escape(project.description || 'No summary yet.')}</p>
          <div class="mb-3">${Kit.tags(project.tags)}</div>
          <div class="d-flex gap-2">
            <a class="btn btn-primary btn-sm" href="/projects/${encodeURIComponent(project.id)}"><i class="bi bi-pencil-square"></i> Open</a>
            <button class="btn btn-outline-danger btn-sm delete-project" data-id="${Kit.escape(project.id)}"><i class="bi bi-trash"></i></button>
          </div>
        </div>
        <div class="card-footer small text-muted">Updated ${Kit.escape(project.updated_at)}</div>
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
      $('#projectGrid').html(projects.projects.map(card).join('') || '<div class="col"><div class="alert alert-info">Create your first project.</div></div>');
    }).catch(err => Kit.toast(err.message, 'danger'));
    loadDeleted();
  }

  // "Recently deleted": a deleted project can be restored; only an admin can delete it for good.
  const isAdmin = $('#deletedSection').data('admin') === true;
  function deletedRow(project) {
    const purge = isAdmin ? `<button class="btn btn-outline-danger btn-sm purge-project" data-id="${Kit.escape(project.id)}">Delete for good</button>` : '';
    return `<div class="list-group-item d-flex gap-2 align-items-center justify-content-between">
      <div><strong>${Kit.escape(project.title)}</strong><div class="small text-muted">Deleted ${Kit.escape(project.deleted_at)}</div></div>
      <div class="text-nowrap"><button class="btn btn-outline-primary btn-sm restore-project" data-id="${Kit.escape(project.id)}"><i class="bi bi-arrow-counterclockwise"></i> Restore</button> ${purge}</div>
    </div>`;
  }
  function loadDeleted() {
    Kit.api('/api/projects?deleted=1').then(data => {
      $('#deletedList').html(data.projects.map(deletedRow).join('') || '<div class="list-group-item small text-muted">Nothing here.</div>');
    }).catch(err => Kit.toast(err.message, 'danger'));
  }
  $('#deletedList').on('click', '.restore-project', function () {
    Kit.api('/api/projects/' + encodeURIComponent($(this).data('id')) + '/restore', { method: 'POST', body: {} })
      .then(() => { Kit.toast('Project restored', 'success'); load(); })
      .catch(err => Kit.toast(err.message, 'danger'));
  });
  $('#deletedList').on('click', '.purge-project', function () {
    if (!confirm('Delete this project for good? Its history goes too. This cannot be undone.')) return;
    Kit.api('/api/projects/' + encodeURIComponent($(this).data('id')) + '?purge=1', { method: 'DELETE' })
      .then(load).catch(err => Kit.toast(err.message, 'danger'));
  });

  function loadExamples() {
    Kit.api('/api/examples').then(data => {
      const badge = example => example.kind === 'game'
        ? '<span class="badge text-bg-success ms-2">complete game</span>'
        : '<span class="badge text-bg-secondary ms-2">sketch</span>';
      $('#exampleList').html(data.examples.map(example => `<div class="list-group-item d-flex gap-3 align-items-center justify-content-between"><div><strong>${Kit.escape(example.title)}</strong>${badge(example)}<div class="small text-muted">${Kit.escape(example.description)}</div></div><button class="btn btn-primary btn-sm import-example" data-slug="${Kit.escape(example.slug)}">Add</button></div>`).join(''));
    }).catch(err => $('#exampleList').html(`<div class="alert alert-danger">${Kit.escape(err.message)}</div>`));
  }

  $('#newProjectForm').on('submit', function (event) {
    event.preventDefault();
    const form = new FormData(this);
    const tags = String(form.get('tags') || '').split(',').map(t => t.trim()).filter(Boolean);
    Kit.api('/api/projects', { method: 'POST', body: { title: form.get('title'), author: form.get('author'), description: form.get('description'), tags, blocks_json: starterBlocks(), game_json: {} } })
      .then(project => { Kit.toast('Project created', 'success'); window.location.href = '/projects/' + encodeURIComponent(project.id); })
      .catch(err => Kit.toast(err.message, 'danger'));
  });

  $('#projectGrid').on('click', '.delete-project', function () {
    const id = $(this).data('id');
    if (!confirm('Move this project to Recently deleted? You can restore it from there.')) return;
    Kit.api('/api/projects/' + encodeURIComponent(id), { method: 'DELETE' }).then(load).catch(err => Kit.toast(err.message, 'danger'));
  });

  $('#exampleList').on('click', '.import-example', function () {
    const button = $(this);
    button.prop('disabled', true);
    Kit.api('/api/examples/' + encodeURIComponent(button.data('slug')) + '/import', { method: 'POST', body: {} })
      .then(project => { window.location.href = '/projects/' + project.id; })
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
        Kit.toast(ignored.length ? 'Project imported. Skipped files it does not use: ' + ignored.join(', ') : 'Project imported', 'success');
        // Leave time to read the list of skipped files before the editor opens.
        setTimeout(() => { window.location.href = '/projects/' + project.id; }, ignored.length ? 3000 : 0);
      })
      .catch(err => Kit.toast(err.message, 'danger'));
  });

  $('#refreshProjects').on('click', load);
  $('#examplesModal').on('show.bs.modal', loadExamples);
  load();
})();
