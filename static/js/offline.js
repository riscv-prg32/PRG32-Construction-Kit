// The offline and guest workspace (static/offline.html, ADR-0017): Blocks games kept in this
// browser's IndexedDB (guest_store.js). Nothing here talks to the server. With ?guest=1 it is
// the "Try without an account" page; otherwise the page shown when the server is unreachable.
(function () {
  'use strict';
  const guest = new URLSearchParams(window.location.search).get('guest') === '1';
  $('#guestNotice').prop('hidden', !guest);
  $('#offlineNotice').prop('hidden', guest);
  $('#offlineBadge').html(guest ? '<i class="bi bi-person"></i> Guest' : '<i class="bi bi-wifi-off"></i> Offline');

  PRG32Blocks.init('blocklyDiv');
  const simulator = new PRG32Simulator.Simulator(document.getElementById('gameCanvas'), document.getElementById('debugState'));
  const store = window.PRG32GuestStore;
  let current = null;
  let loading = false;
  let timer = null;

  function show(message, variant) {
    $('#guestSpace').text(message).toggleClass('text-danger', variant === 'danger');
  }

  function space() {
    return store.estimate().then(estimate => {
      if (!estimate || !estimate.quota) return show(tr('js.offline.kept_in_this_browser', 'Kept in this browser.'));
      const mb = bytes => (bytes / 1048576).toFixed(1);
      show(tr('js.offline.browser_space', 'This browser: {used} MB used of {quota} MB it allows.', { used: mb(estimate.usage), quota: mb(estimate.quota) }));
    });
  }

  function fill(rows) {
    $('#guestProjects').html(rows.map(row => `<option value="${row.id}"></option>`).join(''));
    $('#guestProjects option').each((index, option) => { option.textContent = rows[index].title; });
    if (current) $('#guestProjects').val(current.id);
  }

  function open(row) {
    current = row;
    loading = true;
    PRG32Blocks.load(row.blocks_json || {});
    loading = false;
    $('#guestTitle').val(row.title);
    $('#guestProjects').val(row.id);
    simulator.loadBlocks(PRG32Blocks.save());
  }

  function refresh() {
    return store.list().then(rows => {
      if (!rows.length) return store.save({ title: tr('js.offline.my_first_game', 'My first game'), blocks_json: {} }).then(row => { fill([row]); open(row); });
      fill(rows);
      if (!current || !rows.some(row => row.id === current.id)) open(rows[0]);
      return null;
    }).then(space);
  }

  // Save a moment after the last change; a full disk keeps the previous copy and says so.
  function flush() {
    clearTimeout(timer);
    timer = null;
    if (!current) return Promise.resolve();
    return store.save({ ...current, title: $('#guestTitle').val() || current.title, blocks_json: PRG32Blocks.save() })
      .then(row => { current = row; return store.list().then(fill); })
      .then(space)
      .catch(error => show(error.message, 'danger'));
  }

  function remember() {
    if (loading || !current) return;
    clearTimeout(timer);
    timer = setTimeout(flush, 400);
    simulator.loadBlocks(PRG32Blocks.save());
  }
  window.addEventListener('pagehide', () => { if (timer) flush(); });

  PRG32Blocks.getWorkspace().addChangeListener(event => { if (!event.isUiEvent) remember(); });
  $('#guestTitle').on('input', remember);
  $('#guestProjects').on('change', function () { store.get(this.value).then(row => row && open(row)); });
  $('#guestNew').on('click', () => store.save({ title: tr('js.offline.new_game', 'New game'), blocks_json: {} })
    .then(row => { current = row; return refresh().then(() => open(row)); }).catch(error => show(error.message, 'danger')));
  $('#guestDelete').on('click', () => {
    if (!current || !window.confirm(tr('js.offline.delete_game', 'Delete "{title}" from this browser? Save it as a file first if you want to keep it.', { title: current.title }))) return;
    store.remove(current.id).then(() => { current = null; return refresh(); });
  });
  $('#guestClear').on('click', () => {
    if (!window.confirm(tr('js.offline.delete_all_games_kept_in_this', 'Delete ALL games kept in this browser? This cannot be undone. Save the ones you want as files first.'))) return;
    store.clear().then(() => { current = null; return refresh(); });
  });

  $('#offlinePlay').on('click', function () {
    const running = simulator.toggle();
    $(this).html(running ? '<i class="bi bi-pause-fill"></i> Pause' : '<i class="bi bi-play-fill"></i> Play');
  });
  $('#offlineStep').on('click', () => simulator.step());
  $('#offlineExport').on('click', () => {
    const link = document.createElement('a');
    link.href = URL.createObjectURL(store.exportFile({ title: $('#guestTitle').val() || tr('js.offline.my_game', 'My game'), blocks_json: PRG32Blocks.save() }));
    link.download = (($('#guestTitle').val() || 'my-game').replace(/[^A-Za-z0-9_-]+/g, '-') || 'my-game') + '.json';
    link.click();  // the dashboard's Import project reads this file
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  });
  $('#offlineImport').on('change', function () {
    const file = this.files[0];
    if (!file) return;
    file.text().then(text => store.save(store.importText(text)))
      .then(row => { current = row; return refresh().then(() => open(row)); })
      .catch(error => window.alert(error.message || tr('js.offline.this_file_is_not_a_blocks', 'This file is not a blocks project.')));
  });
  $('#retryOnline').on('click', () => window.location.reload());

  store.persist();
  store.migrateScratchpad().then(refresh).catch(error => show(error.message, 'danger'));
  window.PRG32Guest = { get current() { return current; }, refresh, flush, get pending() { return Boolean(timer); } };
})();
