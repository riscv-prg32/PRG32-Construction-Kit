// Backgrounds (_backgrounds.html, docs/backgrounds.md), an IDE tab for the open project like Sprite Lab
// and AudioStudio: PRG32 tiles (8x8 pixels, one bit each, drawn in a foreground and a background colour)
// and the playfield maps made of them, two layers. A background is a project asset of kind
// "background" (backgrounds.py checks it); Convert to C gives what prg32_tile_define and
// prg32_playfield_put draw.
(function () {
  const canvas = document.getElementById('backgroundCanvas');
  if (!canvas) return;
  const projectId = $('#projectId').val() || null;
  const listUrl = '/api/assets?kind=background' + (projectId ? '&project_id=' + encodeURIComponent(projectId) : '');
  const ctx = canvas.getContext('2d');
  const tileCanvas = document.getElementById('tileCanvas');
  const tileCtx = tileCanvas.getContext('2d');
  let current = null;          // {id, version, name, width, height, tiles, layers}
  let tileId = 0;              // the tile the map brush paints (0: empty)
  let layer = 0;

  function emptyLayer(width, height) { return Array.from({ length: height }, () => Array(width).fill(0)); }
  function fresh(name) {
    // Two tiles to start with: a full brick and a ground line, so the map has something to paint.
    return { id: null, version: 0, name: name || 'level', width: 40, height: 25,
      tiles: [{ id: 1, name: 'brick', rows: [255, 129, 129, 255, 255, 24, 24, 255], fg: '#c84c0c', bg: '#000000', flags: ['solid'] },
        { id: 2, name: 'grass', rows: [0, 0, 0, 0, 0, 0, 255, 255], fg: '#00a800', bg: '#000000', flags: ['platform'] }],
      layers: [emptyLayer(40, 25), emptyLayer(40, 25)] };
  }
  function tile(id) { return current.tiles.find(item => item.id === id); }

  // One tile drawn at (x, y), `size` screen pixels per tile pixel.
  function drawTile(target, item, x, y, size, alpha) {
    target.globalAlpha = alpha || 1;
    for (let row = 0; row < 8; row++) {
      for (let col = 0; col < 8; col++) {
        target.fillStyle = (item.rows[row] >> (7 - col)) & 1 ? item.fg : item.bg;
        target.fillRect(x + col * size, y + row * size, size, size);
      }
    }
    target.globalAlpha = 1;
  }

  function cellSize() { return Math.max(1, Math.floor(Math.min(canvas.width / (current.width * 8), canvas.height / (current.height * 8)))); }

  function drawMap() {
    const size = cellSize(), cell = size * 8;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#20232a';
    ctx.fillRect(0, 0, current.width * cell, current.height * cell);
    const showOther = $('#backgroundShowOther').is(':checked');
    const order = layer === 0 ? [[0, 1], [1, showOther ? 0.35 : 0]] : [[0, showOther ? 0.35 : 0], [1, 1]];
    for (const [index, alpha] of order) {
      if (!alpha || !current.layers[index]) continue;
      current.layers[index].forEach((row, y) => row.forEach((id, x) => {
        const item = id && tile(id);
        if (item) drawTile(ctx, item, x * cell, y * cell, size, alpha);
      }));
    }
    ctx.strokeStyle = 'rgba(255,255,255,.08)';
    for (let x = 0; x <= current.width; x++) { ctx.beginPath(); ctx.moveTo(x * cell + 0.5, 0); ctx.lineTo(x * cell + 0.5, current.height * cell); ctx.stroke(); }
    for (let y = 0; y <= current.height; y++) { ctx.beginPath(); ctx.moveTo(0, y * cell + 0.5); ctx.lineTo(current.width * cell, y * cell + 0.5); ctx.stroke(); }
  }

  function tileImage(item) {
    const small = document.createElement('canvas');
    small.width = small.height = 24;
    drawTile(small.getContext('2d'), item, 0, 0, 3);
    return small.toDataURL();
  }

  function drawPalette() {
    const empty = `<button type="button" class="tile-entry tile-empty" role="radio" aria-checked="${tileId === 0}" data-tile="0"
      title="${Kit.escape(tr('js.backgrounds.empty', 'Empty (0)'))}" aria-label="${Kit.escape(tr('js.backgrounds.empty', 'Empty (0)'))}">0</button>`;
    $('#tilePalette').html(empty + current.tiles.map(item => `<button type="button" class="tile-entry" role="radio" aria-checked="${tileId === item.id}"
      data-tile="${item.id}" title="${Kit.escape(item.id + ': ' + item.name)}" aria-label="${Kit.escape(item.id + ': ' + item.name)}"><img alt="" src="${tileImage(item)}"></button>`).join(''));
  }

  function drawTileEditor() {
    const item = tile(tileId);
    tileCtx.clearRect(0, 0, tileCanvas.width, tileCanvas.height);
    $('#tileNumber').text(item ? item.id : '');
    $('#tileName, #tileFg, #tileBg, .tile-flag, #removeTile').prop('disabled', !item);
    if (!item) return;
    drawTile(tileCtx, item, 0, 0, tileCanvas.width / 8);
    tileCtx.strokeStyle = 'rgba(128,128,128,.6)';
    for (let i = 0; i <= 8; i++) {
      const at = i * tileCanvas.width / 8 + 0.5;
      tileCtx.beginPath(); tileCtx.moveTo(at, 0); tileCtx.lineTo(at, tileCanvas.height); tileCtx.stroke();
      tileCtx.beginPath(); tileCtx.moveTo(0, at); tileCtx.lineTo(tileCanvas.width, at); tileCtx.stroke();
    }
    $('#tileName').val(item.name);
    $('#tileFg').val(item.fg);
    $('#tileBg').val(item.bg);
    $('.tile-flag').each(function () { this.checked = item.flags.includes(this.value); });
  }

  function redraw() { drawMap(); drawPalette(); drawTileEditor(); }

  function setBackground(asset) {
    const data = asset.data || {};
    current = { id: asset.id || null, version: asset.version || 0, name: asset.name || 'level',
      width: data.width || 40, height: data.height || 25, tiles: (data.tiles || []).map(item => ({ ...item, rows: item.rows.slice(), flags: (item.flags || []).slice() })),
      layers: (data.layers || []).map(rows => rows.map(row => row.slice())) };
    while (current.layers.length < 2) current.layers.push(emptyLayer(current.width, current.height));
    tileId = current.tiles[0] ? current.tiles[0].id : 0;
    $('#backgroundId').val(current.id || '');
    $('#backgroundName').val(current.name);
    $('#backgroundWidth').val(current.width);
    $('#backgroundHeight').val(current.height);
    redraw();
  }

  function payload() {
    // The front layer is kept only when something is on it, so a one-layer background stays one layer.
    const used = current.layers[1].some(row => row.some(Boolean));
    return { project_id: projectId, kind: 'background', name: $('#backgroundName').val() || 'level',
      content_type: 'application/json', expected_version: current.version,
      data: { width: current.width, height: current.height, tiles: current.tiles, layers: used ? current.layers : [current.layers[0]] } };
  }

  function loadList() {
    return Kit.api(listUrl).then(data => {
      const items = (data.assets || []).filter(item => item.kind === 'background');
      $('#backgroundList').html(items.map(item => `<button class="list-group-item list-group-item-action background-choice ${item.id === (current && current.id) ? 'active' : ''}" data-id="${Kit.escape(item.id)}">${Kit.escape(item.name)} <span class="small">${Kit.escape(String(item.data.width))}x${Kit.escape(String(item.data.height))}</span></button>`).join('')
        || `<div class="list-group-item text-muted">${Kit.escape(tr('js.backgrounds.none_yet', 'No backgrounds yet.'))}</div>`);
      return items;
    });
  }

  function save() {
    const body = payload();
    const request = current.id ? Kit.api('/api/assets/' + encodeURIComponent(current.id), { method: 'PUT', body })
      : Kit.api('/api/assets', { method: 'POST', body });
    return request.then(asset => {
      Kit.toast(tr('js.backgrounds.saved', 'Background saved'), 'success');
      setBackground(asset);
      loadList();
      $(document).trigger('prg32:backgrounds-changed', [asset]);
      return asset;
    });
  }

  function cellAt(event, target, columns, rows) {
    const rect = target.getBoundingClientRect();
    const x = Math.floor((event.clientX - rect.left) * (target.width / rect.width) / (target.width / columns));
    const y = Math.floor((event.clientY - rect.top) * (target.height / rect.height) / (target.height / rows));
    return x >= 0 && y >= 0 && x < columns && y < rows ? [x, y] : null;
  }

  // The map: the brush paints the chosen tile (0 empties a cell). Pointer events: mouse, pen, touch.
  let painting = false;
  canvas.style.touchAction = 'none';
  function paintMap(event) {
    const size = cellSize() * 8;
    const at = cellAt(event, canvas, canvas.width / size, canvas.height / size);
    if (!at || at[0] >= current.width || at[1] >= current.height) return;
    current.layers[layer][at[1]][at[0]] = tileId;
    drawMap();
  }
  canvas.addEventListener('pointerdown', event => { painting = true; canvas.setPointerCapture(event.pointerId); paintMap(event); });
  canvas.addEventListener('pointermove', event => { if (painting) paintMap(event); });
  ['pointerup', 'pointercancel'].forEach(name => canvas.addEventListener(name, () => { painting = false; }));

  // The tile: a click turns a pixel on or off; dragging paints the same value.
  let tileValue = null;
  tileCanvas.style.touchAction = 'none';
  function paintTile(event) {
    const item = tile(tileId);
    const at = item && cellAt(event, tileCanvas, 8, 8);
    if (!at) return;
    const bit = 1 << (7 - at[0]);
    if (tileValue === null) tileValue = !(item.rows[at[1]] & bit);
    item.rows[at[1]] = tileValue ? item.rows[at[1]] | bit : item.rows[at[1]] & ~bit;
    redraw();
  }
  tileCanvas.addEventListener('pointerdown', event => { tileValue = null; tileCanvas.setPointerCapture(event.pointerId); paintTile(event); });
  tileCanvas.addEventListener('pointermove', event => { if (tileValue !== null) paintTile(event); });
  ['pointerup', 'pointercancel'].forEach(name => tileCanvas.addEventListener(name, () => { tileValue = null; }));

  $('#tilePalette').on('click', '.tile-entry', function () { tileId = Number(this.dataset.tile); drawPalette(); drawTileEditor(); });
  $('#tilePalette').on('keydown', '.tile-entry', function (event) {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];
    if (!step) return;
    event.preventDefault();
    const ids = [0].concat(current.tiles.map(item => item.id));
    tileId = ids[(ids.indexOf(tileId) + step + ids.length) % ids.length];
    drawPalette(); drawTileEditor();
    $('#tilePalette .tile-entry[data-tile="' + tileId + '"]').trigger('focus');
  });
  $('#tileName').on('input', function () { tile(tileId).name = this.value.slice(0, 32); drawPalette(); });
  $('#tileFg').on('input', function () { tile(tileId).fg = this.value.toLowerCase(); redraw(); });
  $('#tileBg').on('input', function () { tile(tileId).bg = this.value.toLowerCase(); redraw(); });
  $('.tile-flag').on('change', function () {
    const item = tile(tileId);
    item.flags = $('.tile-flag:checked').map(function () { return this.value; }).get();
    drawTileEditor();
  });
  $('#addTile').on('click', () => {
    let id = 1;
    while (tile(id) && id < 255) id++;
    if (tile(id)) { Kit.toast(tr('js.backgrounds.too_many_tiles', 'A background has at most 255 tiles.'), 'warning'); return; }
    current.tiles.push({ id, name: 'tile ' + id, rows: [0, 0, 0, 0, 0, 0, 0, 0], fg: '#ffffff', bg: '#000000', flags: [] });
    tileId = id;
    redraw();
  });
  // Removing a tile empties the map cells that used it.
  $('#removeTile').on('click', () => {
    const item = tile(tileId);
    if (!item) return;
    current.tiles = current.tiles.filter(other => other.id !== item.id);
    current.layers = current.layers.map(rows => rows.map(row => row.map(id => id === item.id ? 0 : id)));
    tileId = 0;
    redraw();
  });
  $('#backgroundLayer').on('change', function () { layer = Number(this.value); drawMap(); });
  $('#backgroundShowOther').on('change', drawMap);
  $('#resizeBackground').on('click', () => {
    const width = Math.max(1, Math.min(64, Number($('#backgroundWidth').val()) || 40));
    const height = Math.max(1, Math.min(32, Number($('#backgroundHeight').val()) || 25));
    current.layers = current.layers.map(rows => Array.from({ length: height }, (_, y) => Array.from({ length: width },
      (_, x) => (rows[y] && rows[y][x]) || 0)));
    current.width = width;
    current.height = height;
    redraw();
  });
  $('#newBackground').on('click', () => setBackground({ name: 'level', data: fresh() }));
  $('#saveBackground').on('click', () => save().catch(err => Kit.toast(err.message, 'danger')));
  $('#deleteBackground').on('click', () => {
    if (!current.id) { setBackground({ name: 'level', data: fresh() }); return; }
    if (!window.confirm(tr('js.backgrounds.delete', 'Delete the background "{name}"?', { name: current.name }))) return;
    Kit.api('/api/assets/' + encodeURIComponent(current.id), { method: 'DELETE' }).then(() => {
      setBackground({ name: 'level', data: fresh() });
      $(document).trigger('prg32:backgrounds-changed', [null]);
      return loadList();
    }).catch(err => Kit.toast(err.message, 'danger'));
  });
  $('#backgroundList').on('click', '.background-choice', function () {
    Kit.api('/api/assets/' + encodeURIComponent($(this).data('id'))).then(setBackground).catch(err => Kit.toast(err.message, 'danger'));
  });
  $('#convertBackground').on('click', () => {
    save().then(asset => Kit.api('/api/assets/' + encodeURIComponent(asset.id) + '/convert', { method: 'POST', body: {} }))
      .then(result => { $('#backgroundC').text(result.c_source); Kit.toast(tr('js.backgrounds.converted', 'Background C made'), 'success'); })
      .catch(err => Kit.toast(err.message, 'danger'));
  });

  setBackground({ name: 'level', data: fresh() });
  loadList().catch(err => Kit.toast(err.message, 'danger'));
  window.PRG32Backgrounds = {
    open(id) { return Kit.api('/api/assets/' + encodeURIComponent(id)).then(setBackground); },
    create() { setBackground({ name: 'level', data: fresh() }); },
    list: loadList,
  };
})();
