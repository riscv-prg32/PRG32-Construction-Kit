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
// - PRG32 Python projects (ADR-0026): game.py is a Monaco editor (prg32-python); like the Blocks,
//   the generated C, assembly and IR open as read-only tabs, and the debugger follows game.py.
// - Problems appear in the Problems panel and as markers in the editor; Enter on a problem jumps
//   to its line. They come from the live checks while typing (language.js, ADR-0014) and from the
//   server's checks and the compiler after Generate / Compile.
// - Completion, hover, signature help and F12 "go to declaration" (into a read-only
//   prg32.h (portable API) tab) come from the committed PRG32 language index: no network.
(function () {
  'use strict';
  const projectId = $('#projectId').val();
  const api = '/api/projects/' + encodeURIComponent(projectId);
  const MODE_NAMES = { blocks: tr('common.blocks', 'Blocks'), c: 'C', asm: tr('js.ide.assembly_risc_v', 'Assembly (RISC-V)'), python: tr('js.ide.python_prg32_python', 'Python (PRG32 Python)') };
  // Blocks and Python are translated by the kit: they have generated C, assembly and IR to show.
  const generatesCode = () => mode === 'blocks' || mode === 'python';
  let project = null;
  let mode = 'blocks';
  let dirty = false;
  let monaco = null;
  let blocklyReady = false;
  let simulator = null;
  const editors = {};      // tab id -> Monaco editor
  const generated = { c: null, asm: null, py: null, ir: null };
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
    $('#statusSaved').text(readOnly() ? tr('js.ide.read_only_shared', 'Read-only (shared)') : value ? tr('js.ide.unsaved_changes', 'Unsaved changes') : tr('js.ide.saved', 'Saved'));
  }

  // A shared classroom project (the starter games): read and run it, never save it.
  function readOnly() { return !!project && project.can_edit === false; }

  // Save first only when there is something this window may save (Run reads the saved project).
  function saveIfNeeded(options) {
    return readOnly() || !dirty ? Promise.resolve() : save(options);
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
    editor.onDidChangeCursorPosition(event => $('#statusCursor').text(tr('js.ide.line_column', 'Ln {line}, Col {column}', { line: event.position.lineNumber, column: event.position.column })));
  }

  // --- tree -----------------------------------------------------------------------------------
  function sourceFile() { return { c: 'game.c', asm: 'game.S', python: 'game.py' }[mode]; }

  function renderTree(sprites) {
    const source = mode === 'blocks'
      ? [{ id: 'blocks', label: tr('js.ide.blocks_program', 'Blocks program'), icon: 'bi-puzzle' }]
      : [{ id: 'src', label: sourceFile(), icon: 'bi-file-earmark-code' }];
    const items = [{ id: 'folder-source', label: tr('js.ide.source', 'Source'), children: source }];
    if (generatesCode()) {
      items.push({ id: 'folder-generated', label: tr('js.ide.generated_read_only', 'Generated (read-only)'), children: [
        { id: 'gen-c', label: 'game.c', icon: 'bi-file-earmark-lock', readonly: true },
        { id: 'gen-asm', label: 'game.S', icon: 'bi-file-earmark-lock', readonly: true },
        // The Blocks as PRG32 Python, to read and compare (py_generator.py); a Python project's
        // game.py is its own source.
        ...(mode === 'blocks' ? [{ id: 'gen-py', label: 'game.py', icon: 'bi-file-earmark-lock', readonly: true }] : []),
        { id: 'gen-ir', label: 'game.ir.json', icon: 'bi-file-earmark-lock', readonly: true }] });
    }
    // Sprites and sound open Sprite Lab and AudioStudio as tabs, for this project (ADR-0024).
    items.push({ id: 'folder-sprites', label: tr('common.sprites', 'Sprites'), children: sprites
      .map(sprite => ({ id: 'sprite-' + sprite.id, label: sprite.name, icon: 'bi-image' }))
      .concat([{ id: 'sprite-new', label: tr('js.ide.new_sprite', 'New sprite…'), icon: 'bi-plus-circle' }]) });
    items.push({ id: 'folder-sound', label: tr('js.ide.sound', 'Sound'), children: [
      { id: 'sound-voices', label: tr('js.ide.voices', 'Voices'), icon: 'bi-soundwave' },
      { id: 'sound-effects', label: tr('js.ide.sound_effects', 'Sound effects'), icon: 'bi-music-note' },
      { id: 'sound-tracks', label: tr('js.ide.soundtracks', 'Soundtracks'), icon: 'bi-music-note-list' },
      { id: 'sound-samples', label: tr('js.ide.samples', 'Samples'), icon: 'bi-mic' }] });
    IdeShell.renderTree(items, openFile);
  }

  function openFile(id) {
    if (id === 'blocks') return openBlocks(true);
    if (id === 'src') return openSource(true);
    if (id === 'gen-c' || id === 'gen-asm' || id === 'gen-py' || id === 'gen-ir') return openGenerated(id.slice(4), true);
    if (id === 'sprite-new') { openTool('sprites'); return PRG32SpriteLab.create(); }
    if (id.startsWith('sprite-')) { openTool('sprites'); return PRG32SpriteLab.open(id.slice(7)); }
    if (id.startsWith('sound-')) return openTool('sound', id.slice(6));
  }

  // --- editors ---------------------------------------------------------------------------------
  // The code editors follow the page's Day or Night colours, also when the menu bar's switch changes them.
  const monacoTheme = () => (document.documentElement.getAttribute('data-bs-theme') === 'dark' ? 'vs-dark' : 'vs');
  $(document).on('kit:color-scheme', () => { if (monaco) monaco.editor.setTheme(monacoTheme()); });
  function monacoTab(id, title, language, value, options) {
    return IdeShell.openTab({
      id, title, closable: options.closable,
      render(panel) {
        const toolbar = options.readOnly
          ? $(`<div class="ide-editor-toolbar"><span class="small text-muted"></span><span class="d-flex gap-1">
              <button class="btn btn-outline-secondary btn-sm ide-copy" type="button">${tr('js.ide.copy', 'Copy')}</button>
              ${options.download ? '<button class="btn btn-outline-secondary btn-sm ide-download" type="button"><i class="bi bi-download" aria-hidden="true"></i> ' + Kit.escape(tr('js.ide.download', 'Download')) + '</button>' : ''}
              </span></div>`).appendTo(panel)
          : null;
        if (toolbar) toolbar.find('span').first().text(options.note || (mode === 'python' ? tr('js.ide.read_only_made_from_game_py', 'Read-only: made from game.py.')
          : tr('js.ide.read_only_made_from_the_blocks', 'Read-only: made from the blocks.')));
        const host = $('<div class="ide-monaco" data-focus-target></div>').appendTo(panel);
        const editor = monaco.editor.create(host[0], Object.assign(options.model ? { model: options.model } : { value, language }, {
          readOnly: !!options.readOnly, automaticLayout: true, minimap: { enabled: false },
          ariaLabel: options.ariaLabel, fontSize: 14, scrollBeyondLastLine: false, tabSize: 4,
          theme: monacoTheme(),
        }));
        editors[id] = editor;
        host.data('focus', () => editor.focus());
        trackCursor(editor);
        if (toolbar) toolbar.find('.ide-copy').on('click', () => navigator.clipboard.writeText(editor.getValue())
          .then(() => Kit.toast(tr('js.ide.copied', 'Copied'), 'success')).catch(() => Kit.toast(tr('js.ide.select_all_and_copy_with_ctrl', 'Select all and copy with Ctrl+C'), 'warning')));
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
        note: tr('js.ide.read_only_everything_a_prg32_cartridge', 'Read-only: everything a PRG32 cartridge can call (PRG32 ABI ') +
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

  const SOURCE_FIELDS = { c: 'source_c', asm: 'source_asm', python: 'source_python' };
  function openSource(focus) {
    const language = { c: 'c', asm: 'prg32-asm', python: 'prg32-python' }[mode];
    const saved = project.game_json || {};
    const text = saved.source_mode === mode ? saved[SOURCE_FIELDS[mode]] : '';
    monacoTab('src', sourceFile(), language, text || '', {
      closable: false, ariaLabel: { c: tr('js.ide.c_source_code', 'C source code'), asm: tr('js.ide.risc_v_assembly_source_code', 'RISC-V assembly source code'),
        python: tr('js.ide.prg32_python_source_code_game_py', 'PRG32 Python source code (game.py)') }[mode],
      onChange: () => setDirty(true),
      onClose: () => { if (liveChecks) { liveChecks.dispose(); liveChecks = null; } liveProblems = []; renderProblems(); },
    });
    if (!liveChecks) {
      liveChecks = PRG32MonacoLanguage.attach(monaco, editors.src.getModel(), mode,
        () => project.title, problems => { liveProblems = problems; renderProblems(); });
    }
    if (focus) editors.src.focus();
  }

  function openGenerated(kind, focus) {
    const titles = { c: tr('js.ide.game_c_generated', 'game.c (generated)'), asm: tr('js.ide.game_s_generated', 'game.S (generated)'),
                     py: tr('js.ide.game_py_generated', 'game.py (generated)'), ir: 'game.ir.json' };
    const languages = { c: 'c', asm: 'prg32-asm', py: 'prg32-python', ir: 'json' };
    const tab = IdeShell.tabs.get('gen-' + kind);
    if (tab && editors['gen-' + kind]) {
      IdeShell.activateTab('gen-' + kind);
    } else {
      monacoTab('gen-' + kind, titles[kind], languages[kind], generated[kind] || (kind === 'py' ? '# ' : '// ') + 'Press Generate to make this file.',
                { readOnly: true, closable: true, ariaLabel: titles[kind] + tr('js.ide.read_only', ', read-only'),
                  download: { c: 'game.c', asm: 'game.S', py: 'game.py', ir: 'game.ir.json' }[kind],
                  note: kind === 'py' ? tr('js.ide.read_only_the_blocks_in_prg32_python', 'Read-only: the blocks written in PRG32 Python, to compare. The cartridge is built from game.c.') : undefined });
    }
    if (focus) editors['gen-' + kind].focus();
    if (generated[kind] === null) generate();
  }

  function updateGenerated() {
    for (const kind of ['c', 'asm', 'py', 'ir']) {
      const editor = editors['gen-' + kind];
      if (editor && generated[kind] !== null) editor.setValue(generated[kind]);
    }
  }

  function openBlocks(focus) {
    IdeShell.openTab({
      id: 'blocks', title: tr('js.ide.blocks_program', 'Blocks program'), closable: false,
      render(panel) {
        // Focusable, so F6 and "Open source" can put the keyboard focus on the workspace.
        $('<div id="blocklyDiv" class="ide-blockly" data-focus-target tabindex="0" role="region" aria-label="' + Kit.escape(tr('js.ide.blocks_workspace', 'Blocks workspace')) + '"></div>').appendTo(panel);
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

  // Sprite Lab and AudioStudio are on the page once, hidden (#ideToolHolder); a tab borrows the
  // tool while it is open and gives it back when closed (moving keeps every event handler).
  const TOOLS = { sprites: { element: 'spriteLab', title: 'Sprite Lab' }, sound: { element: 'audioStudio', title: 'AudioStudio' } };
  function openTool(name, section) {
    const tool = TOOLS[name];
    if (IdeShell.tabs.has('tool-' + name)) IdeShell.activateTab('tool-' + name);
    else {
      IdeShell.openTab({
        id: 'tool-' + name, title: tool.title, closable: true,
        render(panel) { $(panel).addClass('ide-tool-panel').append($('#' + tool.element)); },
        onClose() { $('#ideToolHolder').append($('#' + tool.element)); },
      });
    }
    if (section && window.PRG32KitTool) PRG32KitTool.show('#' + tool.element, section);
  }

  function openToolFromHash() {
    const wanted = window.location.hash.slice(1);
    if (wanted === 'sprites' || wanted === 'sound') openTool(wanted);
  }
  window.addEventListener('hashchange', () => { if (project) openToolFromHash(); });

  // The top menu's Editor, Sprite Lab and AudioStudio (base.html) switch tab here, without
  // loading the page again; the address keeps the tool, so reloading opens it again.
  $('[data-ide-tool="editor"], [data-ide-tool="sprites"], [data-ide-tool="sound"]').on('click', function (event) {
    event.preventDefault();
    const item = $(this).attr('data-ide-tool');
    // The folded menu of a small screen closes.
    if ($('#topNav').hasClass('show')) bootstrap.Collapse.getOrCreateInstance(document.getElementById('topNav'), { toggle: false }).hide();
    history.replaceState(null, '', window.location.pathname + (item === 'editor' ? '' : '#' + item));
    if (!project) return;               // still loading: the start opens the tool from the address
    if (item === 'editor') openFile(mode === 'blocks' ? 'blocks' : 'src');
    else openTool(item);
  });
  $(document).on('ide:tab', (event, id) => Kit.projectMenu.mark(id === 'tool-sprites' ? 'sprites' : id === 'tool-sound' ? 'sound' : 'editor'));

  // A tool changed the project: the tree and the blocks follow.
  $(document).on('prg32:sprites-changed', () => {
    Kit.api('/api/sprites?project_id=' + encodeURIComponent(projectId))
      .then(data => { spriteList = data.sprites || []; renderTree(spriteList); }).catch(() => {});
  });
  $(document).on('prg32:audio-saved', () => { loadAudio(); });

  // --- preview (Blocks) -------------------------------------------------------------------------
  function refreshPreview() {
    if (!previewMode || !blocklyReady || !simulator) return;
    simulator.loadBlocks(PRG32Blocks.save());
  }

  // --- problems ---------------------------------------------------------------------------------
  // Server and compiler messages -> problems at exact places, without server paths (language.js).
  function parseProblems(text) {
    const source = editors.src ? editors.src.getValue() : '';
    const problems = PRG32Language.normalizeCompilerOutput(text, { language: mode === 'asm' ? 'asm' : mode === 'python'
      ? 'python' : 'c', source });
    if (!problems.length && text && !/^\s*$/.test(text)) {
      problems.push({ line: 0, column: 0, endLine: 0, endColumn: 0, severity: 'error', code: 'server',
        message: PRG32Language.withoutPaths(String(text)), explanation: '' });
    }
    return problems;
  }

  // A refusal that names its problem (code and exact range, routes.Refusal) is used as it is;
  // other errors are read from their text.
  function problemsOf(err) {
    const given = err && err.data && Array.isArray(err.data.problems) ? err.data.problems : null;
    if (!given) return parseProblems(err && err.message);
    return given.map(problem => ({ line: problem.line || 0, column: problem.column || 0,
      endLine: problem.end_line || problem.line || 0, endColumn: problem.end_column || problem.column || 0,
      severity: problem.severity || 'error', code: problem.code || 'server',
      message: String(problem.message || err.message), explanation: '' }));
  }

  // The same problem found by the live check and by the server is listed once. In another
  // interface language the live check speaks that language and the server English: a live
  // problem then stands for the server's problem on the same line.
  function sameProblem(a, b) {
    const text = problem => problem.message.replace(/^Line \d+: /, '');
    if (a.line === b.line && b.code === 'server' && window.PRG32I18n && PRG32I18n.locale !== 'en') return true;
    return a.line === b.line && (text(a) === text(b) || text(b).startsWith(text(a).split(':')[0]));
  }

  function renderProblems() {
    const problems = liveProblems.concat(serverProblems.filter(server => !liveProblems.some(live => sameProblem(server, live))));
    $('#problemCount').text(problems.length);
    $('#ideProblems').html(problems.length ? problems.map((problem, index) => `<li><button type="button" class="ide-problem"
        data-index="${index}"><i class="bi ${problem.severity === 'warning' ? 'bi-exclamation-triangle text-warning' : 'bi-x-circle text-danger'}" aria-hidden="true"></i>
        <span class="visually-hidden">${problem.severity === 'warning' ? tr('js.ide.warning', 'warning') : tr('js.ide.error', 'error')}</span>
        ${problem.line ? tr('js.ide.line_n', 'Line {line}: ', { line: problem.line }) : ''}${Kit.escape(problem.message.replace(/^Line \d+: /, ''))}
        ${problem.explanation ? `<span class="d-block small text-muted">${Kit.escape(problem.explanation)}</span>` : ''}</button></li>`).join('')
      : `<li class="text-muted">${tr('ide.no_problems', 'No problems.')}</li>`);
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
    // Python: the server's PRG32 Python compiler checks game.py first (a refusal names the line);
    // then, with a toolchain, the C made from it is compiled like Advanced C.
    checking = Kit.api(api + '/check', { method: 'POST', body: { source_language: mode === 'python' ? 'c' : mode } }).then(result => {
      if (!result.available && mode === 'python') {
        if (project.version === version) showProblems([], options.quiet);
        setBuildStatus(tr('js.ide.prg32_python_no_problems', 'PRG32 Python: no problems'));
        return;
      }
      if (!result.available) {
        if (!options.quiet) setBuildStatus(result.guest ? tr('js.ide.compiler_check_sign_in_to_use', 'Compiler check: sign in to use the compiler')
          : tr('js.ide.compiler_check_no_toolchain_on_this', 'Compiler check: no toolchain on this server'));
        return;
      }
      if (project.version !== version || result.project_version !== version) return;   // saved again since
      const problems = result.ok ? [] : parseProblems(result.log);
      showProblems(problems, options.quiet);
      setBuildStatus(result.ok ? tr('js.ide.compiler_no_problems', 'Compiler: no problems') : tr('js.ide.compiler_problems', 'Compiler: {count} problems', { count: problems.length }));
    }).catch(err => {
      if (mode === 'python' && project.version === version && (err.data && err.data.problems || /^Line \d+: /.test(err.message))) {
        const problems = problemsOf(err);
        showProblems(problems, options.quiet);
        setBuildStatus(tr('js.ide.python_problems', 'PRG32 Python: {count} problems', { count: problems.length }));
        return;
      }
      if (!options.quiet) setBuildStatus(tr('js.ide.compiler_check', 'Compiler check: {message}', { message: err.message }));
    });
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
    if (mode === 'python') {
      return { blocks_json: project.blocks_json || {}, game_json: { source_mode: 'python', source_python: text,
        python_language_version: PRG32LanguageIndex.python.version } };
    }
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
      $('#statusSaved').text(dirty ? tr('js.ide.unsaved_changes', 'Unsaved changes') : (options.autosave ? tr('js.ide.autosaved', 'Autosaved {time}', { time: time }) : tr('js.ide.saved', 'Saved')));
      if (!options.autosave && !options.quiet) Kit.toast(tr('js.ide.saved', 'Saved'), 'success');
      if (!options.noCheck) compilerCheck({ quiet: options.autosave });
      return saved;
    }).catch(err => {
      if (err.code === 'version_conflict') {
        autosavePaused = true;
        $('#statusSaved').text(tr('js.ide.not_saved_saved_elsewhere', 'Not saved: saved elsewhere'));
        Kit.versionConflict(err, { copy: keepMineAsCopy, reload: loadSavedVersion,
          overwrite: version => { autosavePaused = false; return save({ baseVersion: version }); } });
      } else {
        $('#statusSaved').text(tr('js.ide.not_saved', 'Not saved: {message}', { message: err.message }));
        if (!options.autosave || err.code === 'quota_exceeded') Kit.toast(tr('js.ide.not_saved', 'Not saved: {message}', { message: err.message }), 'danger');
      }
      throw err;
    }).finally(() => { saving = null; });
    return saving;
  }

  function keepMineAsCopy() {
    return Kit.api('/api/projects', { method: 'POST', body: Object.assign(payload(), { title: project.title + tr('js.ide.my_version', ' (my version)') }) })
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
    if (mode === 'python') return { expected_source_python: saved.source_python };
    return { expected_blocks_json: project.blocks_json };
  }

  function generate() {
    setBuildStatus(tr('js.ide.generating', 'Generating…'));
    const language = generatesCode() ? 'both' : mode;
    // A shared project (read-only here) is generated by the stateless converter: nothing is stored.
    const generating = readOnly()
      ? Kit.api('/api/guest/convert', { method: 'POST', body: { source_language: language, project: {
          title: project.title, blocks_json: blocklyReady ? PRG32Blocks.save() : project.blocks_json, game_json: project.game_json } } })
      : save({ noCheck: true }).then(() => Kit.api(api + '/convert', { method: 'POST', body: { source_language: language } }));
    return generating
      .then(result => {
        if (generatesCode()) {
          generated.c = result.c_source || '';
          generated.asm = result.asm_source || '';
          generated.py = result.python_source || '';
          generated.ir = JSON.stringify(result.game_ir, null, 2);
          updateGenerated();
        }
        showProblems([]);
        setBuildStatus(tr('js.ide.generated', 'Generated'));
        $('#ideOutput').text(mode === 'blocks' ? tr('js.ide.generated_c_assembly_and_ir_from', 'Generated C, assembly and IR from the blocks.')
          : mode === 'python' ? tr('js.ide.generated_c_assembly_and_ir_from_2', 'Generated C, assembly and IR from game.py.') : tr('js.ide.the_source_passed_the_kit_s', 'The source passed the kit\'s checks.'));
      })
      .catch(err => { showProblems(problemsOf(err)); setBuildStatus(tr('js.ide.problems_found', 'Problems found')); });
  }

  function compile() {
    setBuildStatus(tr('js.ide.compiling', 'Compiling…'));
    $('#ideOutput').text(tr('js.ide.compiling', 'Compiling…'));
    $('#ideCartridges').empty();
    IdeShell.showPanel('build');
    log(tr('js.ide.compile_building_the_cartridges_to_downl', 'Compile: building the cartridges to download…'));
    return save({ noCheck: true }).then(() => Kit.api(api + '/package', { method: 'POST',
      body: Object.assign({ source_language: generatesCode() ? buildFrom() : mode }, expectedVersion()) }))
      .then(result => {
        $('#ideOutput').text(result.build.log || tr('js.ide.no_log', 'No log.'));
        const cartridges = result.cartridge_artifacts || [];
        setBuildStatus(cartridges.length ? tr('js.ide.cartridge_ready', 'Cartridge ready') : result.build.status === 'failed' ? tr('js.ide.build_failed', 'Build failed') : tr('js.ide.source_bundle_only', 'Source bundle only'));
        showProblems(result.build.status === 'failed' ? parseProblems(result.build.log) : []);
        $('#ideCartridges').html(cartridges.map(artifact => `
          <a class="btn btn-outline-primary btn-sm" href="/api/artifacts/${encodeURIComponent(artifact.id)}/download">
            <i class="bi bi-download" aria-hidden="true"></i> ${Kit.escape(tr('js.ide.download_arch_cartridge', 'Download {architecture} .prg32', { architecture: artifact.metadata.architecture }))}</a>`).join('')
          || `<span class="text-muted">${tr('js.ide.no_cartridge_see_log', 'No cartridge was made: see the log below.')}</span>`);
        log(cartridges.length ? tr('js.ide.compile_cartridges_ready', 'Compile: {count} cartridges ready to download.', { count: cartridges.length }) : tr('js.ide.compile_no_cartridge_was_made', 'Compile: no cartridge was made.'),
            cartridges.length ? 'ok' : 'error');
      })
      .catch(err => {
        $('#ideOutput').text(err.message); showProblems(problemsOf(err)); setBuildStatus(tr('js.ide.build_failed', 'Build failed'));
        log(tr('js.ide.compile', 'Compile: {message}', { message: err.message }), 'error');
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
    setBuildStatus(tr('js.ide.building_to_run', 'Building to run…'));
    $('#ideRun').prop('disabled', true);
    log(tr('js.ide.run_building', 'Run: building {title}', { title: project.title }) + tr('js.ide.for_the_simulator', ' for the simulator…'));
    return saveIfNeeded({ noCheck: true, quiet: true }).then(() => Kit.api(api + '/run', { method: 'POST', body: {} }))
      .then(answer => {
        $('#ideOutput').text(answer.log || tr('js.ide.no_log', 'No log.'));
        $('#ideCartridges').empty();
        if (!answer.ok) {
          showProblems(parseProblems(answer.log));
          setBuildStatus(tr('js.ide.build_failed', 'Build failed'));
          IdeShell.showPanel('build');
          log(tr('js.ide.run_the_game_did_not_build', 'Run: the game did not build. See Build and Problems.'), 'error');
          return null;
        }
        showProblems([], true);
        lastRun = { bytes: base64Bytes(answer.cartridge), debug: answer.debug };
        return startCartridge(lastRun.bytes, lastRun.debug).then(() => {
          setBuildStatus(tr('js.ide.running', 'Running'));
          log(tr('js.ide.run_running_in_the_simulator_click', 'Run: running in the simulator. Click the screen to use the game keys.'), 'ok');
        });
      })
      .catch(err => {
        if (err.code === 'no_toolchain' && mode === 'blocks' && blocklyReady) {
          // This server cannot compile: Blocks still run in the JavaScript preview.
          usePreview(true);
          simulator.loadBlocks(PRG32Blocks.save());
          if (!simulator.running) simulator.toggle();
          setBuildStatus(tr('js.ide.running_blocks_preview', 'Running (Blocks preview)'));
          log(tr('js.ide.run_this_server_cannot_compile_so', 'Run: this server cannot compile, so the Blocks preview runs instead of the PRG32 core.'), 'error');
          return;
        }
        setBuildStatus(tr('js.ide.not_running', 'Not running'));
        if (err.data && err.data.problems) showProblems(problemsOf(err));
        log(tr('js.ide.run', 'Run: {message}', { message: err.message }), 'error');
        if (err.code !== 'sign_in_required') Kit.toast(err.message, 'danger');
      })
      .finally(() => $('#ideRun').prop('disabled', false));
  }

  function restart() {
    if (previewMode) { simulator.reset(); return Promise.resolve(); }
    if (!lastRun) return run();
    log(tr('js.ide.restart_the_game_starts_again', 'Restart: the game starts again.'));
    return startCartridge(lastRun.bytes, lastRun.debug);
  }

  // --- mode ----------------------------------------------------------------------------------------
  function applyMode(newMode, sprites) {
    mode = newMode;
    $('#ideType').text(MODE_NAMES[mode]).attr('data-type', mode);
    $('.ide-blocks-only').prop('hidden', mode !== 'blocks');
    $('.ide-generated-only').prop('hidden', !generatesCode());
    $('.ide-code-only').prop('hidden', mode === 'blocks' || mode === 'python');
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
    command('save', tr('js.ide.save_project', 'Save project'), 'Ctrl+S', () => save());
    command('generate', tr('js.ide.generate_c_and_assembly_check_the', 'Generate C and assembly (check the source)'), 'Ctrl+Shift+G', () => generate());
    command('run', tr('js.ide.run_in_the_simulator', 'Run in the simulator'), 'Shift+F10', () => run());
    command('restart', tr('js.ide.restart_the_game', 'Restart the game'), '', () => restart());
    command('compile', tr('js.ide.compile_cartridges_to_download', 'Compile cartridges to download'), 'Ctrl+Shift+B', () => compile());
    command('compiler-check', tr('js.ide.check_with_the_compiler', 'Check with the compiler'), '', () => save({ noCheck: true }).then(() => compilerCheck()));
    command('open-source', tr('js.ide.open_source', 'Open source'), '', () => (mode === 'blocks' ? openBlocks(true) : openSource(true)));
    command('open-gen-c', tr('js.ide.open_generated_c', 'Open generated C'), '', () => generatesCode() && openGenerated('c', true));
    command('open-gen-asm', tr('js.ide.open_generated_assembly', 'Open generated assembly'), '', () => generatesCode() && openGenerated('asm', true));
    command('open-gen-py', tr('js.ide.open_generated_python', 'Open the blocks as PRG32 Python'), '', () => mode === 'blocks' && openGenerated('py', true));
    command('open-gen-ir', tr('js.ide.open_game_ir', 'Open game IR'), '', () => generatesCode() && openGenerated('ir', true));
    command('focus-tree', tr('js.ide.focus_project_files', 'Focus project files'), 'F6', () => { IdeShell.toggleTree(true); IdeShell.focusTree(); });
    command('focus-editor', tr('js.ide.focus_editor', 'Focus editor'), 'F6', () => IdeShell.focusRegion('editor'));
    command('show-problems', tr('js.ide.show_problems', 'Show problems'), '', () => { IdeShell.showPanel('problems'); IdeShell.focusRegion('panel'); });
    command('show-build', tr('js.ide.show_the_build_log', 'Show the build log'), '', () => { IdeShell.showPanel('build'); IdeShell.focusRegion('panel'); });
    command('show-console', tr('js.ide.show_the_console', 'Show the console'), '', () => { IdeShell.showPanel('console'); IdeShell.focusRegion('panel'); });
    command('show-debug', tr('js.ide.show_the_debugger', 'Show the debugger'), '', () => { IdeShell.showPanel('debug'); IdeShell.focusRegion('panel'); });
    command('focus-simulator', tr('js.ide.focus_the_simulator', 'Focus the simulator'), '', () => { IdeShell.showPane('sim', true); IdeShell.focusRegion('simulator'); });
    command('toggle-files', tr('js.ide.show_or_hide_the_project_files', 'Show or hide the project files'), 'Alt+1', () => IdeShell.showPane('tree'));
    command('toggle-panel', tr('js.ide.show_or_hide_the_tool_window', 'Show or hide the tool window'), 'Alt+4', () => IdeShell.showPane('panel'));
    command('toggle-simulator', tr('js.ide.show_or_hide_the_simulator', 'Show or hide the simulator'), 'Alt+9', () => IdeShell.showPane('sim'));
    command('properties', tr('js.ide.project_properties', 'Project properties'), '', () => showProperties());
    command('sprite-lab', tr('js.ide.open_sprite_lab', 'Open Sprite Lab'), '', () => openTool('sprites'));
    command('audio-studio', tr('js.ide.open_audiostudio', 'Open AudioStudio'), '', () => openTool('sound'));
    command('history', tr('js.ide.history_earlier_versions', 'History: earlier versions'), '', () => showHistory());
    command('export-archive', tr('js.ide.export_project_zip', 'Export project (.zip)'), '', () => exportSaved('/archive'));
    command('export-json', tr('js.ide.export_project_as_json', 'Export project as JSON'), '', () => exportSaved('/export'));
    command('copy', tr('js.ide.make_a_copy_of_this_project', 'Make a copy of this project'), '', () => makeCopy(project.title + ' (copy)'));
    command('convert-c', tr('js.ide.convert_this_blocks_project_to_c', 'Convert this Blocks project to C (one way)'), '', () => mode === 'blocks' && askConvert('c'));
    command('convert-asm', tr('js.ide.convert_this_blocks_project_to_assembly', 'Convert this Blocks project to Assembly (one way)'), '', () => mode === 'blocks' && askConvert('asm'));
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
  $('#ideSharedCopy').on('click', () => makeCopy(project.title + tr('js.ide.my_copy', ' (my copy)')));
  $('#ideCopy').on('click', () => (dirty ? save({ quiet: true }) : Promise.resolve()).then(() => makeCopy(project.title + ' (copy)')));

  // Exports read the saved project: save first so the file has the newest changes.
  function exportSaved(path) {
    return (dirty && project.can_edit !== false ? save({ noCheck: true, quiet: true }) : Promise.resolve())
      .then(() => Kit.download(api + path));
  }
  $('#ideExportArchive').on('click', () => exportSaved('/archive'));
  $('#ideExportJson').on('click', () => exportSaved('/export'));

  const REASONS = { save: tr('js.ide.before_a_save', 'before a save'), autosave: 'autosave', restore: tr('js.ide.before_a_restore', 'before a restore'), convert: tr('js.ide.before_converting', 'before converting') };
  function showHistory() {
    const list = $('#ideHistoryList').html(`<li class="list-group-item small text-muted">${tr('common.loading', 'Loading…')}</li>`);
    modal('ideHistoryDialog').show();
    Kit.api(api + '/revisions').then(data => {
      if (!data.revisions.length) {
        list.html(`<li class="list-group-item small text-muted">${tr('js.ide.no_earlier_versions_yet', 'No earlier versions yet. They appear after you save a change.')}</li>`);
        return;
      }
      list.html(data.revisions.map(rev => `<li class="list-group-item d-flex flex-wrap gap-2 align-items-center justify-content-between">
        <span class="small"><strong>#${rev.number}</strong> ${Kit.escape(Kit.when(rev.created_at))}
          <span class="text-muted">(${Kit.escape(REASONS[rev.reason] || rev.reason)}, ${Kit.escape(rev.authoring_mode || '')})</span></span>
        <span class="text-nowrap">
          <button class="btn btn-outline-primary btn-sm ide-restore" type="button" data-id="${Kit.escape(rev.id)}" data-number="${rev.number}"
            ${project.can_edit === false ? 'disabled' : ''}>${tr('js.ide.restore', 'Restore')}</button>
          <button class="btn btn-outline-secondary btn-sm ide-revision-download" type="button" data-id="${Kit.escape(rev.id)}"
            aria-label="${Kit.escape(tr('js.ide.download_version_n', 'Download version {number}', { number: rev.number }))}"><i class="bi bi-download" aria-hidden="true"></i></button>
        </span></li>`).join(''));
    }).catch(err => list.html(`<li class="list-group-item small text-danger">${Kit.escape(err.message)}</li>`));
  }
  $('#ideHistory').on('click', showHistory);
  $('#ideHistoryList').on('click', '.ide-revision-download', function () {
    Kit.download(api + '/revisions/' + encodeURIComponent($(this).data('id')) + '/archive');
  }).on('click', '.ide-restore', function () {
    const unsaved = dirty ? tr('js.ide.your_unsaved_changes_in_this_window', ' Your unsaved changes in this window will be lost.') : '';
    if (!window.confirm(tr('js.ide.go_back_to_version', 'Go back to version #{number}? The current saved version is kept in History.', { number: $(this).data('number') }) + unsaved)) return;
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
    log(tr('js.ide.convert_making_this_project', 'Convert: making this project {language}…', { language: MODE_NAMES[language] }));
    return save({ noCheck: true, quiet: true })
      .then(() => Kit.api(api + '/convert_to', { method: 'POST', body: { language, expected_version: project.version } }))
      .then(() => {
        dirty = false;   // saved and converted: no "leave page?" question
        window.location.reload();
      })
      .catch(err => { log(tr('js.ide.convert', 'Convert: {message}', { message: err.message }), 'error'); Kit.toast(err.message, 'danger'); });
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
      document.title = project.title + tr('js.ide.ide_prg32_construction_kit', ' - IDE - PRG32 Construction Kit');
      const saved = project.game_json || {};
      applyMode(['c', 'asm', 'python'].includes(saved.source_mode) ? saved.source_mode : 'blocks', spriteList);
      setDirty(false);
      showShared();
      $('#projectTitle').text(project.title);
      // /ide/<id>#sprites or #sound (the Sprite Lab and AudioStudio menu items) open that tool.
      openToolFromHash();
      $('#ide').attr('data-ready', 'true');
    })
    .catch(err => Kit.toast(tr('js.ide.the_ide_could_not_start', 'The IDE could not start: {message}', { message: err.message }), 'danger'));

  window.PRG32Ide = { save, generate, compile, run, restart, log, editors, openSdkHeader, get mode() { return mode; },
    get version() { return project && project.version; }, get autosavePaused() { return autosavePaused; },
    get dirty() { return dirty; }, get problems() { return $('#ideProblems').data('problems') || []; },
    get serverProblems() { return serverProblems; } };
})();
