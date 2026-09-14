(function () {
  const projectId = $('#projectId').val();
  let project = null;
  let simulator = null;
  let dirty = false;

  function isCMode() { return $('#editorMode').val() === 'c'; }

  function showMode() {
    $('#blocksEditor').toggleClass('d-none', isCMode());
    $('#sourceEditor').toggleClass('d-none', !isCMode());
    $('#runGame, #stepGame, #resetGame').prop('disabled', isCMode());
    if (isCMode()) {
      simulator.stop();
      $('#runGame').removeClass('btn-danger').addClass('btn-success').html('<i class="bi bi-play-fill"></i> Play');
      $('#debugState').text('Advanced C is compiled by PRG32; this browser simulator runs Blocks only.');
    } else {
      refreshSimulator();
      Blockly.svgResize(PRG32Blocks.getWorkspace());
    }
  }

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
      $('#editorMode').val(project.game_json && project.game_json.source_mode === 'c' ? 'c' : 'blocks');
      $('#customC').val(project.game_json && project.game_json.source_c || '');
      $('#requiredFeatures').val(project.game_json && (project.game_json.required_features || []).join(', ') || '');
      showMode();
      setLog('Loaded project ' + project.id);
    });
  }

  function saveProject() {
    const blocks = PRG32Blocks.save();
    const features = $('#requiredFeatures').val().split(',').map(item => item.trim()).filter(Boolean);
    const ir = isCMode() ? { source_mode: 'c', source_c: $('#customC').val(), required_features: features } : PRG32Simulator.compileBlocks(blocks);
    return Kit.api('/api/projects/' + projectId, { method: 'PUT', body: { blocks_json: blocks, game_json: ir } })
      .then(data => {
        project = data;
        dirty = false;
        Kit.toast('Project saved', 'success');
        if (!isCMode()) refreshSimulator();
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
        const cartridges = result.cartridge_artifacts || [];
        if (cartridges.length) {
          const links = cartridges.map(artifact => `<a class="btn btn-success btn-sm ms-2" href="/api/artifacts/${encodeURIComponent(artifact.id)}/download"><i class="bi bi-download"></i> ${Kit.escape(artifact.metadata.architecture)} .prg32</a>`).join('');
          $('#cartridgeDownloads').removeClass('d-none alert-warning').addClass('alert-success').html(`<strong>Cartridge ready.</strong> Download it and upload it to a PRG32 cartridge slot.${links}`);
        } else {
          $('#cartridgeDownloads').removeClass('d-none alert-success').addClass('alert-warning').text('The source bundle is ready, but the PRG32 compiler toolchain is not installed on this server.');
        }
        Kit.toast(cartridges.length ? 'PRG32 cartridge compiled' : 'Source bundle prepared; PRG32 toolchain required for the binary', cartridges.length ? 'success' : 'warning');
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
  $('#editorMode').on('change', () => { dirty = true; showMode(); });
  $('#customC').on('input', () => { dirty = true; });
  $('#requiredFeatures').on('input', () => { dirty = true; });
  $('#startFromBlocks').on('click', () => {
    const blocks = PRG32Blocks.save();
    Kit.api('/api/projects/' + projectId, { method: 'PUT', body: { blocks_json: blocks, game_json: PRG32Simulator.compileBlocks(blocks) } })
      .then(() => Kit.api('/api/projects/' + projectId + '/convert', { method: 'POST', body: {} }))
      .then(result => { $('#customC').val(result.c_source); dirty = true; Kit.toast('Generated C copied. Save to keep your changes.', 'success'); })
      .catch(err => Kit.toast(err.message, 'danger'));
  });
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
