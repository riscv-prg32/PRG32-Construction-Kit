// The IDE page for one project (ADR-0013, ADR-0024): fills the shell with the project's files and
// wires Save, Run, Generate and Compile.
//
// - Run builds the saved project for the simulator on the right (a run build: nothing is kept,
//   /api/projects/<id>/run) and starts it in the PRG32 core, with the debugger in the tool
//   window's Debug tab. Blocks, C and assembly run the same way. Only when the server cannot
//   compile do Blocks fall back to the JavaScript preview.
// - Compile makes the cartridges to download or publish (needs an account).
// - Blocks projects: the Blockly workspace is the source (Blockly JSON stays canonical); the
//   generated C, assembly and IR open as read-only Monaco tabs that can be copied.
// - Advanced C / assembly projects: the source is a Monaco editor (C, or the prg32-asm grammar).
// - Problems appear in the Problems panel and as markers in the editor; Enter on a problem jumps
//   to its line. They come from the live checks while typing (language.js, ADR-0014) and from the
//   server's checks and the compiler after Generate / Compile.
// - Completion, hover, signature help and F12 "go to declaration" (into a read-only
//   prg32.h (portable API) tab) come from the committed PRG32 language index: no network.
(function () {
  'use strict';
  const projectId = $('#projectId').val();
  const api = '/api/projects/' + encodeURIComponent(projectId);
  const MODE_NAMES = { blocks: 'Blocks', c: 'C', asm: 'Assembly (RISC-V)' };
  let project = null;
  let mode = 'blocks';
  let dirty = false;
  let monaco = null;
  let blocklyReady = false;
  let simulator = null;
  const editors = {};      // tab id -> Monaco editor
  const generated = { c: null, asm: null, ir: null };
  let liveProblems = [];   // from the live checks of the open source
  let serverProblems = []; // from the last Generate or Compile
  let liveChecks = null;
  let lastRun = null;      // {bytes, debug}: Restart loads the same cartridge again
  let previewMode = false; // true: Blocks run in the JavaScript preview (no toolchain on this server)

  // Autosave (ADR-0017): 5 seconds after the last change, and when the window is hidden.
  // Every save names the version it started from; a conflict pauses autosave until the
  // student decides (Kit.versionConflict), so nothing is ever overwritten silently.
  const AUTOSAVE_MS = 5000;
  let autosaveTimer = null;
  let autosavePaused = false;
  let changes = 0;          // counts edits, so an edit made while saving stays unsaved
  let saving = null;

  // --- status bar ------------------------------------------------------------------------------
  function setDirty(value) {
    dirty = value;
    if (value) {
      changes += 1;
      scheduleAutosave();
    }
    $('#statusSaved').text(value ? 'Unsaved changes' : 'Saved');
  }

  function scheduleAutosave() {
    clearTimeout(autosaveTimer);
    if (!autosavePaused) autosaveTimer = setTimeout(() => { if (dirty) save({ autosave: true }).catch(() => {}); }, AUTOSAVE_MS);
  }
  function setBuildStatus(text) { $('#statusBuild').text(text); }

  // The Console tab: what the kit did, newest last (read-only; there is no shell on the server).
  function log(text, kind) {
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const line = $('<li></li>').toggleClass('text-danger', kind === 'error').toggleClass('text-success', kind === 'ok');
    line.append($('<time></time>').text(time)).append(document.createTextNode(text));
    $('#ideConsole').append(line);
    const list = $('#ideConsole').children();
    if (list.length > 300) list.first().remove();
    const panel = document.getElementById('panel-console');
    panel.scrollTop = panel.scrollHeight;
  }
  function trackCursor(editor) {
    editor.onDidChangeCursorPosition(event => $('#statusCursor').text(`Ln ${event.position.lineNumber}, Col ${event.position.column}`));
  }

  // --- tree -----------------------------------------------------------------------------------
  function sourceFile() { return mode === 'c' ? 'game.c' : 'game.S'; }

  function renderTree(sprites) {
    const source = mode === 'blocks'
      ? [{ id: 'blocks', label: 'Blocks program', icon: 'bi-puzzle' }]
      : [{ id: 'src', label: sourceFile(), icon: 'bi-file-earmark-code' }];
    const items = [{ id: 'folder-source', label: 'Source', children: source }];
    if (mode === 'blocks') {
      items.push({ id: 'folder-generated', label: 'Generated (read-only)', children: [
        { id: 'gen-c', label: 'game.c', icon: 'bi-file-earmark-lock', readonly: true },
        { id: 'gen-asm', label: 'game.S', icon: 'bi-file-earmark-lock', readonly: true },
        { id: 'gen-ir', label: 'game.ir.json', icon: 'bi-file-earmark-lock', readonly: true }] });
    }
    items.push({ id: 'folder-sprites', label: 'Sprites', children: sprites.length
      ? sprites.map(sprite => ({ id: 'sprite-' + sprite.id, label: sprite.name, icon: 'bi-image', readonly: true }))
      : [{ id: 'sprite-none', label: '(no sprites)', icon: 'bi-dash', readonly: true }] });
    IdeShell.renderTree(items, openFile);
  }

  function openFile(id) {
    if (id === 'blocks') return openBlocks(true);
    if (id === 'src') return openSource(true);
    if (id === 'gen-c' || id === 'gen-asm' || id === 'gen-ir') return openGenerated(id.slice(4), true);
    if (id.startsWith('sprite-') && id !== 'sprite-none') return openSprite(id.slice(7));
  }

  // --- editors ---------------------------------------------------------------------------------
  function monacoTab(id, title, language, value, options) {
    return IdeShell.openTab({
      id, title, closable: options.closable,
      render(panel) {
        const toolbar = options.readOnly
          ? $(`<div class="ide-editor-toolbar"><span class="small text-muted"></span><span class="d-flex gap-1">
              <button class="btn btn-outline-secondary btn-sm ide-copy" type="button">Copy</button>
              ${options.download ? '<button class="btn btn-outline-secondary btn-sm ide-download" type="button"><i class="bi bi-download" aria-hidden="true"></i> Download</button>' : ''}
              </span></div>`).appendTo(panel)
          : null;
        if (toolbar) toolbar.find('span').text(options.note || 'Read-only: made from the blocks.');
        const host = $('<div class="ide-monaco" data-focus-target></div>').appendTo(panel);
        const editor = monaco.editor.create(host[0], Object.assign(options.model ? { model: options.model } : { value, language }, {
          readOnly: !!options.readOnly, automaticLayout: true, minimap: { enabled: false },
          ariaLabel: options.ariaLabel, fontSize: 14, scrollBeyondLastLine: false, tabSize: 4,
        }));
        editors[id] = editor;
        host.data('focus', () => editor.focus());
        trackCursor(editor);
        if (toolbar) toolbar.find('.ide-copy').on('click', () => navigator.clipboard.writeText(editor.getValue())
          .then(() => Kit.toast('Copied', 'success')).catch(() => Kit.toast('Select all and copy with Ctrl+C', 'warning')));
        // Export the generated code as a file (the project stays Blocks; Convert makes it code for good).
        if (toolbar && options.download) toolbar.find('.ide-download').on('click', () => {
          const link = document.createElement('a');
          link.href = URL.createObjectURL(new Blob([editor.getValue()], { type: 'text/plain' }));
          link.download = options.download;
          link.click();
          setTimeout(() => URL.revokeObjectURL(link.href), 1000);
        });
        if (options.onChange) editor.onDidChangeModelContent(options.onChange);
      },
      onShow() { if (editors[id]) setTimeout(() => editors[id].layout(), 0); },
      onClose() {
        if (options.onClose) options.onClose();
        if (editors[id]) { editors[id].dispose(); delete editors[id]; }
      },
    });
  }

  // "Go to declaration" on a PRG32 name: the generated, read-only list of the portable API.
  function openSdkHeader(line) {
    if (!editors['sdk-h']) {
      monacoTab('sdk-h', 'prg32.h (portable API)', 'c', '', {
        readOnly: true, closable: true, model: PRG32MonacoLanguage.sdkModel,
        note: 'Read-only: everything a PRG32 cartridge can call (PRG32 ABI ' +
          `${PRG32LanguageIndex.abi.major}.${PRG32LanguageIndex.abi.minor}).`,
        ariaLabel: 'prg32.h, the portable PRG32 API, read-only' });
    } else {
      IdeShell.activateTab('sdk-h');
    }
    const editor = editors['sdk-h'];
    editor.revealLineInCenter(line);
    editor.setPosition({ lineNumber: line, column: 1 });
    editor.focus();
  }

  function openSource(focus) {
    const language = mode === 'c' ? 'c' : 'prg32-asm';
    const saved = project.game_json || {};
    const text = mode === 'c' ? (saved.source_mode === 'c' ? saved.source_c : '') : (saved.source_mode === 'asm' ? saved.source_asm : '');
    monacoTab('src', sourceFile(), language, text || '', {
      closable: false, ariaLabel: mode === 'c' ? 'C source code' : 'RISC-V assembly source code',
      onChange: () => setDirty(true),
      onClose: () => { if (liveChecks) { liveChecks.dispose(); liveChecks = null; } liveProblems = []; renderProblems(); },
    });
    if (!liveChecks) {
      liveChecks = PRG32MonacoLanguage.attach(monaco, editors.src.getModel(), mode === 'c' ? 'c' : 'asm',
        () => project.title, problems => { liveProblems = problems; renderProblems(); });
    }
    if (focus) editors.src.focus();
  }

  function openGenerated(kind, focus) {
    const titles = { c: 'game.c (generated)', asm: 'game.S (generated)', ir: 'game.ir.json' };
    const languages = { c: 'c', asm: 'prg32-asm', ir: 'json' };
    const tab = IdeShell.tabs.get('gen-' + kind);
    if (tab && editors['gen-' + kind]) {
      IdeShell.activateTab('gen-' + kind);
    } else {
      monacoTab('gen-' + kind, titles[kind], languages[kind], generated[kind] || '// Press Generate to make this file.',
                { readOnly: true, closable: true, ariaLabel: titles[kind] + ', read-only',
                  download: { c: 'game.c', asm: 'game.S', ir: 'game.ir.json' }[kind] });
    }
    if (focus) editors['gen-' + kind].focus();
    if (generated[kind] === null) generate();
  }

  function updateGenerated() {
    for (const kind of ['c', 'asm', 'ir']) {
      const editor = editors['gen-' + kind];
      if (editor && generated[kind] !== null) editor.setValue(generated[kind]);
    }
  }

  function openBlocks(focus) {
    IdeShell.openTab({
      id: 'blocks', title: 'Blocks program', closable: false,
      render(panel) {
        // Focusable, so F6 and "Open source" can put the keyboard focus on the workspace.
        $('<div id="blocklyDiv" class="ide-blockly" data-focus-target tabindex="0" role="region" aria-label="Blocks workspace"></div>').appendTo(panel);
      },
      onShow() {
        if (!blocklyReady) {
          blocklyReady = true;
          PRG32Blocks.init('blocklyDiv');
          PRG32Blocks.load(project.blocks_json || {});
          PRG32Blocks.getWorkspace().addChangeListener(event => {
            if (!event.isUiEvent && event.type !== 'finished_loading') { setDirty(true); refreshPreview(); }
          });
          $('#blocklyDiv').data('focus', () => $('#blocklyDiv').trigger('focus'));
          refreshPreview();
        }
        setTimeout(() => Blockly.svgResize(PRG32Blocks.getWorkspace()), 0);
      },
    });
    if (focus) $('#blocklyDiv').data('focus')();
  }

  function openSprite(spriteId) {
    Kit.api('/api/sprites/' + encodeURIComponent(spriteId)).then(sprite => IdeShell.openTab({
      id: 'sprite-' + spriteId, title: sprite.name, closable: true,
      render(panel) {
        $(panel).append(`<div class="p-3"><p class="small text-muted">Sprites are drawn in the
          <a href="/sprites">Sprite Lab</a>.</p>${sprite.data_url
          ? `<img class="ide-sprite" alt="Sprite ${Kit.escape(sprite.name)}" src="${Kit.escape(sprite.data_url)}">` : ''}
          <p class="small">${sprite.width} &times; ${sprite.height} pixels</p></div>`);
      },
    }));
  }

  // --- preview (Blocks) -------------------------------------------------------------------------
  function refreshPreview() {
    if (!previewMode || !blocklyReady || !simulator) return;
    simulator.loadBlocks(PRG32Blocks.save());
  }

  // --- problems ---------------------------------------------------------------------------------
  // Server and compiler messages -> problems at exact places, without server paths (language.js).
  function parseProblems(text) {
    const source = editors.src ? editors.src.getValue() : '';
    const problems = PRG32Language.normalizeCompilerOutput(text, { language: mode === 'asm' ? 'asm' : 'c', source });
    if (!problems.length && text && !/^\s*$/.test(text)) {
      problems.push({ line: 0, column: 0, endLine: 0, endColumn: 0, severity: 'error', code: 'server',
        message: PRG32Language.withoutPaths(String(text)), explanation: '' });
    }
    return problems;
  }

  // The same problem found by the live check and by the server is listed once.
  function sameProblem(a, b) {
    const text = problem => problem.message.replace(/^Line \d+: /, '');
    return a.line === b.line && (text(a) === text(b) || text(b).startsWith(text(a).split(':')[0]));
  }

  function renderProblems() {
    const problems = liveProblems.concat(serverProblems.filter(server => !liveProblems.some(live => sameProblem(server, live))));
    $('#problemCount').text(problems.length);
    $('#ideProblems').html(problems.length ? problems.map((problem, index) => `<li><button type="button" class="ide-problem"
        data-index="${index}"><i class="bi ${problem.severity === 'warning' ? 'bi-exclamation-triangle text-warning' : 'bi-x-circle text-danger'}" aria-hidden="true"></i>
        <span class="visually-hidden">${problem.severity}</span>
        ${problem.line ? `Line ${problem.line}: ` : ''}${Kit.escape(problem.message.replace(/^Line \d+: /, ''))}
        ${problem.explanation ? `<span class="d-block small text-muted">${Kit.escape(problem.explanation)}</span>` : ''}</button></li>`).join('')
      : '<li class="text-muted">No problems.</li>');
    $('#ideProblems').data('problems', problems);
  }

  function showProblems(problems, quiet) {
    serverProblems = problems;
    renderProblems();
    const model = editors.src && editors.src.getModel();
    if (model) {
      monaco.editor.setModelMarkers(model, 'prg32', problems.filter(problem => problem.line > 0
          && problem.line <= model.getLineCount()).map(problem => ({
        startLineNumber: problem.line, startColumn: Math.max(1, problem.column),
        endLineNumber: problem.line, endColumn: problem.endColumn > problem.column ? problem.endColumn
          : model.getLineMaxColumn(problem.line),
        message: problem.explanation ? `${problem.message}\n${problem.explanation}` : problem.message,
        severity: problem.severity === 'warning' ? monaco.MarkerSeverity.Warning : monaco.MarkerSeverity.Error,
      })));
    }
    if (problems.length && !quiet) IdeShell.showPanel('problems');
  }

  // The compiler check (ADR-0014): after a save, the server compiles the saved C or assembly
  // with the real PRG32 toolchain in its build sandbox and keeps nothing; its messages join the
  // Problems list. It only adds problems: the kit's own checks still decide what is valid.
  let checking = null;
  function compilerCheck(options = {}) {
    if (mode === 'blocks' || !project) return Promise.resolve();
    const version = project.version;
    checking = Kit.api(api + '/check', { method: 'POST', body: { source_language: mode } }).then(result => {
      if (!result.available) {
        if (!options.quiet) setBuildStatus(result.guest ? 'Compiler check: sign in to use the compiler'
          : 'Compiler check: no toolchain on this server');
        return;
      }
      if (project.version !== version || result.project_version !== version) return;   // saved again since
      const problems = result.ok ? [] : parseProblems(result.log);
      showProblems(problems, options.quiet);
      setBuildStatus(result.ok ? 'Compiler: no problems' : `Compiler: ${problems.length} problem${problems.length === 1 ? '' : 's'}`);
    }).catch(err => { if (!options.quiet) setBuildStatus('Compiler check: ' + err.message); });
    return checking;
  }

  $('#ideProblems').on('click', '.ide-problem', function () {
    const problem = $('#ideProblems').data('problems')[$(this).data('index')];
    if (!problem.line || mode === 'blocks') return;
    openSource(false);
    editors.src.revealLineInCenter(problem.line);
    editors.src.setPosition({ lineNumber: problem.line, column: Math.max(1, problem.column) });
    editors.src.focus();
  });

  // --- save / generate / compile ----------------------------------------------------------------
  function payload() {
    const saved = project.game_json || {};
    const features = Array.isArray(saved.required_features) ? saved.required_features : [];
    if (mode === 'blocks') {
      const blocks = blocklyReady ? PRG32Blocks.save() : (project.blocks_json || {});
      return { blocks_json: blocks, game_json: PRG32Simulator.compileBlocks(blocks) };
    }
    const text = editors.src ? editors.src.getValue() : '';
    return { blocks_json: project.blocks_json || {}, game_json: mode === 'c'
      ? { source_mode: 'c', source_c: text, required_features: features }
      : { source_mode: 'asm', source_asm: text, required_features: features } };
  }

  // options: {autosave: true} (quiet), {quiet: true} (no toast), {baseVersion: n} (save over a newer version on purpose)
  function save(options = {}) {
    if (saving) return saving.then(() => save(options), () => save(options));  // one save at a time
    clearTimeout(autosaveTimer);
    const started = changes;
    const body = Object.assign(payload(), options.extra || {}, { expected_version: options.baseVersion ?? (project.version || 0) },
      options.autosave ? { autosave: true } : {});
    saving = Kit.api(api, { method: 'PUT', body }).then(saved => {
      project = saved;
      if (changes === started) setDirty(false); else scheduleAutosave();
      const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      $('#statusSaved').text(dirty ? 'Unsaved changes' : (options.autosave ? 'Autosaved ' + time : 'Saved'));
      if (!options.autosave && !options.quiet) Kit.toast('Saved', 'success');
      if (!options.noCheck) compilerCheck({ quiet: options.autosave });
      return saved;
    }).catch(err => {
      if (err.code === 'version_conflict') {
        autosavePaused = true;
        $('#statusSaved').text('Not saved: saved elsewhere');
        Kit.versionConflict(err, { copy: keepMineAsCopy, reload: loadSavedVersion,
          overwrite: version => { autosavePaused = false; return save({ baseVersion: version }); } });
      } else {
        $('#statusSaved').text('Not saved: ' + err.message);
        if (!options.autosave || err.code === 'quota_exceeded') Kit.toast('Not saved: ' + err.message, 'danger');
      }
      throw err;
    }).finally(() => { saving = null; });
    return saving;
  }

  function keepMineAsCopy() {
    return Kit.api('/api/projects', { method: 'POST', body: Object.assign(payload(), { title: project.title + ' (my version)' }) })
      .then(copy => { dirty = false; window.location.href = '/ide/' + encodeURIComponent(copy.id); });
  }

  function loadSavedVersion() {
    dirty = false;  // the student chose the saved version: no "leave page?" question
    window.location.reload();
  }

  document.addEventListener('visibilitychange', () => {
    if (document.hidden && dirty && !autosavePaused && project) save({ autosave: true }).catch(() => {});
  });

  function expectedVersion() {
    const saved = project.game_json || {};
    if (mode === 'c') return { expected_source_c: saved.source_c };
    if (mode === 'asm') return { expected_source_asm: saved.source_asm };
    return { expected_blocks_json: project.blocks_json };
  }

  function generate() {
    setBuildStatus('Generating…');
    return save({ noCheck: true }).then(() => Kit.api(api + '/convert', { method: 'POST', body: { source_language: mode === 'blocks' ? 'both' : mode } }))
      .then(result => {
        if (mode === 'blocks') {
          generated.c = result.c_source || '';
          generated.asm = result.asm_source || '';
          generated.ir = JSON.stringify(result.game_ir, null, 2);
          updateGenerated();
        }
        showProblems([]);
        setBuildStatus('Generated');
        $('#ideOutput').text(mode === 'blocks' ? 'Generated C, assembly and IR from the blocks.' : 'The source passed the kit\'s checks.');
      })
      .catch(err => { showProblems(parseProblems(err.message)); setBuildStatus('Problems found'); });
  }

  function compile() {
    setBuildStatus('Compiling…');
    $('#ideOutput').text('Compiling…');
    $('#ideCartridges').empty();
    IdeShell.showPanel('build');
    log('Compile: building the cartridges to download…');
    return save({ noCheck: true }).then(() => Kit.api(api + '/package', { method: 'POST',
      body: Object.assign({ source_language: mode === 'blocks' ? buildFrom() : mode }, expectedVersion()) }))
      .then(result => {
        $('#ideOutput').text(result.build.log || 'No log.');
        const cartridges = result.cartridge_artifacts || [];
        setBuildStatus(cartridges.length ? 'Cartridge ready' : result.build.status === 'failed' ? 'Build failed' : 'Source bundle only');
        showProblems(result.build.status === 'failed' ? parseProblems(result.build.log) : []);
        $('#ideCartridges').html(cartridges.map(artifact => `
          <a class="btn btn-outline-primary btn-sm" href="/api/artifacts/${encodeURIComponent(artifact.id)}/download">
            <i class="bi bi-download" aria-hidden="true"></i> Download ${Kit.escape(artifact.metadata.architecture)} .prg32</a>`).join('')
          || '<span class="text-muted">No cartridge was made: see the log below.</span>');
        log(cartridges.length ? `Compile: ${cartridges.length} cartridge(s) ready to download.` : 'Compile: no cartridge was made.',
            cartridges.length ? 'ok' : 'error');
      })
      .catch(err => {
        $('#ideOutput').text(err.message); showProblems(parseProblems(err.message)); setBuildStatus('Build failed');
        log('Compile: ' + err.message, 'error');
      });
  }

  // --- run: the game in the simulator on the right -------------------------------------------------
  function base64Bytes(text) {
    const binary = atob(text);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    return bytes;
  }

  function usePreview(on) {
    previewMode = on;
    $('#gameCanvas, #debugState').prop('hidden', !on);
    $('#playerScreen').prop('hidden', on);
  }

  function startCartridge(bytes, debug) {
    if (simulator) simulator.stop();
    usePreview(false);
    return PRG32PlayerPage.open(bytes, project.title, { quiet: true }).then(() => {
      if (window.PRG32SourceDebugger) PRG32SourceDebugger.attach(debug || null);
      PRG32PlayerPage.player.start();
      $('#ideReset').prop('disabled', false);
      $('#playerScreen').trigger('focus');
    });
  }

  function run() {
    if (IdeShell.showPane && $('#ide').attr('data-sim') === 'closed') IdeShell.showPane('sim', true);
    setBuildStatus('Building to run…');
    $('#ideRun').prop('disabled', true);
    log('Run: building ' + project.title + ' for the simulator…');
    return save({ noCheck: true, quiet: true }).then(() => Kit.api(api + '/run', { method: 'POST', body: {} }))
      .then(answer => {
        $('#ideOutput').text(answer.log || 'No log.');
        $('#ideCartridges').empty();
        if (!answer.ok) {
          showProblems(parseProblems(answer.log));
          setBuildStatus('Build failed');
          IdeShell.showPanel('build');
          log('Run: the game did not build. See Build and Problems.', 'error');
          return null;
        }
        showProblems([], true);
        lastRun = { bytes: base64Bytes(answer.cartridge), debug: answer.debug };
        return startCartridge(lastRun.bytes, lastRun.debug).then(() => {
          setBuildStatus('Running');
          log('Run: running in the simulator. Click the screen to use the game keys.', 'ok');
        });
      })
      .catch(err => {
        if (err.code === 'no_toolchain' && mode === 'blocks' && blocklyReady) {
          // This server cannot compile: Blocks still run in the JavaScript preview.
          usePreview(true);
          simulator.loadBlocks(PRG32Blocks.save());
          if (!simulator.running) simulator.toggle();
          setBuildStatus('Running (Blocks preview)');
          log('Run: this server cannot compile, so the Blocks preview runs instead of the PRG32 core.', 'error');
          return;
        }
        setBuildStatus('Not running');
        log('Run: ' + err.message, 'error');
        if (err.code !== 'sign_in_required') Kit.toast(err.message, 'danger');
      })
      .finally(() => $('#ideRun').prop('disabled', false));
  }

  function restart() {
    if (previewMode) { simulator.reset(); return Promise.resolve(); }
    if (!lastRun) return run();
    log('Restart: the game starts again.');
    return startCartridge(lastRun.bytes, lastRun.debug);
  }

  // --- mode ----------------------------------------------------------------------------------------
  function applyMode(newMode, sprites) {
    mode = newMode;
    $('#ideType').text(MODE_NAMES[mode]).attr('data-type', mode);
    $('.ide-blocks-only').prop('hidden', mode !== 'blocks');
    $('.ide-code-only').prop('hidden', mode === 'blocks');
    $('#statusMode').text(MODE_NAMES[mode]);
    for (const id of Array.from(IdeShell.tabs.keys())) {
      if (id !== 'blocks' && id !== 'src') IdeShell.closeTab(id);
    }
    if (IdeShell.tabs.has('src')) { const spec = IdeShell.tabs.get('src'); spec.closable = true; IdeShell.closeTab('src'); }
    renderTree(sprites);
    if (mode === 'blocks') openBlocks(false); else openSource(false);
    if (mode !== 'blocks' && IdeShell.tabs.has('blocks')) $('#tab-blocks').attr('hidden', true);
    else $('#tab-blocks').removeAttr('hidden');
  }

  // --- commands and shortcuts --------------------------------------------------------------------
  function register() {
    const command = (id, title, keys, run) => IdeShell.addCommand({ id, title, keys, run });
    command('save', 'Save project', 'Ctrl+S', () => save());
    command('generate', 'Generate C and assembly (check the source)', 'Ctrl+Shift+G', () => generate());
    command('run', 'Run in the simulator', 'Shift+F10', () => run());
    command('restart', 'Restart the game', '', () => restart());
    command('compile', 'Compile cartridges to download', 'Ctrl+Shift+B', () => compile());
    command('compiler-check', 'Check with the compiler', '', () => save({ noCheck: true }).then(() => compilerCheck()));
    command('open-source', 'Open source', '', () => (mode === 'blocks' ? openBlocks(true) : openSource(true)));
    command('open-gen-c', 'Open generated C', '', () => mode === 'blocks' && openGenerated('c', true));
    command('open-gen-asm', 'Open generated assembly', '', () => mode === 'blocks' && openGenerated('asm', true));
    command('open-gen-ir', 'Open game IR', '', () => mode === 'blocks' && openGenerated('ir', true));
    command('focus-tree', 'Focus project files', 'F6', () => { IdeShell.toggleTree(true); IdeShell.focusTree(); });
    command('focus-editor', 'Focus editor', 'F6', () => IdeShell.focusRegion('editor'));
    command('show-problems', 'Show problems', '', () => { IdeShell.showPanel('problems'); IdeShell.focusRegion('panel'); });
    command('show-build', 'Show the build log', '', () => { IdeShell.showPanel('build'); IdeShell.focusRegion('panel'); });
    command('show-console', 'Show the console', '', () => { IdeShell.showPanel('console'); IdeShell.focusRegion('panel'); });
    command('show-debug', 'Show the debugger', '', () => { IdeShell.showPanel('debug'); IdeShell.focusRegion('panel'); });
    command('focus-simulator', 'Focus the simulator', '', () => { IdeShell.showPane('sim', true); IdeShell.focusRegion('simulator'); });
    command('toggle-files', 'Show or hide the project files', 'Alt+1', () => IdeShell.showPane('tree'));
    command('toggle-panel', 'Show or hide the tool window', 'Alt+4', () => IdeShell.showPane('panel'));
    command('toggle-simulator', 'Show or hide the simulator', 'Alt+9', () => IdeShell.showPane('sim'));
    command('properties', 'Project properties', '', () => showProperties());
    command('history', 'History: earlier versions', '', () => showHistory());
    command('export-archive', 'Export project (.zip)', '', () => exportSaved('/archive'));
    command('export-json', 'Export project as JSON', '', () => exportSaved('/export'));
    command('copy', 'Make a copy of this project', '', () => makeCopy(project.title + ' (copy)'));
    command('convert-c', 'Convert this Blocks project to C (one way)', '', () => mode === 'blocks' && askConvert('c'));
    command('convert-asm', 'Convert this Blocks project to Assembly (one way)', '', () => mode === 'blocks' && askConvert('asm'));
    IdeShell.addShortcut({ key: 's', ctrl: true, run: () => save() });
    IdeShell.addShortcut({ key: 'g', ctrl: true, shift: true, run: () => generate() });
    IdeShell.addShortcut({ key: 'b', ctrl: true, shift: true, run: () => compile() });
    IdeShell.addShortcut({ key: 'F10', shift: true, run: () => run() });
  }

  let spriteList = [];

  // --- the Project menu: properties, history, export, copy ----------------------------------------
  // Which generated file a Blocks project is compiled from (remembered per project in this browser).
  const BUILD_FROM_KEY = 'prg32-source-language-' + projectId;
  function buildFrom() { return $('#ideBuildFrom').val() || 'c'; }
  try { const saved = localStorage.getItem(BUILD_FROM_KEY); if (saved) $('#ideBuildFrom').val(saved); } catch (_) { /* private window */ }
  $('#ideBuildFrom').on('change', function () {
    try { localStorage.setItem(BUILD_FROM_KEY, this.value); } catch (_) { /* private window */ }
  });

  function modal(id) { return bootstrap.Modal.getOrCreateInstance(document.getElementById(id)); }

  // Shared classroom projects (the starter games): read and run, and make your own copy to change.
  function showShared() {
    const shared = project.can_edit === false;
    $('#ideShared').prop('hidden', !shared);
    $('#ideSave, #ideConvertConfirm').prop('disabled', shared);
    if (shared) {
      autosavePaused = true;
      Object.values(editors).forEach(editor => editor.updateOptions({ readOnly: true }));
    }
  }

  function makeCopy(title) {
    return Kit.api(api + '/duplicate', { method: 'POST', body: { title } })
      .then(created => { dirty = false; window.location.href = '/ide/' + encodeURIComponent(created.id); })
      .catch(err => Kit.toast(err.message, 'danger'));
  }
  $('#ideSharedCopy').on('click', () => makeCopy(project.title + ' (my copy)'));
  $('#ideCopy').on('click', () => (dirty ? save({ quiet: true }) : Promise.resolve()).then(() => makeCopy(project.title + ' (copy)')));

  // Exports read the saved project: save first so the file has the newest changes.
  function exportSaved(path) {
    return (dirty && project.can_edit !== false ? save({ noCheck: true, quiet: true }) : Promise.resolve())
      .then(() => Kit.download(api + path));
  }
  $('#ideExportArchive').on('click', () => exportSaved('/archive'));
  $('#ideExportJson').on('click', () => exportSaved('/export'));

  const REASONS = { save: 'before a save', autosave: 'autosave', restore: 'before a restore', convert: 'before converting' };
  function showHistory() {
    const list = $('#ideHistoryList').html('<li class="list-group-item small text-muted">Loading…</li>');
    modal('ideHistoryDialog').show();
    Kit.api(api + '/revisions').then(data => {
      if (!data.revisions.length) {
        list.html('<li class="list-group-item small text-muted">No earlier versions yet. They appear after you save a change.</li>');
        return;
      }
      list.html(data.revisions.map(rev => `<li class="list-group-item d-flex flex-wrap gap-2 align-items-center justify-content-between">
        <span class="small"><strong>#${rev.number}</strong> ${Kit.escape(rev.created_at.replace('T', ' ').replace('+00:00', ' UTC'))}
          <span class="text-muted">(${Kit.escape(REASONS[rev.reason] || rev.reason)}, ${Kit.escape(rev.authoring_mode || '')})</span></span>
        <span class="text-nowrap">
          <button class="btn btn-outline-primary btn-sm ide-restore" type="button" data-id="${Kit.escape(rev.id)}" data-number="${rev.number}"
            ${project.can_edit === false ? 'disabled' : ''}>Restore</button>
          <button class="btn btn-outline-secondary btn-sm ide-revision-download" type="button" data-id="${Kit.escape(rev.id)}"
            aria-label="Download version ${rev.number}"><i class="bi bi-download" aria-hidden="true"></i></button>
        </span></li>`).join(''));
    }).catch(err => list.html(`<li class="list-group-item small text-danger">${Kit.escape(err.message)}</li>`));
  }
  $('#ideHistory').on('click', showHistory);
  $('#ideHistoryList').on('click', '.ide-revision-download', function () {
    Kit.download(api + '/revisions/' + encodeURIComponent($(this).data('id')) + '/archive');
  }).on('click', '.ide-restore', function () {
    const unsaved = dirty ? ' Your unsaved changes in this window will be lost.' : '';
    if (!window.confirm(`Go back to version #${$(this).data('number')}? The current saved version is kept in History.` + unsaved)) return;
    Kit.api(api + '/revisions/' + encodeURIComponent($(this).data('id')) + '/restore', { method: 'POST', body: {} })
      .then(() => { dirty = false; window.location.reload(); })
      .catch(err => Kit.toast(err.message, err.code === 'type_locked' ? 'warning' : 'danger'));
  });

  function showProperties() {
    const saved = project.game_json || {};
    $('#propTitle').val(project.title);
    $('#propAuthor').val(project.author || '');
    $('#propDescription').val(project.description || '');
    $('#propTags').val((project.tags || []).join(', '));
    $('#propFeatures').val((saved.required_features || []).join(', '));
    $('#propPrefix').text(PRG32Language.entryPrefix ? PRG32Language.entryPrefix(project.title) : '');
    $('#idePropertiesForm button[type=submit]').prop('disabled', project.can_edit === false);
    modal('idePropertiesDialog').show();
  }
  $('#ideProperties').on('click', showProperties);
  $('#propTitle').on('input', function () {
    if (PRG32Language.entryPrefix) $('#propPrefix').text(PRG32Language.entryPrefix(this.value));
  });
  $('#idePropertiesForm').on('submit', function (event) {
    event.preventDefault();
    const list = text => String(text || '').split(',').map(item => item.trim()).filter(Boolean);
    project.title = $('#propTitle').val().trim() || project.title;
    project.author = $('#propAuthor').val();
    project.description = $('#propDescription').val();
    project.tags = list($('#propTags').val());
    if (mode !== 'blocks') project.game_json = Object.assign({}, project.game_json, { required_features: list($('#propFeatures').val()) });
    const fields = { title: project.title, author: project.author, description: project.description, tags: project.tags };
    // The properties go with the next save, together with the source (one version, one save).
    setDirty(true);
    save({ extra: fields }).then(() => {
      modal('idePropertiesDialog').hide();
      $('#ideTitle').text(project.title);
      document.title = project.title + ' - IDE';
    }).catch(() => {});
  });

  // --- convert Blocks to C or assembly: one way (ADR-0024) ------------------------------------------
  let convertTo = null;
  function askConvert(language) {
    convertTo = language;
    $('#ideConvertDialog .ide-convert-to').text(MODE_NAMES[language]);
    bootstrap.Modal.getOrCreateInstance(document.getElementById('ideConvertDialog')).show();
  }

  function convert(language) {
    log(`Convert: making this project ${MODE_NAMES[language]}…`);
    return save({ noCheck: true, quiet: true })
      .then(() => Kit.api(api + '/convert_to', { method: 'POST', body: { language, expected_version: project.version } }))
      .then(() => {
        dirty = false;   // saved and converted: no "leave page?" question
        window.location.reload();
      })
      .catch(err => { log('Convert: ' + err.message, 'error'); Kit.toast(err.message, 'danger'); });
  }

  $('#ideProjectItems').on('click', '[data-convert]', function () { askConvert($(this).data('convert')); });
  $('#ideConvertConfirm').on('click', () => {
    bootstrap.Modal.getOrCreateInstance(document.getElementById('ideConvertDialog')).hide();
    if (convertTo) convert(convertTo);
  });
  $('#ideSave').on('click', () => save());
  $('#ideGenerate').on('click', () => generate());
  $('#ideCompile').on('click', () => compile());
  $('#ideRun').on('click', () => run());
  $('#ideReset').on('click', () => restart());
  // In the Blocks preview (no toolchain), Play and Frame drive the JavaScript simulator instead.
  $('#playPause').on('click', () => { if (previewMode) simulator.toggle(); });
  $('#stepFrame').on('click', () => { if (previewMode) simulator.step(); });
  window.addEventListener('beforeunload', event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });

  // --- start -----------------------------------------------------------------------------------------
  register();
  simulator = new PRG32Simulator.Simulator(document.getElementById('gameCanvas'), document.getElementById('debugState'));
  // The project's AudioStudio sound (docs/audio_studio.md): names for the sound blocks, and the
  // simulator's preview through the PRG32 engine, as in the classic editor.
  function loadAudio() {
    return Kit.api(api + '/audio').then(audio => {
      PRG32Blocks.setAudioNames({ effects: audio.document.effects.map(effect => effect.name),
                                  soundtracks: audio.document.soundtracks.map(track => track.name) });
      PRG32Simulator.setAudio(audio.document);
      const engine = new window.PRG32AudioEngine();
      const block = audio.asset_id && !audio.missing_samples.length
        ? Kit.api(api + '/audio/preview', { method: 'POST', body: {} }) : Promise.resolve(null);
      return block.then(bytes => engine.start(bytes)).then(() => { simulator.audioEngine = engine; });
    }).catch(() => { /* the game still runs, silently */ });
  }

  Promise.all([Kit.api(api), Kit.api('/api/sprites?project_id=' + encodeURIComponent(projectId)), PRG32Monaco.load(),
               loadAudio()])
    .then(([data, sprites, loadedMonaco]) => {
      project = data;
      monaco = loadedMonaco;
      PRG32MonacoLanguage.register(monaco, { openSdk: openSdkHeader });
      spriteList = sprites.sprites || [];
      $('#ideTitle').text(project.title);
      document.title = project.title + ' - IDE - PRG32-Construction-Kit';
      const saved = project.game_json || {};
      applyMode(saved.source_mode === 'c' ? 'c' : saved.source_mode === 'asm' ? 'asm' : 'blocks', spriteList);
      setDirty(false);
      showShared();
      $('#ide').attr('data-ready', 'true');
    })
    .catch(err => Kit.toast('The IDE could not start: ' + err.message, 'danger'));

  window.PRG32Ide = { save, generate, compile, run, restart, log, editors, openSdkHeader, get mode() { return mode; },
    get version() { return project && project.version; }, get autosavePaused() { return autosavePaused; },
    get dirty() { return dirty; }, get problems() { return $('#ideProblems').data('problems') || []; },
    get serverProblems() { return serverProblems; } };
})();
