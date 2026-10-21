// The Cartridge Player page: open a .prg32 file (or a compiled artifact) and run it.
(function () {
  const player = new PRG32CartridgePlayer(document.getElementById('playerScreen'), {
    onStatus: showStatus,
    onDebug: state => {
      if (window.PRG32Debugger) window.PRG32Debugger.update(state);
      if (window.PRG32SourceDebugger) window.PRG32SourceDebugger.update(state);
    }
  });
  window.prg32Player = player; // the debugger panel (prg32_debugger.js) drives the same player
  let muted = false;

  function showStatus(status) {
    $('#playPause, #stepFrame').prop('disabled', !status.loaded);
    $('#playPause').toggleClass('btn-danger', status.running).toggleClass('btn-success', !status.running)
      .html(status.running ? '<i class="bi bi-pause-fill"></i> Pause' : '<i class="bi bi-play-fill"></i> Play');
    if (status.error) {
      $('#playerStatus').html(`<span class="text-danger"><i class="bi bi-exclamation-triangle"></i> ${Kit.escape(status.error)}</span>`);
      return;
    }
    if (!status.loaded) return;
    const seconds = ms => (ms / 1000).toFixed(1) + ' s';
    $('#playerStatus').html(`<span>Frame <strong>${status.frames}</strong></span>
      <span title="Time the cartridge sees: 33 ms per frame">Game time ${seconds(status.guestMs)}</span>
      <span title="Real time spent playing">Real time ${seconds(status.wallMs)}</span>
      <span title="RISC-V instructions executed so far">${Number(status.retired).toLocaleString()} instructions</span>
      <span>Speed ${status.speed}×</span>
      ${status.legacySoundCalls ? `<span class="text-warning" title="PRG32 games now use the eight-voice audio engine">
        Old sound calls (${status.legacySoundCalls}): no longer supported, so they are silent</span>` : ''}`);
  }

  function open(bytes, label) {
    return player.load(bytes)
      .then(info => {
        $('#cartridgeName').text(info.name || label);
        if (window.PRG32Debugger) window.PRG32Debugger.loaded();
        Kit.toast('Cartridge loaded. Press Play.', 'success');
      })
      .catch(err => Kit.toast('This is not a cartridge the PRG32 core can run: ' + err.message, 'danger'));
  }

  $('#cartridgeFile').on('change', function () {
    const file = this.files[0];
    if (file) file.arrayBuffer().then(bytes => open(bytes, file.name))
      .then(() => window.PRG32SourceDebugger && window.PRG32SourceDebugger.attach(null));
  });
  $('#playPause').on('click', () => player.toggle());
  $('#stepFrame').on('click', () => player.step());
  $('#speed').on('change', function () { player.setSpeed(this.value); });
  $('#mute').on('click', function () {
    muted = !muted;
    player.audio.setMuted(muted);
    $(this).html(muted ? '<i class="bi bi-volume-mute"></i>' : '<i class="bi bi-volume-up"></i>');
  });
  $('#touchButtons').on('pointerdown', '.touch-button', function (event) {
    event.preventDefault();
    player.setButton($(this).data('button'), true);
  }).on('pointerup pointerleave pointercancel', '.touch-button', function () {
    player.setButton($(this).data('button'), false);
  });

  // /player?artifact=<id>: a cartridge compiled in the editor.
  const artifact = new URLSearchParams(window.location.search).get('artifact');
  if (artifact) {
    fetch('/api/artifacts/' + encodeURIComponent(artifact) + '/download', { headers: { 'X-PRG32-Kit': '1' } })
      .then(response => {
        if (!response.ok) throw new Error('could not download artifact ' + artifact);
        return response.arrayBuffer();
      })
      .then(bytes => open(bytes, artifact))
      // Source and block debugging (ADR-0015): the maps the kit saved with this cartridge.
      .then(() => Kit.api('/api/artifacts/' + encodeURIComponent(artifact) + '/debug'))
      .then(answer => window.PRG32SourceDebugger && window.PRG32SourceDebugger.attach(answer))
      .catch(err => Kit.toast(err.message, 'danger'));
  }
})();
