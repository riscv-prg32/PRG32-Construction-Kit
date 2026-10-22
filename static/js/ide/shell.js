// The IDE shell (ADR-0013): regions, project tree, tabs, command palette and shortcuts.
// Nothing here knows about PRG32 projects; ide.js fills it in.
//
// Keyboard model (WAI-ARIA authoring practices):
// - F6 / Shift+F6 move focus between regions: toolbar, project tree, editor, tool window, simulator.
// - The splitters between the panes move with the mouse, or with the arrow keys when focused;
//   Alt+1 / Alt+4 / Alt+9 show or hide the files, the tool window and the simulator (as in
//   JetBrains IDEs). The sizes are remembered in this browser (prg32-kit-ide-layout).
// - Tree: Up/Down move, Right opens a folder (or moves into it), Left closes (or moves to the
//   parent), Home/End, Enter or Space opens the file. One item is in the Tab order at a time.
// - Tab lists: Left/Right move between tabs, Home/End, Delete closes an editor tab.
// - Ctrl+Shift+P or F1 opens the command palette: type, Up/Down, Enter, Escape.
window.IdeShell = (function () {
  'use strict';
  const commands = new Map();
  const shortcuts = [];

  // --- regions ---------------------------------------------------------------------
  const REGIONS = ['toolbar', 'tree', 'editor', 'panel', 'simulator'];

  function focusRegion(name) {
    if (name === 'tree') return focusTree();
    if (name === 'editor') {
      const active = $('#ideTabs [role=tab][aria-selected=true]');
      const panel = active.length ? $('#' + active.attr('aria-controls')) : $();
      const focusTarget = panel.find('[data-focus-target]').first();
      if (focusTarget.length && focusTarget.data('focus')) return focusTarget.data('focus')();
      return (active.length ? active : $('#ideEditorArea')).trigger('focus');
    }
    if (name === 'panel') return $('#idePanelTabs [role=tab][aria-selected=true]').trigger('focus');
    if (name === 'simulator') return $('#playerScreen').is(':visible') ? $('#playerScreen').trigger('focus') : $('#ideSim').trigger('focus');
    return $('.ide-toolbar').find('button, select, a').filter(':visible').first().trigger('focus');
  }

  function currentRegion() {
    const region = $(document.activeElement).closest('[data-region]').data('region');
    return REGIONS.includes(region) ? region : 'editor';
  }

  function cycleRegion(step) {
    const index = REGIONS.indexOf(currentRegion());
    let next = REGIONS[(index + step + REGIONS.length) % REGIONS.length];
    const hidden = region => (region === 'tree' && !$('#ideTree').is(':visible'))
      || (region === 'panel' && !$('#idePanel').is(':visible')) || (region === 'simulator' && !$('#ideSim').is(':visible'));
    for (let tries = 0; hidden(next) && tries < REGIONS.length; tries += 1) {
      next = REGIONS[(REGIONS.indexOf(next) + step + REGIONS.length) % REGIONS.length];
    }
    focusRegion(next);
  }

  // --- tree --------------------------------------------------------------------------
  // items: [{id, label, icon, children: [...]}] ; onOpen(id) when a file is opened.
  let treeOpen = () => {};

  function renderTree(items, onOpen) {
    treeOpen = onOpen;
    const html = (list, level) => list.map(item => {
      const folder = Array.isArray(item.children);
      return `<li role="treeitem" id="tree-${item.id}" data-id="${Kit.escape(item.id)}" aria-level="${level}"
        tabindex="-1" ${folder ? 'aria-expanded="true"' : ''} ${item.readonly ? 'data-readonly="1"' : ''}>
        <span class="ide-tree-label"><i class="bi ${item.icon || (folder ? 'bi-folder2-open' : 'bi-file-earmark')}" aria-hidden="true"></i>
        ${Kit.escape(item.label)}${item.readonly ? ' <span class="visually-hidden">(read-only)</span>' : ''}</span>
        ${folder ? `<ul role="group">${html(item.children, level + 1)}</ul>` : ''}</li>`;
    }).join('');
    $('#ideTreeList').html(html(items, 1));
    const first = $('#ideTreeList [role=treeitem]').first();
    first.attr('tabindex', '0');
  }

  function visibleItems() {
    return $('#ideTreeList [role=treeitem]').filter(function () {
      return !$(this).parents('[role=treeitem][aria-expanded=false]').length;
    });
  }

  function focusTreeItem(item) {
    if (!item || !item.length) return;
    $('#ideTreeList [role=treeitem]').attr('tabindex', '-1');
    item.attr('tabindex', '0').trigger('focus');
  }

  function focusTree() {
    const current = $('#ideTreeList [role=treeitem][tabindex=0]');
    focusTreeItem(current.length ? current : $('#ideTreeList [role=treeitem]').first());
  }

  $(document).on('keydown', '#ideTreeList [role=treeitem]', function (event) {
    const item = $(this);
    const items = visibleItems();
    const index = items.index(item);
    const folder = item.is('[aria-expanded]');
    let handled = true;
    switch (event.key) {
      case 'ArrowDown': focusTreeItem(items.eq(Math.min(index + 1, items.length - 1))); break;
      case 'ArrowUp': focusTreeItem(items.eq(Math.max(index - 1, 0))); break;
      case 'Home': focusTreeItem(items.first()); break;
      case 'End': focusTreeItem(items.last()); break;
      case 'ArrowRight':
        if (folder && item.attr('aria-expanded') === 'false') item.attr('aria-expanded', 'true');
        else if (folder) focusTreeItem(item.find('[role=treeitem]').first());
        break;
      case 'ArrowLeft':
        if (folder && item.attr('aria-expanded') === 'true') item.attr('aria-expanded', 'false');
        else focusTreeItem(item.parent().closest('[role=treeitem]'));
        break;
      case 'Enter': case ' ':
        if (folder) item.attr('aria-expanded', item.attr('aria-expanded') === 'true' ? 'false' : 'true');
        else treeOpen(item.data('id'));
        break;
      default: handled = false;
    }
    if (handled) { event.preventDefault(); event.stopPropagation(); }
  });

  $(document).on('click', '#ideTreeList .ide-tree-label', function (event) {
    const item = $(this).closest('[role=treeitem]');
    focusTreeItem(item);
    if (item.is('[aria-expanded]')) item.attr('aria-expanded', item.attr('aria-expanded') === 'true' ? 'false' : 'true');
    else treeOpen(item.data('id'));
    event.stopPropagation();
  });

  // --- editor tabs -----------------------------------------------------------------------
  // A tab: {id, title, closable, render(panelElement), onShow()}. Panels stay in the page when hidden.
  const tabs = new Map();

  function openTab(spec) {
    if (!tabs.has(spec.id)) {
      const tab = $(`<button role="tab" id="tab-${spec.id}" aria-controls="tabpanel-${spec.id}" aria-selected="false" tabindex="-1">
        <span>${Kit.escape(spec.title)}</span></button>`);
      if (spec.closable !== false) {
        tab.append(`<span class="ide-tab-close" data-close="${Kit.escape(spec.id)}" aria-hidden="true" title="Close (Delete)">&times;</span>`);
      }
      const panel = $(`<div role="tabpanel" id="tabpanel-${spec.id}" aria-labelledby="tab-${spec.id}" class="ide-tab-panel" hidden></div>`);
      $('#ideTabs').append(tab);
      $('#ideTabPanels').append(panel);
      tabs.set(spec.id, spec);
      spec.render(panel[0]);
    }
    activateTab(spec.id);
    return tabs.get(spec.id);
  }

  function activateTab(id) {
    $('#ideTabs [role=tab]').attr({ 'aria-selected': 'false', tabindex: '-1' });
    $('#ideTabPanels [role=tabpanel]').attr('hidden', true);
    $(`#tab-${id}`).attr({ 'aria-selected': 'true', tabindex: '0' });
    $(`#tabpanel-${id}`).removeAttr('hidden');
    const spec = tabs.get(id);
    if (spec && spec.onShow) spec.onShow();
    $(document).trigger('ide:tab', [id]);
  }

  function closeTab(id) {
    const spec = tabs.get(id);
    if (!spec || spec.closable === false) return;
    const tab = $(`#tab-${id}`);
    const neighbour = tab.next('[role=tab]').length ? tab.next('[role=tab]') : tab.prev('[role=tab]');
    if (spec.onClose) spec.onClose();
    tab.remove();
    $(`#tabpanel-${id}`).remove();
    tabs.delete(id);
    if (neighbour.length) { activateTab(neighbour.attr('id').slice(4)); neighbour.trigger('focus'); }
  }

  function activeTabId() {
    const tab = $('#ideTabs [role=tab][aria-selected=true]');
    return tab.length ? tab.attr('id').slice(4) : null;
  }

  function tablistKeys(list, onActivate) {
    $(document).on('keydown', list + ' [role=tab]', function (event) {
      const all = $(list + ' [role=tab]');
      const index = all.index(this);
      let next = null;
      if (event.key === 'ArrowRight') next = all.eq((index + 1) % all.length);
      else if (event.key === 'ArrowLeft') next = all.eq((index - 1 + all.length) % all.length);
      else if (event.key === 'Home') next = all.first();
      else if (event.key === 'End') next = all.last();
      else if (event.key === 'Delete' && list === '#ideTabs') { closeTab(this.id.slice(4)); event.preventDefault(); return; }
      if (next) { event.preventDefault(); onActivate(next); next.trigger('focus'); }
    });
    $(document).on('click', list + ' [role=tab]', function () { onActivate($(this)); });
  }
  tablistKeys('#ideTabs', tab => activateTab(tab.attr('id').slice(4)));
  tablistKeys('#idePanelTabs', tab => showPanel(tab.attr('aria-controls').slice(6)));
  $(document).on('click', '.ide-tab-close', function (event) { closeTab($(this).data('close')); event.stopPropagation(); });

  function showPanel(name) {
    $('#idePanelTabs [role=tab]').attr({ 'aria-selected': 'false', tabindex: '-1' });
    $('.ide-panel > [role=tabpanel]').attr('hidden', true);   // not the debugger's own tab panes
    $(`#panelTab-${name}`).attr({ 'aria-selected': 'true', tabindex: '0' });
    $(`#panel-${name}`).removeAttr('hidden');
    if ($('#ide').attr('data-panel') === 'closed') showPane('panel', true);   // asked for: show the tool window
  }

  // --- command palette ---------------------------------------------------------------------
  // command: {id, title, keys (shown), run()}
  function addCommand(command) { commands.set(command.id, command); }

  let paletteReturnFocus = null;
  let paletteModal = null;
  function renderPalette(filter) {
    const words = filter.toLowerCase().split(/\s+/).filter(Boolean);
    const matches = Array.from(commands.values()).filter(command => words.every(word => command.title.toLowerCase().includes(word)));
    $('#paletteList').html(matches.map((command, index) => `<li role="option" class="list-group-item d-flex justify-content-between"
        id="cmd-${command.id}" data-command="${command.id}" aria-selected="${index === 0}">
        <span>${Kit.escape(command.title)}</span>${command.keys ? `<kbd>${Kit.escape(command.keys)}</kbd>` : ''}</li>`).join('')
      || '<li class="list-group-item text-muted">No matching command.</li>');
    $('#paletteInput').attr('aria-activedescendant', matches.length ? `cmd-${matches[0].id}` : '');
  }
  function movePalette(step) {
    const options = $('#paletteList [role=option]');
    if (!options.length) return;
    const index = options.index(options.filter('[aria-selected=true]'));
    const next = options.eq((index + step + options.length) % options.length);
    options.attr('aria-selected', 'false');
    next.attr('aria-selected', 'true');
    next[0].scrollIntoView({ block: 'nearest' });
    $('#paletteInput').attr('aria-activedescendant', next.attr('id'));
  }
  function openPalette() {
    paletteReturnFocus = document.activeElement;
    paletteModal = paletteModal || bootstrap.Modal.getOrCreateInstance(document.getElementById('ideCommandPalette'));
    $('#paletteInput').val('');
    renderPalette('');
    paletteModal.show();
  }
  function runCommand(id) {
    const command = commands.get(id);
    // Run after the dialog has closed so the command can move focus where it needs. The handler
    // is attached first: without an animation Bootstrap reports "hidden" inside hide() itself.
    $('#ideCommandPalette').one('hidden.bs.modal', () => command && command.run());
    paletteModal.hide();
  }
  $('#ideCommandPalette').on('shown.bs.modal', () => $('#paletteInput').trigger('focus'));
  $('#ideCommandPalette').on('hidden.bs.modal', () => { if (paletteReturnFocus && document.body.contains(paletteReturnFocus)) paletteReturnFocus.focus(); });
  $('#paletteInput').on('input', function () { renderPalette(this.value); });
  $('#paletteInput').on('keydown', function (event) {
    if (event.key === 'ArrowDown') { movePalette(1); event.preventDefault(); }
    else if (event.key === 'ArrowUp') { movePalette(-1); event.preventDefault(); }
    else if (event.key === 'Enter') {
      const chosen = $('#paletteList [role=option][aria-selected=true]');
      if (chosen.length) { paletteReturnFocus = null; runCommand(chosen.data('command')); }
      event.preventDefault();
    }
  });
  $('#paletteList').on('click', '[role=option]', function () { paletteReturnFocus = null; runCommand($(this).data('command')); });

  // --- shortcuts ---------------------------------------------------------------------------------
  // {key, ctrl, shift, alt, run}; "ctrl" means Ctrl, or Cmd on a Mac.
  function addShortcut(shortcut) { shortcuts.push(shortcut); }
  // Capture phase: shortcuts work even while Monaco or Blockly has the focus.
  document.addEventListener('keydown', event => {
    if ($('#ideCommandPalette').hasClass('show')) return;
    const ctrl = event.ctrlKey || event.metaKey;
    for (const shortcut of shortcuts) {
      // event.code also matches, because Alt+0 on a Mac types a symbol instead of "0".
      const key = shortcut.key.toLowerCase();
      const sameKey = event.key.toLowerCase() === key || event.code === 'Digit' + key || event.code === 'Key' + key.toUpperCase();
      if (sameKey && !!shortcut.ctrl === ctrl
          && !!shortcut.shift === event.shiftKey && !!shortcut.alt === event.altKey) {
        event.preventDefault();
        event.stopPropagation();
        shortcut.run();
        return;
      }
    }
  }, true);
  addShortcut({ key: 'F6', run: () => cycleRegion(1) });
  addShortcut({ key: 'F6', shift: true, run: () => cycleRegion(-1) });
  addShortcut({ key: 'p', ctrl: true, shift: true, run: openPalette });
  addShortcut({ key: 'F1', run: openPalette });
  $('#idePalette').on('click', openPalette);

  // --- small screens: the tree slides in over the editor --------------------------------------
  function toggleTree(open) {
    const show = open === undefined ? !$('#ide').hasClass('ide-tree-open') : open;
    $('#ide').toggleClass('ide-tree-open', show);
    $('#ideTreeToggle').attr('aria-expanded', String(show));
    if (show) focusTree();
  }
  $('#ideTreeToggle').on('click', () => toggleTree());
  addShortcut({ key: '0', alt: true, run: () => toggleTree() });

  // --- panes: splitters and show/hide (JetBrains-style layout) ---------------------------------
  const LAYOUT_KEY = 'prg32-kit-ide-layout';
  const SIZES = { tree: ['--ide-tree-w', 120, 480], sim: ['--ide-sim-w', 240, 900], panel: ['--ide-panel-h', 80, 700] };
  let layout = {};
  try { layout = JSON.parse(localStorage.getItem(LAYOUT_KEY) || '{}') || {}; } catch (_) { layout = {}; }

  function rememberLayout() {
    try { localStorage.setItem(LAYOUT_KEY, JSON.stringify(layout)); } catch (_) { /* private window */ }
  }

  function setSize(pane, pixels) {
    const [variable, min, max] = SIZES[pane];
    const size = Math.round(Math.max(min, Math.min(max, pixels)));
    document.getElementById('ide').style.setProperty(variable, size + 'px');
    $(`.ide-splitter[data-split=${pane}]`).attr({ 'aria-valuenow': size, 'aria-valuemin': min, 'aria-valuemax': max });
    layout[pane] = size;
    $(window).trigger('resize');   // Monaco and Blockly measure themselves again
  }

  function showPane(pane, show) {
    const ide = $('#ide');
    const open = show === undefined ? ide.attr('data-' + pane) === 'closed' : show;
    ide.attr('data-' + pane, open ? 'open' : 'closed');
    $(`.ide-pane-toggle[data-pane=${pane}]`).attr('aria-pressed', String(open));
    layout['hide_' + pane] = !open;
    rememberLayout();
    $(window).trigger('resize');
    return open;
  }

  function currentSize(pane) {
    if (pane === 'panel') return $('#idePanel').outerHeight();
    return pane === 'tree' ? $('#ideTree').outerWidth() : $('#ideSim').outerWidth();
  }

  $('.ide-splitter').each(function () {
    const pane = $(this).data('split');
    $(this).on('pointerdown', event => {
      event.preventDefault();
      const splitter = $(this).addClass('is-dragging');
      const start = { x: event.clientX, y: event.clientY, size: currentSize(pane) };
      const move = moved => {
        const delta = pane === 'panel' ? start.y - moved.clientY : pane === 'tree' ? moved.clientX - start.x : start.x - moved.clientX;
        setSize(pane, start.size + delta);
      };
      const stop = () => {
        splitter.removeClass('is-dragging');
        window.removeEventListener('pointermove', move);
        window.removeEventListener('pointerup', stop);
        rememberLayout();
      };
      window.addEventListener('pointermove', move);
      window.addEventListener('pointerup', stop);
    }).on('keydown', event => {
      const grow = { tree: ['ArrowRight', 'ArrowLeft'], sim: ['ArrowLeft', 'ArrowRight'], panel: ['ArrowUp', 'ArrowDown'] }[pane];
      const step = event.shiftKey ? 80 : 20;
      if (event.key === grow[0]) setSize(pane, currentSize(pane) + step);
      else if (event.key === grow[1]) setSize(pane, currentSize(pane) - step);
      else return;
      event.preventDefault();
      rememberLayout();
    });
  });
  $('.ide-pane-toggle').on('click', function () { showPane($(this).data('pane')); });
  for (const pane of Object.keys(SIZES)) {
    if (layout[pane]) setSize(pane, layout[pane]);
    else {   // a focusable splitter says how big its pane is (ARIA "separator")
      const [, min, max] = SIZES[pane];
      $(`.ide-splitter[data-split=${pane}]`).attr({ 'aria-valuenow': Math.round(currentSize(pane) || min),
                                                    'aria-valuemin': min, 'aria-valuemax': max });
    }
    if (layout['hide_' + pane]) showPane(pane, false);
  }
  addShortcut({ key: '1', alt: true, run: () => showPane('tree') });
  addShortcut({ key: '4', alt: true, run: () => showPane('panel') });
  addShortcut({ key: '9', alt: true, run: () => showPane('sim') });

  return { renderTree, focusTree, openTab, activateTab, closeTab, activeTabId, showPanel, showPane, addCommand,
    addShortcut, openPalette, focusRegion, toggleTree, tabs };
})();
