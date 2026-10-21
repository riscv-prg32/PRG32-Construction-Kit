// The IDE page for one project (ADR-0013): fills the shell with the project's files and wires
// Save, Generate and Compile to the same API as the classic editor.
//
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
  const MODE_NAMES = { blocks: 'Blocks', c: 'Advanced C', asm: 'Assembly (RISC-V)' };
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
          ? $(`<div class="ide-editor-toolbar"><span class="small text-muted"></span>
              <button class="btn btn-outline-secondary btn-sm" type="button">Copy</button></div>`).appendTo(panel)
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
        if (toolbar) toolbar.find('button').on('click', () => navigator.clipboard.writeText(editor.getValue())
          .then(() => Kit.toast('Copied', 'success')).catch(() => Kit.toast('Select all and copy with Ctrl+C', 'warning')));
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
                { readOnly: true, closable: true, ariaLabel: titles[kind] + ', read-only' });
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
    $.getJSON('/api/sprites/' + encodeURIComponent(spriteId)).then(sprite => IdeShell.openTab({
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
    if (!blocklyReady || !simulator) return;
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
        if (!options.quiet) setBuildStatus('Compiler check: no toolchain on this server');
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

  // options: {autosave: true} (quiet), {baseVersion: n} (save over a newer version on purpose)
  function save(options = {}) {
    if (saving) return saving.then(() => save(options), () => save(options));  // one save at a time
    clearTimeout(autosaveTimer);
    const started = changes;
    const body = Object.assign(payload(), { expected_version: options.baseVersion ?? (project.version || 0) },
      options.autosave ? { autosave: true } : {});
    saving = Kit.api(api, { method: 'PUT', body }).then(saved => {
      project = saved;
      if (changes === started) setDirty(false); else scheduleAutosave();
      const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      $('#statusSaved').text(dirty ? 'Unsaved changes' : (options.autosave ? 'Autosaved ' + time : 'Saved'));
      if (!options.autosave) Kit.toast('Saved', 'success');
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
    IdeShell.showPanel('output');
    return save({ noCheck: true }).then(() => Kit.api(api + '/package', { method: 'POST',
      body: Object.assign({ source_language: mode === 'blocks' ? 'c' : mode }, expectedVersion()) }))
      .then(result => {
        $('#ideOutput').text(result.build.log || 'No log.');
        const cartridges = result.cartridge_artifacts || [];
        setBuildStatus(cartridges.length ? 'Cartridge ready' : result.build.status === 'failed' ? 'Build failed' : 'Source bundle only');
        showProblems(result.build.status === 'failed' ? parseProblems(result.build.log) : []);
        $('#ideCartridges').html(cartridges.map(artifact => `
          <a class="btn btn-outline-success btn-sm" target="_blank" rel="noopener" href="/player?artifact=${encodeURIComponent(artifact.id)}">
            <i class="bi bi-cpu" aria-hidden="true"></i> Run &amp; debug ${Kit.escape(artifact.metadata.architecture)}</a>
          <a class="btn btn-outline-primary btn-sm" href="/api/artifacts/${encodeURIComponent(artifact.id)}/download">
            <i class="bi bi-download" aria-hidden="true"></i> Download ${Kit.escape(artifact.metadata.architecture)} .prg32</a>`).join('')
          || '<span class="text-muted">No cartridge was made. See Output.</span>');
        if (cartridges.length) IdeShell.showPanel('run');
      })
      .catch(err => { $('#ideOutput').text(err.message); showProblems(parseProblems(err.message)); setBuildStatus('Build failed'); });
  }

  // --- mode ----------------------------------------------------------------------------------------
  function applyMode(newMode, sprites) {
    mode = newMode;
    $('#ideMode').val(mode);
    $('#statusMode').text(MODE_NAMES[mode]);
    for (const id of Array.from(IdeShell.tabs.keys())) {
      if (id !== 'blocks' && id !== 'src') IdeShell.closeTab(id);
    }
    if (IdeShell.tabs.has('src')) { const spec = IdeShell.tabs.get('src'); spec.closable = true; IdeShell.closeTab('src'); }
    $('#idePreviewPlay, #idePreviewStep').prop('disabled', mode !== 'blocks');
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
    command('compile', 'Compile cartridge', 'Ctrl+Shift+B', () => compile());
    command('compiler-check', 'Check with the compiler', '', () => save({ noCheck: true }).then(() => compilerCheck()));
    command('open-source', 'Open source', '', () => (mode === 'blocks' ? openBlocks(true) : openSource(true)));
    command('open-gen-c', 'Open generated C', '', () => mode === 'blocks' && openGenerated('c', true));
    command('open-gen-asm', 'Open generated assembly', '', () => mode === 'blocks' && openGenerated('asm', true));
    command('open-gen-ir', 'Open game IR', '', () => mode === 'blocks' && openGenerated('ir', true));
    command('focus-tree', 'Focus project files', 'F6', () => { IdeShell.toggleTree(true); IdeShell.focusTree(); });
    command('focus-editor', 'Focus editor', 'F6', () => IdeShell.focusRegion('editor'));
    command('show-problems', 'Show problems', '', () => { IdeShell.showPanel('problems'); IdeShell.focusRegion('panel'); });
    command('show-output', 'Show output', '', () => { IdeShell.showPanel('output'); IdeShell.focusRegion('panel'); });
    command('show-preview', 'Show Blocks preview', '', () => { IdeShell.showPanel('preview'); IdeShell.focusRegion('panel'); });
    command('show-run', 'Show run & debug', '', () => { IdeShell.showPanel('run'); IdeShell.focusRegion('panel'); });
    command('mode-blocks', 'Switch to Blocks', '', () => switchMode('blocks'));
    command('mode-c', 'Switch to Advanced C', '', () => switchMode('c'));
    command('mode-asm', 'Switch to Assembly (RISC-V)', '', () => switchMode('asm'));
    command('classic', 'Open the classic editor', '', () => { window.location.href = '/projects/' + encodeURIComponent(projectId); });
    IdeShell.addShortcut({ key: 's', ctrl: true, run: () => save() });
    IdeShell.addShortcut({ key: 'g', ctrl: true, shift: true, run: () => generate() });
    IdeShell.addShortcut({ key: 'b', ctrl: true, shift: true, run: () => compile() });
  }

  let spriteList = [];
  function switchMode(newMode) {
    if (newMode === mode) return;
    applyMode(newMode, spriteList);
    setDirty(true);
    Kit.toast(`Switched to ${MODE_NAMES[newMode]}. Save to keep it.`, 'info');
  }

  $('#ideMode').on('change', function () { switchMode(this.value); });
  $('#ideSave').on('click', () => save());
  $('#ideGenerate').on('click', () => generate());
  $('#ideCompile').on('click', () => compile());
  $('#idePreviewPlay').on('click', function () {
    if (!simulator) return;
    const running = simulator.toggle();
    $(this).text(running ? 'Pause' : 'Play');
  });
  $('#idePreviewStep').on('click', () => simulator && simulator.step());
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
      $('#ide').attr('data-ready', 'true');
    })
    .catch(err => Kit.toast('The IDE could not start: ' + err.message, 'danger'));

  window.PRG32Ide = { save, generate, compile, editors, openSdkHeader, get mode() { return mode; },
    get version() { return project && project.version; }, get autosavePaused() { return autosavePaused; },
    get dirty() { return dirty; }, get problems() { return $('#ideProblems').data('problems') || []; },
    get serverProblems() { return serverProblems; } };
})();
