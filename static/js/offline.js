// The offline page (static/offline.html): a Blocks scratchpad kept in this browser only.
// Nothing here talks to the server; when it is back, "Try again" reloads the real page.
(function () {
  const STORAGE_KEY = 'prg32-offline-scratchpad';
  PRG32Blocks.init('blocklyDiv');
  const simulator = new PRG32Simulator.Simulator(document.getElementById('gameCanvas'), document.getElementById('debugState'));

  function stored() {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null'); } catch (err) { return null; }
  }
  const saved = stored();
  if (saved) PRG32Blocks.load(saved);

  function remember() {
    const blocks = PRG32Blocks.save();
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(blocks)); } catch (err) { /* private window: not kept */ }
    simulator.loadBlocks(blocks);
  }
  PRG32Blocks.getWorkspace().addChangeListener(event => { if (!event.isUiEvent) remember(); });
  remember();

  $('#offlinePlay').on('click', function () {
    const running = simulator.toggle();
    $(this).html(running ? '<i class="bi bi-pause-fill"></i> Pause' : '<i class="bi bi-play-fill"></i> Play');
  });
  $('#offlineStep').on('click', () => simulator.step());
  $('#offlineExport').on('click', () => {
    const blob = new Blob([JSON.stringify({ abi: 'prg32-construction-kit-project-1.0',
      project: { title: 'Offline sketch', blocks_json: PRG32Blocks.save() } }, null, 2)], { type: 'application/json' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'offline-sketch.json';  // Import project on the dashboard reads this file
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  });
  $('#offlineImport').on('change', function () {
    const file = this.files[0];
    if (!file) return;
    file.text().then(text => {
      const data = JSON.parse(text);
      PRG32Blocks.load((data.project || data).blocks_json || data);
      remember();
    }).catch(() => window.alert('This file is not a blocks project.'));
  });
  $('#retryOnline').on('click', () => window.location.reload());
})();
