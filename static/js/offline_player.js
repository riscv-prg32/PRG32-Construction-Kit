// static/offline-player.html: run a local .prg32 with the cached PRG32 core, no server needed.
(function () {
  const status = document.getElementById('playerStatus');
  const button = document.getElementById('playPause');
  const player = new PRG32CartridgePlayer(document.getElementById('playerScreen'), {
    onStatus(state) {
      button.disabled = !state.loaded;
      button.textContent = state.running ? tr('js.offline_player.pause', 'Pause') : tr('common.play', 'Play');
      status.textContent = state.error ? state.error : state.loaded ? `Frame ${state.frames}` : tr('js.offline_player.no_cartridge_loaded', 'No cartridge loaded.');
    }
  });
  document.getElementById('cartridgeFile').addEventListener('change', event => {
    const file = event.target.files[0];
    if (file) file.arrayBuffer().then(bytes => player.load(bytes)).catch(err => { status.textContent = err.message; });
  });
  button.addEventListener('click', () => player.toggle());
})();
