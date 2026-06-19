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
            <a class="btn btn-primary btn-sm" href="/projects/${project.id}"><i class="bi bi-pencil-square"></i> Open</a>
            <button class="btn btn-outline-danger btn-sm delete-project" data-id="${project.id}"><i class="bi bi-trash"></i></button>
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
  }

  $('#newProjectForm').on('submit', function (event) {
    event.preventDefault();
    const form = new FormData(this);
    const tags = String(form.get('tags') || '').split(',').map(t => t.trim()).filter(Boolean);
    Kit.api('/api/projects', { method: 'POST', body: { title: form.get('title'), author: form.get('author'), description: form.get('description'), tags, blocks_json: starterBlocks(), game_json: {} } })
      .then(project => { Kit.toast('Project created', 'success'); window.location.href = '/projects/' + project.id; })
      .catch(err => Kit.toast(err.message, 'danger'));
  });

  $('#projectGrid').on('click', '.delete-project', function () {
    const id = $(this).data('id');
    if (!confirm('Delete this project and its dependent resources?')) return;
    Kit.api('/api/projects/' + id, { method: 'DELETE' }).then(load).catch(err => Kit.toast(err.message, 'danger'));
  });

  $('#importProjectFile').on('change', function () {
    const file = this.files[0];
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    Kit.api('/api/projects/import', { method: 'POST', body: form })
      .then(project => { Kit.toast('Project imported', 'success'); window.location.href = '/projects/' + project.id; })
      .catch(err => Kit.toast(err.message, 'danger'));
  });

  $('#refreshProjects').on('click', load);
  load();
})();
