// The Cartridge Player: open a .prg32 file (or a compiled artifact) and run it. Used by the
// Player page and by the IDE's simulator pane (the same element ids); the IDE loads the
// cartridges it builds through window.PRG32PlayerPage.open.
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
      .html(status.running ? '<i class="bi bi-pause-fill"></i> ' + Kit.escape(tr('js.offline_player.pause', 'Pause')) : '<i class="bi bi-play-fill"></i> ' + Kit.escape(tr('common.play', 'Play')));
    if (status.error) {
      $('#playerStatus').html(`<span class="text-danger"><i class="bi bi-exclamation-triangle"></i> ${Kit.escape(status.error)}</span>`);
      return;
    }
    if (!status.loaded) return;
    const seconds = ms => (ms / 1000).toFixed(1) + ' s';
    $('#playerStatus').html(`<span>${tr('js.player.frame_n', 'Frame {frame}', { frame: `<strong>${status.frames}</strong>` })}</span>
      <span title="${Kit.escape(tr('js.player.game_time_title', 'Time the cartridge sees: 33 ms per frame'))}">${Kit.escape(tr('js.prg32_debugger.game_time', 'Game time {time}', { time: seconds(status.guestMs) }))}</span>
      <span title="${Kit.escape(tr('js.player.real_time_title', 'Real time spent playing'))}">${Kit.escape(tr('js.prg32_debugger.real_time', 'Real time {time}', { time: seconds(status.wallMs) }))}</span>
      <span title="${Kit.escape(tr('js.player.instructions_title', 'RISC-V instructions executed so far'))}">${Kit.escape(tr('js.player.instructions', '{count} instructions', { count: Number(status.retired).toLocaleString(PRG32I18n.locale) }))}</span>
      <span>${Kit.escape(tr('js.player.speed', 'Speed {speed}×', { speed: status.speed }))}</span>
      ${status.legacySoundCalls ? `<span class="text-warning" title="${Kit.escape(tr('js.player.legacy_sound_title', 'PRG32 games now use the eight-voice audio engine'))}">
        ${Kit.escape(tr('js.player.legacy_sound_calls', 'Old sound calls ({count}): no longer supported, so they are silent', { count: status.legacySoundCalls }))}</span>` : ''}`);
  }

  // options.quiet: no "loaded" toast, and a failure is passed on to the caller (the IDE says it itself).
  function open(bytes, label, options = {}) {
    return player.load(bytes)
      .then(info => {
        $('#cartridgeName').text(info.name || label);
        if (window.PRG32Debugger) window.PRG32Debugger.loaded();
        if (!options.quiet) Kit.toast(tr('js.player.cartridge_loaded_press_play', 'Cartridge loaded. Press Play.'), 'success');
        return info;
      })
      .catch(err => {
        if (options.quiet) throw err;
        Kit.toast(tr('js.player.this_is_not_a_cartridge_the', 'This is not a cartridge the PRG32 core can run: {message}', { message: err.message }), 'danger');
      });
  }
  window.PRG32PlayerPage = { open, player };

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
        if (!response.ok) throw new Error(tr('js.player.could_not_download_artifact', 'could not download artifact {artifact}', { artifact: artifact }));
        return response.arrayBuffer();
      })
      .then(bytes => open(bytes, artifact))
      // Source and block debugging (ADR-0015): the maps the kit saved with this cartridge.
      .then(() => Kit.api('/api/artifacts/' + encodeURIComponent(artifact) + '/debug'))
      .then(answer => window.PRG32SourceDebugger && window.PRG32SourceDebugger.attach(answer))
      .catch(err => Kit.toast(err.message, 'danger'));
  }
})();
