(function () {
  const projectId = encodeURIComponent($('#projectId').val());
  let project = null;
  let simulator = null;
  let dirty = false;
  let loading = false;

  function isCMode() { return $('#editorMode').val() === 'c'; }

  // Which generated source Generate and Compile make: C, RISC-V assembly, or both.
  // Assembly is made from Blocks, so an Advanced C project always uses its own C.
  const CONVERT_LABELS = { c: 'Generate C', asm: 'Generate Assembly', both: 'Generate C + Assembly' };
  const languageKey = 'prg32-source-language-' + projectId;
  function sourceLanguage() { return isCMode() ? 'c' : ($('#sourceLanguage').val() || 'c'); }
  function codeChoice() { return { source_language: sourceLanguage() }; }
  function showLanguage() {
    $('#sourceLanguage').prop('disabled', isCMode());
    $('#convertLabel').text(CONVERT_LABELS[sourceLanguage()]);
  }
  function rememberLanguage() {
    try { localStorage.setItem(languageKey, $('#sourceLanguage').val()); } catch (err) { /* private window */ }
  }
  function restoreLanguage() {
    let saved = null;
    try { saved = localStorage.getItem(languageKey); } catch (err) { /* private window */ }
    if (CONVERT_LABELS[saved]) $('#sourceLanguage').val(saved);
  }

  // Put generated sources in their tabs and show the first one that arrived.
  function showSources(cSource, asmSource) {
    if (typeof cSource === 'string') $('#generatedC').text(cSource);
    if (typeof asmSource === 'string') $('#generatedAsm').text(asmSource);
    const target = typeof cSource === 'string' ? '#cPanel' : typeof asmSource === 'string' ? '#asmPanel' : null;
    if (target) bootstrap.Tab.getOrCreateInstance(document.querySelector(`[data-bs-target="${target}"]`)).show();
  }

  function showMode() {
    $('#blocksEditor').toggleClass('d-none', isCMode());
    $('#sourceEditor').toggleClass('d-none', !isCMode());
    $('#runGame, #stepGame, #resetGame').prop('disabled', isCMode());
    showLanguage();
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
      // Blockly reports the load as change events a moment later; those are not student edits.
      loading = true;
      PRG32Blocks.load(project.blocks_json || {});
      setTimeout(() => { loading = false; dirty = false; }, 0);
      $('#editorMode').val(project.game_json && project.game_json.source_mode === 'c' ? 'c' : 'blocks');
      $('#customC').val(project.game_json && project.game_json.source_c || '');
      const features = project.game_json && project.game_json.required_features;
      $('#requiredFeatures').val(Array.isArray(features) ? features.join(', ') : '');
      showMode();
      showSharedNotice();
      setLog('Loaded project ' + project.id);
    });
  }

  // Shared classroom projects (like the starter games) are read-only for students:
  // offer a personal copy, which they can then change, run and build.
  function showSharedNotice() {
    if (project.can_edit !== false) return;
    $('#sharedNotice').remove();
    $('#projectTitle').closest('div').append(`<div id="sharedNotice" class="alert alert-info py-2 mt-2 mb-0 small">
      This is a shared classroom project, so you cannot change it. <button class="btn btn-primary btn-sm ms-2" id="copyProject">Make my copy</button></div>`);
  }

  $(document).on('click', '#copyProject', () => {
    const copy = { title: project.title + ' (my copy)', description: project.description, author: project.author,
                   tags: project.tags, blocks_json: PRG32Blocks.save(), game_json: project.game_json };
    Kit.api('/api/projects', { method: 'POST', body: copy })
      .then(created => { window.location.href = '/projects/' + encodeURIComponent(created.id); })
      .catch(err => Kit.toast(err.message, 'danger'));
  });

  // Tell the server exactly what this window saved, so a build notices if
  // another browser window saved a different version in the meantime.
  function savedVersion() {
    if (isCMode()) return { expected_source_c: project.game_json.source_c };
    return { expected_blocks_json: project.blocks_json };
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
      .then(() => Kit.api('/api/projects/' + projectId + '/convert', { method: 'POST', body: codeChoice() }))
      .then(result => {
        showSources(result.c_source, result.asm_source);
        $('#generatedIR').text(JSON.stringify(result.game_ir, null, 2));
        const names = (result.artifacts || [result.artifact]).map(artifact => artifact.name + ' (' + artifact.id + ')');
        setLog('Generated artifacts: ' + names.join(', ') + '\nWarnings: ' + (result.game_ir.warnings || []).join(', '));
        Kit.toast(CONVERT_LABELS[result.source_language || 'c'].replace('Generate', 'Generated'), 'success');
      })
      .catch(err => Kit.toast(err.message, 'danger'))
      .finally(() => $('#convertProject').prop('disabled', false));
  }

  function packageProject() {
    $('#packageProject').prop('disabled', true);
    return saveProject()
      .then(() => Kit.api('/api/projects/' + projectId + '/package', { method: 'POST', body: Object.assign(codeChoice(), savedVersion()) }))
      .then(result => {
        showSources(result.c_artifact && result.c_artifact.text_content, result.asm_artifact && result.asm_artifact.text_content);
        $('#generatedIR').text(JSON.stringify(result.result.manifest, null, 2));
        setLog(result.build.log || JSON.stringify(result.result, null, 2));
        const cartridges = result.cartridge_artifacts || [];
        if (cartridges.length) {
          const links = cartridges.map(artifact => `<a class="btn btn-success btn-sm ms-2" href="/api/artifacts/${encodeURIComponent(artifact.id)}/download"><i class="bi bi-download"></i> ${Kit.escape(artifact.metadata.architecture)} .prg32</a>`).join('');
          $('#cartridgeDownloads').removeClass('d-none alert-warning').addClass('alert-success').html(`<strong>Cartridge ready.</strong> Download it and upload it to a PRG32 cartridge slot.${links}`);
        } else {
          $('#cartridgeDownloads').removeClass('d-none alert-success').addClass('alert-warning').text('The source bundle is ready, but this server cannot compile PRG32 cartridges yet. Ask your teacher to start the kit with its Docker image (see docs/install_cartridge_build.md).');
        }
        Kit.toast(cartridges.length ? 'PRG32 cartridge compiled' : 'Source bundle prepared; PRG32 toolchain required for the binary', cartridges.length ? 'success' : 'warning');
      })
      .catch(err => Kit.toast(err.message, 'danger'))
      .finally(() => $('#packageProject').prop('disabled', false));
  }

  // Compile only the chosen target and hand the .prg32 file straight to the browser.
  function downloadCartridge(architecture) {
    const buttons = $('.download-cartridge, .download-cartridge-toggle');
    buttons.prop('disabled', true);
    return saveProject()
      .then(() => Kit.api('/api/projects/' + projectId + '/package', { method: 'POST', body: Object.assign({ architectures: [architecture] }, codeChoice(), savedVersion()) }))
      .then(result => {
        setLog(result.build.log || JSON.stringify(result.result, null, 2));
        const cartridge = (result.cartridge_artifacts || []).find(artifact => artifact.metadata.architecture === architecture);
        if (!cartridge) {
          $('#cartridgeDownloads').removeClass('d-none alert-success').addClass('alert-warning').text('No .prg32 cartridge was produced. Check the Debug Log: if it says a command or the compiler was not found, ask your teacher to start the kit with its Docker image (see docs/install_cartridge_build.md).');
          Kit.toast('Cartridge build failed; see the Debug Log', 'warning');
          return;
        }
        const link = document.createElement('a');
        link.href = '/api/artifacts/' + encodeURIComponent(cartridge.id) + '/download';
        link.download = cartridge.name;
        document.body.appendChild(link);
        link.click();
        link.remove();
        $('#cartridgeDownloads').removeClass('d-none alert-warning').addClass('alert-success').html(`<strong>Cartridge downloaded.</strong> Upload it to a PRG32 cartridge slot. <a href="${link.href}">Download ${Kit.escape(cartridge.name)} again</a>`);
        Kit.toast('Downloading ' + cartridge.name, 'success');
      })
      .catch(err => Kit.toast(err.message, 'danger'))
      .finally(() => buttons.prop('disabled', false));
  }

  PRG32Blocks.init('blocklyDiv');
  simulator = new PRG32Simulator.Simulator(document.getElementById('gameCanvas'), document.getElementById('debugState'));
  PRG32Blocks.getWorkspace().addChangeListener(event => {
    if (event.type !== Blockly.Events.UI && !event.isUiEvent) {
      if (!loading) dirty = true;
      refreshSimulator();
    }
  });

  $('#saveProject').on('click', () => saveProject().catch(err => Kit.toast(err.message, 'danger')));
  $('#editorMode').on('change', () => { dirty = true; showMode(); });
  $('#sourceLanguage').on('change', () => { rememberLanguage(); showLanguage(); });
  restoreLanguage();
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
  $('.download-cartridge').on('click', function () { downloadCartridge($(this).data('architecture')); });
  $('#runGame').on('click', function () {
    const running = simulator.toggle();
    $(this).toggleClass('btn-danger', running).toggleClass('btn-success', !running).html(running ? '<i class="bi bi-pause-fill"></i> Pause' : '<i class="bi bi-play-fill"></i> Play');
  });
  $('#stepGame').on('click', () => simulator.step());
  $('#resetGame').on('click', () => simulator.reset());
  // Exports read the saved project, so unsaved block changes are not in the file.
  function exportSaved(path) {
    if (dirty) Kit.toast('Exporting the last saved version. Save first to include your newest changes.', 'warning');
    window.location.href = '/api/projects/' + encodeURIComponent(projectId) + path;
  }
  $('#exportProject').on('click', () => exportSaved('/export'));
  $('#exportArchive').on('click', () => exportSaved('/archive'));

  window.addEventListener('beforeunload', event => {
    if (dirty) {
      event.preventDefault();
      event.returnValue = '';
    }
  });

  loadProject().catch(err => Kit.toast(err.message, 'danger'));
})();
