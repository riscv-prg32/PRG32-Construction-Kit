(function () {
  const projectId = $('#projectId').val();
  let project = null;
  let simulator = null;
  let dirty = false;

  function setLog(text) {
    $('#debugLog').text(text);
  }

  function refreshSimulator() {
    const blocks = PRG32Blocks.save();
    const ir = simulator.loadBlocks(blocks);
    $('#generatedIR').text(JSON.stringify(ir, null, 2));
  }

  function loadProject() {
    return Kit.api('/api/projects/' + projectId).then(data => {
      project = data;
      $('#projectTitle').text(project.title);
      $('#projectSummary').text(project.description || 'No summary yet.');
      PRG32Blocks.load(project.blocks_json || {});
      refreshSimulator();
      setLog('Loaded project ' + project.id);
    });
  }

  function saveProject() {
    const blocks = PRG32Blocks.save();
    const ir = PRG32Simulator.compileBlocks(blocks);
    return Kit.api('/api/projects/' + projectId, { method: 'PUT', body: { blocks_json: blocks, game_json: ir } })
      .then(data => {
        project = data;
        dirty = false;
        Kit.toast('Project saved', 'success');
        refreshSimulator();
      });
  }

  function convertProject() {
    $('#convertProject').prop('disabled', true);
    return saveProject()
      .then(() => Kit.api('/api/projects/' + projectId + '/convert', { method: 'POST', body: {} }))
      .then(result => {
        $('#generatedC').text(result.c_source);
        $('#generatedIR').text(JSON.stringify(result.game_ir, null, 2));
        setLog('Generated C artifact: ' + result.artifact.id + '\nWarnings: ' + (result.game_ir.warnings || []).join(', '));
        Kit.toast('Generated C artifact', 'success');
      })
      .catch(err => Kit.toast(err.message, 'danger'))
      .finally(() => $('#convertProject').prop('disabled', false));
  }

  function packageProject() {
    $('#packageProject').prop('disabled', true);
    return saveProject()
      .then(() => Kit.api('/api/projects/' + projectId + '/package', { method: 'POST', body: {} }))
      .then(result => {
        $('#generatedC').text(result.c_artifact.text_content || $('#generatedC').text());
        $('#generatedIR').text(JSON.stringify(result.result.manifest, null, 2));
        setLog(result.build.log || JSON.stringify(result.result, null, 2));
        const kind = result.result.publishable ? 'success' : 'warning';
        Kit.toast(result.result.publishable ? 'Store bundle prepared' : 'Source bundle prepared; PRG32 toolchain required for .prg32 files', kind);
      })
      .catch(err => Kit.toast(err.message, 'danger'))
      .finally(() => $('#packageProject').prop('disabled', false));
  }

  PRG32Blocks.init('blocklyDiv');
  simulator = new PRG32Simulator.Simulator(document.getElementById('gameCanvas'), document.getElementById('debugState'));
  PRG32Blocks.getWorkspace().addChangeListener(event => {
    if (event.type !== Blockly.Events.UI) {
      dirty = true;
      refreshSimulator();
    }
  });

  $('#saveProject').on('click', () => saveProject().catch(err => Kit.toast(err.message, 'danger')));
  $('#convertProject').on('click', convertProject);
  $('#packageProject').on('click', packageProject);
  $('#runGame').on('click', function () {
    const running = simulator.toggle();
    $(this).toggleClass('btn-danger', running).toggleClass('btn-success', !running).html(running ? '<i class="bi bi-pause-fill"></i> Pause' : '<i class="bi bi-play-fill"></i> Play');
  });
  $('#stepGame').on('click', () => simulator.step());
  $('#resetGame').on('click', () => simulator.reset());
  $('#exportProject').on('click', () => { window.location.href = '/api/projects/' + projectId + '/export'; });

  window.addEventListener('beforeunload', event => {
    if (dirty) {
      event.preventDefault();
      event.returnValue = '';
    }
  });

  loadProject().catch(err => Kit.toast(err.message, 'danger'));
})();
