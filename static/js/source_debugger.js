// The source and block panels of the Player's debugger (ADR-0015).
//
// When the cartridge came from the kit (/player?artifact=<id>), player.js fetches
// GET /api/artifacts/<id>/debug and calls PRG32SourceDebugger.attach(info). The panels then
// show, whenever the game is paused:
//   Blocks     the project's blocks (read-only), the running block highlighted
//   Source     game.c / game.S with the running line; Enter on a line number = breakpoint
//   Where      line, block and function in words
//   Variables  the Blocks variables (beginner) or locals, parameters and globals (advanced)
//   Call stack which function called which; choose one to see its variables
//   Watches    names to keep an eye on: score, player.x, heights[2], a0
//   CSR, Stack the counter registers and the words around sp (advanced)
// Source and block breakpoints are ordinary address breakpoints in the core; a condition
// (score > 10) is checked when one hits, and the game runs on while it is false.
// Without debug information everything here stays hidden and the address debugger works as before.
(function () {
  'use strict';

  const player = window.prg32Player;
  if (!player) return;

  let debug = null;          // PRG32SourceDebug session
  let info = null;           // the /debug answer
  let workspace = null;      // read-only Blockly workspace
  let selectedFrame = 0;
  let lastPc = null;
  const lineBreakpoints = new Map();   // line -> {addresses, condition}
  const blockBreakpoints = new Map();  // block id -> {addresses, condition}
  const watches = [];
  const memory = { read: (address, length) => player.readMemory(address, length) };

  const escape = text => Kit.escape(String(text));
  const hex = value => '0x' + (value >>> 0).toString(16).padStart(8, '0');
  const advanced = () => $('body').hasClass('dbg-mode-advanced');

  function storageKey() { return 'prg32-kit-source-breakpoints:' + (player.sha256 || ''); }

  function remember() {
    const saved = { lines: [...lineBreakpoints].map(([line, item]) => [line, item.condition || '']),
      blocks: [...blockBreakpoints].map(([block, item]) => [block, item.condition || '']), watches };
    try { localStorage.setItem(storageKey(), JSON.stringify(saved)); } catch (_) { /* private window */ }
  }

  function restore() {
    let saved = null;
    try { saved = JSON.parse(localStorage.getItem(storageKey()) || 'null'); } catch (_) { saved = null; }
    if (!saved) return;
    for (const [line, condition] of saved.lines || []) setLineBreakpoint(Number(line), true, condition);
    for (const [block, condition] of saved.blocks || []) setBlockBreakpoint(block, true, condition);
    watches.splice(0, watches.length, ...(saved.watches || []).slice(0, 20));
  }

  // --- breakpoints -------------------------------------------------------------------
  function placeAddresses(addresses, enabled) {
    for (const address of addresses) player.debug({ command: 'breakpoint', address, enabled });
  }

  function setLineBreakpoint(line, enabled, condition) {
    if (!enabled) {
      const item = lineBreakpoints.get(line);
      if (item) placeAddresses(item.addresses, false);
      lineBreakpoints.delete(line);
    } else {
      const found = debug.breakpointForLine(line);
      if (!found) { Kit.toast(`Line ${line} has no code to stop at.`, 'warning'); return; }
      if (found.line !== line) Kit.toast(`Line ${line} has no code of its own: the breakpoint is on line ${found.line}.`, 'info');
      lineBreakpoints.set(found.line, { addresses: found.addresses, condition: condition || '' });
      placeAddresses(found.addresses, true);
    }
    remember();
    render(player.debugState());
  }

  function setBlockBreakpoint(block, enabled, condition) {
    if (!enabled) {
      const item = blockBreakpoints.get(block);
      if (item) placeAddresses(item.addresses, false);
      blockBreakpoints.delete(block);
    } else {
      const found = debug.breakpointForBlock(block);
      if (!found) { Kit.toast('This block makes no code of its own (a comment, or inside an empty part).', 'warning'); return; }
      blockBreakpoints.set(block, { addresses: found.addresses, condition: condition || '' });
      placeAddresses(found.addresses, true);
    }
    markBlocks();
    remember();
    render(player.debugState());
  }

  function conditionAt(pc) {
    for (const item of [...lineBreakpoints.values(), ...blockBreakpoints.values()]) {
      if (item.condition && item.addresses.includes(pc >>> 0)) return item.condition;
    }
    return '';
  }

  // Called by the player when an address breakpoint hits: true = stop here.
  function breakpointFilter(state) {
    const text = conditionAt(state.pc);
    if (!text) return true;
    const frame = debug.callStack(state, memory)[0];
    const verdict = debug.condition(text, frame, memory);
    if (!verdict.ok) {
      Kit.toast(`Breakpoint condition "${text}": ${verdict.error}. Stopping here.`, 'warning');
      return true;
    }
    return verdict.value;
  }

  // --- Blocks -------------------------------------------------------------------------
  function openBlocks() {
    if (!info.blocks_json || !debug.hasBlocks || workspace) return;
    PRG32Blocks.defineBlocks();
    workspace = Blockly.inject('dbgBlocks', {
      readOnly: true, scrollbars: true, sounds: false, media: '/static/vendor/blockly/11.2.1/media/',
      zoom: { controls: true, wheel: true, startScale: 0.6, maxScale: 2.0, minScale: 0.2 },
    });
    Blockly.serialization.workspaces.load(info.blocks_json, workspace);
    workspace.addChangeListener(event => {
      if (event.type === Blockly.Events.SELECTED && event.newElementId) chooseBlock(event.newElementId);
    });
    // A read-only workspace does not select blocks on a click (and Blockly keeps the click to
    // itself), so the press is read first, in the capture phase: the innermost block under it.
    document.getElementById('dbgBlocks').addEventListener('pointerdown', event => {
      const group = event.target.closest && event.target.closest('#dbgBlocks g[data-id]');
      const block = group && workspace.getBlockById(group.getAttribute('data-id'));
      if (block) setTimeout(() => Blockly.common.setSelected(block), 0);
    }, true);
    // The same choice from the keyboard: every block that made code, in program order.
    $('#dbgBlockChoose').html('<option value="">Choose a block…</option>' + entries()
      .filter(entry => workspace.getBlockById(entry.block))
      .map(entry => `<option value="${escape(entry.block)}">${escape(entry.ir)}: ${escape(describeBlock(entry.block))}</option>`).join(''));
    markBlocks();
  }

  function entries() { return (info.source_map && info.source_map.entries) || []; }

  function chooseBlock(id) {
    $('#dbgBlockSelected').data('block', id).text(describeBlock(id));
    $('#dbgBlockChoose').val(id);
    $('#dbgBlockBreak').prop('disabled', !id);
  }

  function describeBlock(id) {
    const block = workspace && workspace.getBlockById(id);
    if (!block) return id;
    const text = block.toString(40).replace(/\s+/g, ' ');
    return blockBreakpoints.has(id) ? `● ${text}` : text;
  }

  function markBlocks() {
    if (!workspace) return;
    for (const block of workspace.getAllBlocks(false)) {
      const root = block.getSvgRoot();
      if (root) root.classList.toggle('dbg-block-breakpoint', blockBreakpoints.has(block.id));
    }
  }

  // The running block: Blockly's own highlight plus a class (an outline anyone can see, and tests can find).
  let activeBlock = null;
  function showBlock(entry) {
    if (!workspace) return;
    const id = entry ? entry.block : null;
    workspace.highlightBlock(id);
    const previous = activeBlock && workspace.getBlockById(activeBlock);
    if (previous && previous.getSvgRoot()) previous.getSvgRoot().classList.remove('dbg-block-active');
    activeBlock = id;
    const block = id && workspace.getBlockById(id);
    if (block) {
      block.getSvgRoot().classList.add('dbg-block-active');
      workspace.centerOnBlock(id);
    }
  }

  // --- Source ------------------------------------------------------------------------
  let sourceLines = [];
  function renderSourceText() {
    sourceLines = (info.source ? info.source.text : '').split('\n');
    const rows = sourceLines.map((text, index) => {
      const line = index + 1;
      return `<div class="dbg-src-line" data-line="${line}"><button type="button" class="dbg-src-gutter"
        data-line="${line}" aria-label="Line ${line}: breakpoint on or off">${line}</button><code>${escape(text) || ' '}</code></div>`;
    });
    $('#dbgSource').html(rows.join(''));
  }

  function renderSourceMarks(line) {
    $('#dbgSource .dbg-src-line').removeClass('dbg-current dbg-bp');
    for (const bp of lineBreakpoints.keys()) $(`#dbgSource .dbg-src-line[data-line="${bp}"]`).addClass('dbg-bp');
    if (line) {
      const row = $(`#dbgSource .dbg-src-line[data-line="${line}"]`).addClass('dbg-current');
      if (row[0]) row[0].scrollIntoView({ block: 'nearest' });
    }
  }

  // --- panels ------------------------------------------------------------------------
  function valueRows(items) {
    return items.map(item => `<tr><th scope="row">${escape(item.name)}${item.type ? ` <span class="text-muted small">${escape(item.type)}</span>` : ''}</th>
      <td class="${item.unavailable ? 'text-muted' : ''}">${escape(item.text)}${item.children
        ? `<ul class="list-unstyled mb-0 ms-2 small">${item.children.map(child => `<li>${escape(child.name)}: ${escape(child.text)}</li>`).join('')}</ul>` : ''}</td></tr>`).join('');
  }

  function renderPanels(state) {
    const stack = debug.callStack(state, memory);
    if (selectedFrame >= stack.length) selectedFrame = 0;
    const frame = stack[selectedFrame];
    const top = stack[0];
    const entry = debug.blockAt(state.pc);
    // Where
    const where = [];
    if (top && top.line) where.push(`Line <strong>${top.line}</strong> of ${escape(top.file)}`);
    if (entry && workspace) where.push(`block <strong>${escape(describeBlock(entry.block))}</strong>`);
    if (top) where.push(`in <code>${escape(top.function)}</code>`);
    $('#dbgWhere').html(where.length ? where.join(' · ') : 'Outside the program (in the PRG32 firmware or between frames).');
    showBlock(entry);
    renderSourceMarks(frame && frame.file === debug.userFile ? frame.line : null);
    // Variables: beginners see the game's own variables; advanced users see the frame too.
    const globals = debug.globals(memory).filter(item => advanced() || !item.name.startsWith('prg32_kit_'));
    const locals = advanced() || !debug.hasBlocks ? debug.variables(frame, memory) : [];
    $('#dbgVariables').html((locals.length ? `<tr><th colspan="2" class="text-muted small">In ${escape(frame.function)}</th></tr>${valueRows(locals)}` : '')
      + (globals.length ? `<tr><th colspan="2" class="text-muted small">${debug.hasBlocks ? 'Your variables' : 'Globals'}</th></tr>${valueRows(globals)}` : '')
      || '<tr><td class="text-muted small">No variables here.</td></tr>');
    // Call stack
    $('#dbgCallStack').html(stack.map((item, index) => `<li><button type="button" class="btn btn-link btn-sm p-0 dbg-frame ${index === selectedFrame ? 'fw-bold' : ''}"
        data-index="${index}" aria-current="${index === selectedFrame}">${escape(item.function)}</button>
        <span class="small text-muted">${item.line ? `${escape(item.file)}:${item.line}` : hex(item.pc)}${item.guessed ? ' (from ra)' : ''}</span></li>`).join('')
      || '<li class="text-muted small">Not inside the program.</li>');
    // Watches
    $('#dbgWatches').html(watches.map((text, index) => {
      const value = debug.watch(text, frame, memory);
      return `<li class="d-flex gap-2 align-items-center"><code>${escape(text)}</code> = <span class="${value.error ? 'text-muted' : ''}">${escape(value.text)}</span>
        <button type="button" class="btn-close kit-tiny-close dbg-unwatch" data-index="${index}" aria-label="Stop watching ${escape(text)}"></button></li>`;
    }).join('') || '<li class="text-muted small">Type a name and press Watch.</li>');
    // CSR and stack (advanced)
    $('#dbgCsr').html(PRG32SourceDebug.csrRows(state).map(row => `<tr><th scope="row">${row.name} <span class="text-muted small">${row.number}</span></th>
      <td>${row.value.toLocaleString()}</td><td class="small text-muted">${escape(row.meaning)}</td></tr>`).join(''));
    $('#dbgStackWords').html(PRG32SourceDebug.stackRows(state, memory, 16).map(row => `<tr class="${row.isSp ? 'dbg-current' : ''}">
      <td>${row.isSp ? 'sp →' : (row.offset > 0 ? `sp+${row.offset}` : `sp${row.offset}`)}</td><td>${hex(row.address).slice(2)}</td>
      <td>${hex(row.value)}</td><td class="text-muted">${row.value | 0}</td></tr>`).join(''));
    // Breakpoint list with conditions
    const items = [...[...lineBreakpoints].map(([line, item]) => ({ kind: 'line', key: line, label: `Line ${line}`, ...item })),
      ...[...blockBreakpoints].map(([block, item]) => ({ kind: 'block', key: block, label: `Block ${describeBlock(block)}`, ...item }))];
    $('#dbgSourceBreakpoints').html(items.map(item => `<li class="d-flex flex-wrap gap-1 align-items-center">
        <span class="text-danger">●</span> ${escape(item.label)}
        <label class="visually-hidden" for="cond-${item.kind}-${escape(item.key)}">Condition for ${escape(item.label)}</label>
        <input class="form-control form-control-sm w-auto font-monospace dbg-condition" id="cond-${item.kind}-${escape(item.key)}"
          data-kind="${item.kind}" data-key="${escape(item.key)}" value="${escape(item.condition)}" placeholder="stop only if… (score > 10)">
        <button type="button" class="btn btn-link btn-sm p-0 dbg-src-remove" data-kind="${item.kind}" data-key="${escape(item.key)}">remove</button></li>`).join('')
      || '<li class="text-muted small">No source or block breakpoints.</li>');
  }

  function render(state) {
    if (!debug || !debug.ok || !state.loaded) return;
    if (!state.enabled || state.running) return;  // values change too fast while running: shown when paused
    if (lastPc !== state.pc) selectedFrame = 0;
    lastPc = state.pc;
    renderPanels(state);
  }

  // --- attach -------------------------------------------------------------------------
  function attach(answer) {
    info = answer;
    debug = answer ? PRG32SourceDebug.create({ debugMap: answer.debug_map, sourceMap: answer.source_map,
      guestBase: player.debugState().guest_base }) : null;
    if (!debug || !debug.ok) {
      $('#srcDebug').attr('hidden', true);
      $('#srcDebugNote').removeAttr('hidden').text('Source and block debugging: '
        + (debug ? debug.reason : 'open a cartridge compiled in the kit (Compile, then Run & debug)') + '. The machine-code debugger above works for every cartridge.');
      player.breakpointFilter = null;
      return;
    }
    $('#srcDebugNote').attr('hidden', true);
    $('#srcDebug').removeAttr('hidden');
    $('#dbgSourceTitle').text(info.source ? info.source.file : 'source');
    $('#dbgStepLine .dbg-beginner').text(debug.hasBlocks && info.blocks_json ? 'Next block' : 'Next line');
    renderSourceText();
    if (debug.hasBlocks && info.blocks_json) {
      $('#tabBlocks').removeAttr('hidden');
      openBlocks();
    } else {
      $('#tabBlocks').attr('hidden', true);
      bootstrap.Tab.getOrCreateInstance(document.getElementById('tabSource')).show();
    }
    player.breakpointFilter = breakpointFilter;
    restore();
    render(player.debugState());
  }

  // --- wiring -------------------------------------------------------------------------
  $('#dbgSource').on('click', '.dbg-src-gutter', function () {
    const line = Number($(this).data('line'));
    setLineBreakpoint(line, !lineBreakpoints.has(line));
  });
  $('#dbgBlockChoose').on('change', function () {
    const block = workspace && this.value && workspace.getBlockById(this.value);
    if (block) {
      Blockly.common.setSelected(block);
      workspace.centerOnBlock(block.id);
    }
  });
  $('#dbgBlockBreak').on('click', () => {
    const block = $('#dbgBlockSelected').data('block');
    if (block) setBlockBreakpoint(block, !blockBreakpoints.has(block));
    $('#dbgBlockSelected').text(describeBlock(block));
  });
  $('#dbgSourceBreakpoints').on('change', '.dbg-condition', function () {
    const kind = $(this).data('kind');
    const key = kind === 'line' ? Number($(this).data('key')) : String($(this).data('key'));
    const item = (kind === 'line' ? lineBreakpoints : blockBreakpoints).get(key);
    if (item) item.condition = this.value.trim();
    remember();
  }).on('click', '.dbg-src-remove', function () {
    const kind = $(this).data('kind');
    if (kind === 'line') setLineBreakpoint(Number($(this).data('key')), false);
    else setBlockBreakpoint(String($(this).data('key')), false);
  });
  $('#dbgCallStack').on('click', '.dbg-frame', function () {
    selectedFrame = Number($(this).data('index'));
    renderPanels(player.debugState());
  });
  $('#dbgWatchForm').on('submit', event => {
    event.preventDefault();
    const text = $('#dbgWatchInput').val().trim();
    if (!text) return;
    if (!watches.includes(text)) watches.push(text);
    $('#dbgWatchInput').val('');
    remember();
    render(player.debugState());
  });
  $('#dbgWatches').on('click', '.dbg-unwatch', function () {
    watches.splice(Number($(this).data('index')), 1);
    remember();
    render(player.debugState());
  });
  $('#dbgStepLine').on('click', () => {
    if (!debug || !debug.ok) return;
    const start = player.debugState().pc;
    const startLine = debug.lineAt(start);
    const startBlock = debug.blockAt(start);
    const key = pc => {
      if (debug.hasBlocks && workspace) { const entry = debug.blockAt(pc); return entry ? entry.block : null; }
      const line = debug.lineAt(pc);
      return line && line.file === debug.userFile ? line.line : null;
    };
    const from = debug.hasBlocks && workspace ? (startBlock && startBlock.block) : (startLine && startLine.line);
    const answer = player.debug({ command: 'step_line', moved: pc => { const now = key(pc); return now !== null && now !== from; } });
    if (!answer.ok) Kit.toast(answer.error, 'warning');
  });
  $('#tabBlocks').on('shown.bs.tab', () => workspace && Blockly.svgResize(workspace));
  $('input[name="dbgView"]').on('change', () => render(player.debugState()));

  window.PRG32SourceDebugger = { attach, update: render, get session() { return debug; },
    get workspace() { return workspace; }, get activeBlock() { return activeBlock; } };
})();
