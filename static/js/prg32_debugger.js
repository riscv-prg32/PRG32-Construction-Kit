// The debugger panel of the Cartridge Player page (docs/tutorials/debugger.md).
//
// Everything goes through player.debug({command: ...}) and player.debugState(), the
// same commands and state as PRG32-QT's /api/debug (ADR-0006). The Beginner and
// Advanced views are two ways of showing that one state: switching view changes
// nothing in the running cartridge, and both share the same breakpoints.
(function () {
  'use strict';

  const player = window.prg32Player;
  if (!player) return;

  // RISC-V ABI names of x0..x31, as in PRG32-QT's register window.
  const NAMES = ['zero', 'ra', 'sp', 'gp', 'tp', 't0', 't1', 't2', 's0', 's1', 'a0', 'a1', 'a2', 'a3', 'a4', 'a5',
    'a6', 'a7', 's2', 's3', 's4', 's5', 's6', 's7', 's8', 's9', 's10', 's11', 't3', 't4', 't5', 't6'];
  // The registers a beginner meets first, with what they are used for.
  const BEGINNER = [
    [10, 'a0: first argument, and the value a function gives back'],
    [11, 'a1: second argument'],
    [12, 'a2: third argument'],
    [13, 'a3: fourth argument'],
    [1, 'ra: return address, where a function goes back to'],
    [2, 'sp: stack pointer, top of the memory a function borrows'],
    [5, 't0: temporary'],
    [6, 't1: temporary'],
    [8, 's0: saved register (often the frame pointer)']
  ];
  const ROWS = 24;          // disassembly rows shown
  const FOLLOW_ROWS = 18;   // if the PC goes past this row, the listing moves
  const REFRESH_MS = 100;   // redraw at most 10 times a second while running

  let view = 'pc';          // init | update | draw | pc | address
  let anchor = null;        // first address of the listing
  let previous = null;      // registers last shown, to highlight what changed
  let memoryAddress = null; // what the memory view shows (null: the PC, once a cartridge is loaded)
  let lastDraw = 0;
  let pending = null;

  const hex = value => '0x' + (value >>> 0).toString(16).padStart(8, '0');
  const signed = value => value | 0;
  const escape = text => (window.Kit && Kit.escape ? Kit.escape(text) : String(text).replace(/[&<>"']/g, c => `&#${c.charCodeAt(0)};`));

  function storedMode() {
    try { return localStorage.getItem('prg32-kit-debugger-view') || 'beginner'; } catch (_) { return 'beginner'; }
  }

  function setMode(mode) {
    $('body').toggleClass('dbg-mode-beginner', mode !== 'advanced').toggleClass('dbg-mode-advanced', mode === 'advanced');
    $(mode === 'advanced' ? '#dbgAdvanced' : '#dbgBeginner').prop('checked', true);
    try { localStorage.setItem('prg32-kit-debugger-view', mode); } catch (_) { /* private window */ }
    previous = null;
    render(player.debugState());
  }

  function run(request) {
    const answer = player.debug(request);
    if (!answer.ok) Kit.toast(answer.error, 'warning');
    return answer;
  }

  // Find a start address a few instructions before `pc` that decodes exactly onto it
  // (RISC-V instructions are 2 or 4 bytes, so we cannot simply count backwards).
  function anchorBefore(pc) {
    for (let back = 12; back > 0; back -= 2) {
      const rows = player.disassemble(pc - back, 8);
      if (rows.some(row => row.address === pc)) return pc - back;
    }
    return pc;
  }

  function listing(state) {
    if (view !== 'pc' && view !== 'address') anchor = state.entries[view];
    if (anchor === null) anchor = anchorBefore(state.pc);
    let rows = player.disassemble(anchor, ROWS);
    const at = rows.findIndex(row => row.address === state.pc);
    if (view === 'pc' && (at < 0 || at > FOLLOW_ROWS)) {
      anchor = anchorBefore(state.pc);
      rows = player.disassemble(anchor, ROWS);
    }
    return rows;
  }

  function renderCode(state) {
    const rows = listing(state);
    if (!rows.length) {
      $('#dbgCode').html('<div class="p-2 small text-muted">Address outside guest memory</div>');
      return;
    }
    const breakpoints = new Set(state.breakpoints);
    const advanced = $('body').hasClass('dbg-mode-advanced');
    const html = rows.map(row => {
      const current = row.address === state.pc;
      const breakpoint = breakpoints.has(row.address);
      const space = row.text.indexOf(' ');
      const operation = space < 0 ? row.text : row.text.slice(0, space);
      const operands = space < 0 ? '' : row.text.slice(space);
      const word = row.width === 2 ? (row.word & 0xffff).toString(16).padStart(4, '0') : (row.word >>> 0).toString(16).padStart(8, '0');
      return `<tr class="${current ? 'dbg-current' : ''} ${breakpoint ? 'dbg-bp' : ''}" data-address="${row.address}">
        <td class="dbg-gutter" title="${breakpoint ? 'Remove breakpoint' : 'Add breakpoint'}" role="button" aria-label="Breakpoint at ${hex(row.address)}">${current ? '▶' : (breakpoint ? '●' : '')}</td>
        <td>${hex(row.address).slice(2)}</td>${advanced ? `<td class="text-muted">${word}</td>` : ''}
        <td><span class="dbg-op">${escape(operation)}</span>${escape(operands)}</td></tr>`;
    }).join('');
    $('#dbgCode').html(`<table class="table table-sm mb-0 font-monospace"><tbody>${html}</tbody></table>`);
    const current = $('#dbgCode .dbg-current')[0];
    if (current && view === 'pc') current.scrollIntoView({ block: 'nearest' });
  }

  function registerCell(index, value, changed) {
    return `<td class="${changed ? 'dbg-changed' : ''}" title="${NAMES[index]} = ${signed(value)} (decimal)">${hex(value)}</td>`;
  }

  function renderRegisters(state) {
    const registers = state.registers;
    const changed = index => previous && previous[index] !== registers[index];
    let html = `<tr><th>pc</th><td colspan="3">${hex(state.pc)}</td></tr>`;
    if ($('body').hasClass('dbg-mode-advanced')) {
      for (let index = 0; index < 32; index += 2) {
        html += '<tr>' + [index, index + 1].map(reg =>
          `<th title="x${reg}">${NAMES[reg]}</th>${registerCell(reg, registers[reg], changed(reg))}`).join('') + '</tr>';
      }
    } else {
      for (const [reg, meaning] of BEGINNER) {
        html += `<tr title="${escape(meaning)}"><th>${NAMES[reg]}</th>
          <td class="${changed(reg) ? 'dbg-changed' : ''}" colspan="3">${signed(registers[reg])}</td></tr>`;
      }
    }
    $('#dbgRegisters').html(html);
    previous = registers.slice();
  }

  function renderMemory() {
    if (!$('body').hasClass('dbg-mode-advanced') || memoryAddress === null) return;
    const length = Number($('#dbgMemoryLength').val());
    const bytes = player.readMemory(memoryAddress, length);
    if (!bytes) {
      $('#dbgMemory').text('Address outside guest memory');
      return;
    }
    const lines = [];
    for (let at = 0; at < bytes.length; at += 16) {
      const chunk = Array.from(bytes.slice(at, at + 16));
      const ascii = chunk.map(byte => (byte >= 32 && byte < 127 ? String.fromCharCode(byte) : '.')).join('');
      lines.push(`${hex(memoryAddress + at).slice(2)}  ${chunk.map(byte => byte.toString(16).padStart(2, '0')).join(' ').padEnd(47)}  |${ascii}|`);
    }
    $('#dbgMemory').text(lines.join('\n'));
  }

  function renderBreakpoints(state) {
    const badges = state.breakpoints.map(address => `<span class="badge text-bg-danger">● ${hex(address)}
      <button class="btn-close btn-close-white ms-1 dbg-remove kit-tiny-close" data-address="${address}" aria-label="Remove breakpoint ${hex(address)}"></button></span>`);
    $('#dbgBreakpoints').html(state.breakpoints.length
      ? `<span class="text-muted">Breakpoints:</span> ${badges.join(' ')} <button class="btn btn-link btn-sm p-0 ms-1" id="dbgClear">clear all</button>`
      : '<span class="text-muted">No breakpoints.</span>');
  }

  const REASONS = {
    breakpoint: 'Stopped at a breakpoint', pause: 'Paused', step: 'Stepped one instruction',
    step_over: 'Stepped over a call', step_out: 'Stepped out of a function', step_frame: 'Ran to the end of the frame',
    budget: 'Stopped after 20 million instructions without returning', error: 'The cartridge stopped with an error'
  };

  function renderStatus(state) {
    const where = { idle: 'between frames', update: 'in update()', draw: 'in draw()' }[state.phase] || state.phase;
    const seconds = ms => (ms / 1000).toFixed(2) + ' s';
    const parts = [
      `<span><strong>${state.running ? 'Running' : (REASONS[state.reason] || 'Paused')}</strong>${state.reason === 'breakpoint' ? ' at ' + hex(state.last_breakpoint) : ''}</span>`,
      `<span>${where}</span>`,
      `<span title="Time the cartridge sees (PRG32 virtual clock)">Game time ${seconds(state.guest_ns / 1e6)}</span>`,
      `<span title="Real time spent running">Real time ${seconds(state.wall_ms)}</span>`,
      `<span>Frame ${state.frames}</span>`,
      `<span class="dbg-advanced">${Number(state.retired).toLocaleString()} instructions · ${Number(state.cycles).toLocaleString()} cycles · ${state.breakpoint_hits} breakpoint hits</span>`
    ];
    if (state.error) parts.push(`<span class="text-danger">${escape(state.error)}</span>`);
    $('#dbgStatus').html(parts.join(''));
  }

  function render(state) {
    const on = Boolean(state.loaded && state.enabled);
    $('#dbgEnable').prop('disabled', !state.loaded).prop('checked', Boolean(state.enabled));
    $('.dbg-control').prop('disabled', !on);
    $('#dbgContinue').toggleClass('btn-danger', Boolean(state.running)).toggleClass('btn-success', !state.running)
      .html(state.running ? '<i class="bi bi-pause-fill"></i> Pause' : '<i class="bi bi-play-fill"></i> Continue');
    $('#dbgStep, #dbgStepOver, #dbgStepOut').prop('disabled', !on);
    if (!state.loaded) return;
    if (!state.enabled) {
      $('#dbgStatus').html('Switch on <strong>Debug mode</strong> to pause the game on any instruction.');
      return;
    }
    renderStatus(state);
    renderCode(state);
    renderRegisters(state);
    renderBreakpoints(state);
    if (memoryAddress === null) {
      memoryAddress = state.memory_address; // like PRG32-QT: start at the PC
      $('#dbgMemoryAddress').val(hex(memoryAddress));
    }
    renderMemory();
  }

  // Called by the player after every command, and every animation frame while running.
  function update(state) {
    const now = performance.now();
    if (state.running && now - lastDraw < REFRESH_MS) {
      pending = state;
      return;
    }
    lastDraw = now;
    pending = null;
    render(state);
  }

  setInterval(() => { if (pending) update(pending); }, REFRESH_MS);

  function loaded() {
    view = 'pc';
    anchor = null;
    previous = null;
    memoryAddress = null;
    $('.dbg-goto').removeClass('active').filter('[data-view="pc"]').addClass('active');
    render(player.debugState());
  }

  // --- wiring -------------------------------------------------------------------
  $('#dbgEnable').on('change', function () {
    if (!this.checked && player.running) player.pause();
    run({ command: 'enable', enabled: this.checked });
  });
  $('input[name="dbgView"]').on('change', function () { setMode(this.value); });
  $('#dbgContinue').on('click', () => run({ command: player.running ? 'pause' : 'resume' }));
  $('#dbgStep').on('click', () => { view = 'pc'; run({ command: 'step' }); });
  $('#dbgStepOver').on('click', () => { view = 'pc'; run({ command: 'step_over' }); });
  $('#dbgStepOut').on('click', () => { view = 'pc'; run({ command: 'step_out' }); });
  $('#dbgStepFrame').on('click', () => { view = 'pc'; run({ command: 'step_frame' }); });
  $('.dbg-goto').on('click', function () {
    view = $(this).data('view');
    anchor = null;
    $('.dbg-goto').removeClass('active');
    $(this).addClass('active');
    render(player.debugState());
  });
  $('#dbgGotoForm').on('submit', event => {
    event.preventDefault();
    const address = PRG32CartridgePlayer.parseAddress($('#dbgGotoAddress').val());
    if (address === null) return Kit.toast('Type an address like 0x40800000 or 1082130432.', 'warning');
    view = 'address';
    anchor = address;
    $('.dbg-goto').removeClass('active');
    render(player.debugState());
  });
  $('#dbgCode').on('click', '.dbg-gutter', function () {
    const address = Number($(this).closest('tr').data('address'));
    const set = player.debugState().breakpoints.includes(address);
    run({ command: 'breakpoint', address, enabled: !set });
  });
  $('#dbgBreakpoints').on('click', '.dbg-remove', function () {
    run({ command: 'breakpoint', address: Number($(this).data('address')), enabled: false });
  }).on('click', '#dbgClear', () => run({ command: 'clear_breakpoints' }));
  $('#dbgMemoryForm').on('submit', event => {
    event.preventDefault();
    const address = PRG32CartridgePlayer.parseAddress($('#dbgMemoryAddress').val());
    if (address === null) {
      $('#dbgMemory').text('Invalid address');
      return;
    }
    memoryAddress = address;
    renderMemory();
  });
  $('#dbgMemoryLength').on('change', renderMemory);

  window.PRG32Debugger = { update, loaded, render: () => render(player.debugState()) };
  setMode(storedMode());
})();
