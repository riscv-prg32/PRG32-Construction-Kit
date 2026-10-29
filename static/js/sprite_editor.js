// Sprite Lab (_sprite_lab.html), an IDE tab for the open project (ADR-0024): its sprites are the
// project's (project_id). It tells the IDE when they change ("prg32:sprites-changed"), so the
// project tree shows them.
//
// A sprite has direct colours (each pixel its own #rrggbb) or indexed colours: a palette and, for
// each pixel, the number of its palette entry (sprite_palette.py). With a palette, the brush paints
// the chosen entry, changing an entry recolours every pixel that uses it, and the eraser paints the
// transparent entry. ``pixels`` always holds every pixel's colour, made from the palette.
(function () {
  const canvas = document.getElementById('spriteCanvas');
  if (!canvas) return;
  const projectId = $('#projectId').val() || null;
  const spritesUrl = projectId ? '/api/sprites?project_id=' + encodeURIComponent(projectId) : '/api/sprites';
  const ctx = canvas.getContext('2d');
  let width = 16;
  let height = 16;
  let pixels = [];
  let selectedId = null;
  let erase = false;
  let palette = null;          // null: direct colours; else {colors, transparent_index, indices}
  let entry = 0;               // the palette entry the brush paints
  const PRESETS = {
    prg32: ['#000000', '#ffffff', '#ff0000', '#00ff00', '#0000ff', '#ffff00', '#00ffff', '#ff00ff'],
    greys: ['#000000', '#555555', '#aaaaaa', '#ffffff'],
    mono: ['#000000', '#ffffff']
  };

  // The smallest PRG32 packing that holds the palette: 1, 2, 4 or 8 bits per pixel.
  function bitsPerPixel(count) { return count <= 2 ? 1 : count <= 4 ? 2 : count <= 16 ? 4 : 8; }

  // Every pixel's colour, made from the palette (the transparent entry is "transparent").
  function pixelsFromPalette() {
    pixels = palette.indices.map(row => row.map(value => value === palette.transparent_index ? 'transparent' : palette.colors[value]));
  }

  function nearestEntry(hex, colors) {
    const rgb = value => [1, 3, 5].map(i => parseInt(value.slice(i, i + 2), 16));
    const target = rgb(hex);
    let best = 0, distance = Infinity;
    colors.forEach((color, index) => {
      if (palette && index === palette.transparent_index) return;
      const [r, g, b] = rgb(color);
      const d = (r - target[0]) ** 2 + (g - target[1]) ** 2 + (b - target[2]) ** 2;
      if (d < distance) { best = index; distance = d; }
    });
    return best;
  }

  // Direct -> indexed: one entry per colour the sprite uses (transparent pixels get entry 0).
  // More than 256 colours: the 256 most used, the others drawn with the nearest of those.
  function paletteFromPixels() {
    const counts = new Map();
    let transparent = false;
    pixels.forEach(row => row.forEach(color => {
      if (color === 'transparent') transparent = true;
      else counts.set(color.toLowerCase(), (counts.get(color.toLowerCase()) || 0) + 1);
    }));
    const used = [...counts.entries()].sort((a, b) => b[1] - a[1]).map(([color]) => color);
    const colors = (transparent ? ['#000000'] : []).concat(used).slice(0, 256);
    if (!colors.length) colors.push('#000000', '#ffd800');
    palette = { colors, transparent_index: transparent ? 0 : -1, indices: [] };
    const index = new Map(colors.map((color, i) => [color, i]));
    palette.indices = pixels.map(row => row.map(color => color === 'transparent' ? 0
      : index.has(color.toLowerCase()) && !(transparent && index.get(color.toLowerCase()) === 0) ? index.get(color.toLowerCase())
        : nearestEntry(color.toLowerCase(), colors)));
    entry = Math.min(transparent ? 1 : 0, colors.length - 1);
  }

  function showPalette() {
    const indexed = palette !== null;
    $('#spriteColorMode').val(indexed ? 'indexed' : 'direct');
    $('#spritePalettePanel').prop('hidden', !indexed);
    $('#spriteDirectPanel').prop('hidden', indexed);
    if (!indexed) { $('#eraser').prop('disabled', false); return; }
    $('#spritePalette').html(palette.colors.map((color, index) => {
      const see = index === palette.transparent_index;
      return `<button type="button" class="palette-entry${see ? ' is-transparent' : ''}" role="radio" aria-checked="${index === entry}"
        data-entry="${index}" title="${Kit.escape(tr('js.sprite_editor.palette_entry', 'Entry {index}: {color}', { index, color }) + (see ? ' · ' + tr('js.sprite_editor.transparent', 'transparent') : ''))}"
        aria-label="${Kit.escape(tr('js.sprite_editor.palette_entry', 'Entry {index}: {color}', { index, color }) + (see ? ' · ' + tr('js.sprite_editor.transparent', 'transparent') : ''))}">${index}</button>`;
    }).join(''));
    $('#spritePalette .palette-entry').each(function () {
      const index = Number(this.dataset.entry);
      if (index !== palette.transparent_index) $(this).css({ 'background-color': palette.colors[index], color: contrast(palette.colors[index]) });
    });
    $('#paletteEntryColor').val(palette.colors[entry]);
    $('#paletteTransparent').prop('checked', entry === palette.transparent_index);
    $('#eraser').prop('disabled', palette.transparent_index < 0);
    $('#paletteRemove').prop('disabled', palette.colors.length <= 1);
    $('#paletteAdd').prop('disabled', palette.colors.length >= 256);
    const bits = bitsPerPixel(palette.colors.length);
    $('#spritePaletteInfo').text(tr('js.sprite_editor.palette_info', '{count} colours · {bits} bits per pixel · {bytes} bytes (direct: {direct})', {
      count: palette.colors.length, bits, bytes: Math.ceil(width * height * bits / 8), direct: width * height * 2 }));
  }

  function contrast(hex) {
    const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16));
    return r * 0.299 + g * 0.587 + b * 0.114 > 140 ? '#000000' : '#ffffff';
  }

  function emptyPixels(w, h) {
    return Array.from({ length: h }, () => Array.from({ length: w }, () => 'transparent'));
  }

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const cell = Math.floor(Math.min(canvas.width / width, canvas.height / height));
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const color = pixels[y] && pixels[y][x] || 'transparent';
        if (color !== 'transparent') {
          ctx.fillStyle = color;
          ctx.fillRect(x * cell, y * cell, cell, cell);
        }
        ctx.strokeStyle = 'rgba(15,23,42,.18)';
        ctx.strokeRect(x * cell, y * cell, cell, cell);
      }
    }
  }

  // Copy old pixels into a width x height grid, so short or missing rows never break painting.
  function fitPixels(source, w, h) {
    const grid = emptyPixels(w, h);
    for (let y = 0; y < h; y++) {
      const row = Array.isArray(source) && Array.isArray(source[y]) ? source[y] : [];
      for (let x = 0; x < w; x++) if (typeof row[x] === 'string') grid[y][x] = row[x];
    }
    return grid;
  }

  function setSprite(sprite) {
    selectedId = sprite.id || null;
    width = Number(sprite.width || 16);
    height = Number(sprite.height || 16);
    pixels = fitPixels(sprite.pixels, width, height);
    const saved = sprite.palette && sprite.palette.mode === 'indexed' ? sprite.palette : null;
    palette = saved ? { colors: saved.colors.slice(), transparent_index: saved.transparent_index,
      indices: saved.indices.map(row => row.slice()) } : null;
    entry = palette ? Math.min(palette.transparent_index === 0 ? 1 : 0, palette.colors.length - 1) : 0;
    if (palette) pixelsFromPalette();
    showPalette();
    $('#spriteId').val(selectedId || '');
    $('#spriteName').val(sprite.name || 'sprite');
    $('#spriteWidth').val(width);
    $('#spriteHeight').val(height);
    draw();
    if (window.PRG32ArtUsage) PRG32ArtUsage.render();   // "Use it in your game" follows the open sprite
  }

  function currentPayload() {
    return {
      project_id: projectId,
      name: $('#spriteName').val() || 'sprite',
      width,
      height,
      pixels,
      palette: palette ? { mode: 'indexed', colors: palette.colors, transparent_index: palette.transparent_index, indices: palette.indices } : {},
      data_url: canvasToDataURL()
    };
  }

  function canvasToDataURL() {
    const out = document.createElement('canvas');
    out.width = width;
    out.height = height;
    const outCtx = out.getContext('2d');
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const color = pixels[y] && pixels[y][x] || 'transparent';
        if (color !== 'transparent') {
          outCtx.fillStyle = color;
          outCtx.fillRect(x, y, 1, 1);
        }
      }
    }
    return out.toDataURL('image/png');
  }

  function loadSprites() {
    return Kit.api(spritesUrl).then(data => {
      const html = data.sprites.map(sprite => `<button class="list-group-item list-group-item-action sprite-choice ${sprite.id === selectedId ? 'active' : ''}" data-id="${Kit.escape(sprite.id)}">${Kit.escape(sprite.name)} <span class="small">${Kit.escape(sprite.width)}x${Kit.escape(sprite.height)}</span></button>`).join('');
      $('#spriteList').html(html || `<div class="list-group-item text-muted">${tr('js.sprite_editor.no_sprites_yet', 'No sprites yet.')}</div>`);
      if (!selectedId && data.sprites[0]) setSprite(data.sprites[0]);
    });
  }

  function save() {
    const payload = currentPayload();
    const method = selectedId ? 'PUT' : 'POST';
    const url = selectedId ? '/api/sprites/' + selectedId : '/api/sprites';
    return Kit.api(url, { method, body: payload }).then(sprite => {
      Kit.toast(tr('js.sprite_editor.sprite_saved', 'Sprite saved'), 'success');
      setSprite(sprite);
      loadSprites();
      $(document).trigger('prg32:sprites-changed', [sprite]);
      return sprite;
    });
  }

  function remove() {
    if (!selectedId) { setSprite({ name: 'sprite', width: 16, height: 16, pixels: emptyPixels(16, 16) }); return Promise.resolve(); }
    if (!window.confirm(tr('js.sprite_editor.delete_the_sprite', 'Delete the sprite "{name}"?', { name: $('#spriteName').val() }))) return Promise.resolve();
    return Kit.api('/api/sprites/' + encodeURIComponent(selectedId), { method: 'DELETE' }).then(() => {
      selectedId = null;
      setSprite({ name: 'sprite', width: 16, height: 16, pixels: emptyPixels(16, 16) });
      $(document).trigger('prg32:sprites-changed', [null]);
      return loadSprites();
    });
  }

  function resize() {
    width = Math.max(4, Math.min(64, Number($('#spriteWidth').val() || 16)));
    height = Math.max(4, Math.min(64, Number($('#spriteHeight').val() || 16)));
    pixels = fitPixels(pixels, width, height);
    if (palette) {
      const fill = palette.transparent_index >= 0 ? palette.transparent_index : 0;
      palette.indices = Array.from({ length: height }, (_, y) => Array.from({ length: width },
        (_, x) => palette.indices[y] && palette.indices[y][x] !== undefined ? palette.indices[y][x] : fill));
      pixelsFromPalette();
      showPalette();
    }
    draw();
  }

  function paint(event) {
    const rect = canvas.getBoundingClientRect();
    const cell = Math.floor(Math.min(canvas.width / width, canvas.height / height));
    const x = Math.floor((event.clientX - rect.left) * (canvas.width / rect.width) / cell);
    const y = Math.floor((event.clientY - rect.top) * (canvas.height / rect.height) / cell);
    if (x < 0 || y < 0 || x >= width || y >= height) return;
    if (palette) {
      palette.indices[y][x] = erase && palette.transparent_index >= 0 ? palette.transparent_index : entry;
      pixelsFromPalette();
    } else {
      pixels[y][x] = erase ? 'transparent' : $('#paintColor').val();
    }
    draw();
  }

  function importImage(file) {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = function () {
      URL.revokeObjectURL(url);
      const tmp = document.createElement('canvas');
      tmp.width = width;
      tmp.height = height;
      const tctx = tmp.getContext('2d');
      tctx.clearRect(0, 0, width, height);
      tctx.drawImage(img, 0, 0, width, height);
      const data = tctx.getImageData(0, 0, width, height).data;
      for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
          const i = (y * width + x) * 4;
          pixels[y][x] = data[i + 3] < 32 ? 'transparent' : '#' + [data[i], data[i + 1], data[i + 2]].map(v => v.toString(16).padStart(2, '0')).join('');
        }
      }
      // With a palette, each pixel takes the nearest palette colour (transparent stays transparent).
      if (palette) {
        palette.indices = pixels.map(row => row.map(color => color === 'transparent'
          ? (palette.transparent_index >= 0 ? palette.transparent_index : 0) : nearestEntry(color, palette.colors)));
        pixelsFromPalette();
      }
      draw();
    };
    img.src = url;
  }

  // Pointer events work for mouse, pen and classroom tablets alike.
  let painting = false;
  canvas.style.touchAction = 'none';
  canvas.addEventListener('pointerdown', event => { painting = true; canvas.setPointerCapture(event.pointerId); paint(event); });
  canvas.addEventListener('pointermove', event => { if (painting) paint(event); });
  ['pointerup', 'pointercancel'].forEach(name => canvas.addEventListener(name, () => { painting = false; }));

  $('#spriteColorMode').on('change', function () {
    if (this.value === 'indexed' && !palette) paletteFromPixels();
    if (this.value === 'direct' && palette) palette = null;     // pixels already hold every colour
    if (palette) pixelsFromPalette();
    showPalette();
    draw();
  });
  $('#spritePalette').on('click', '.palette-entry', function () { entry = Number(this.dataset.entry); showPalette(); });
  // Arrow keys move between entries, as in any radio group.
  $('#spritePalette').on('keydown', '.palette-entry', function (event) {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];
    if (!step) return;
    event.preventDefault();
    entry = (entry + step + palette.colors.length) % palette.colors.length;
    showPalette();
    $('#spritePalette .palette-entry')[entry].focus();
  });
  $('#paletteEntryColor').on('input', function () {
    palette.colors[entry] = this.value.toLowerCase();      // every pixel of this entry changes colour
    pixelsFromPalette(); showPalette(); draw();
  });
  $('#paletteTransparent').on('change', function () {
    palette.transparent_index = this.checked ? entry : -1;
    if (erase && palette.transparent_index < 0) $('#eraser').trigger('click');
    pixelsFromPalette(); showPalette(); draw();
  });
  $('#paletteAdd').on('click', () => {
    palette.colors.push($('#paletteEntryColor').val().toLowerCase());
    entry = palette.colors.length - 1;
    showPalette();
  });
  // Removing the last entry: its pixels take entry 0.
  $('#paletteRemove').on('click', () => {
    const last = palette.colors.length - 1;
    palette.colors.pop();
    palette.indices = palette.indices.map(row => row.map(value => value === last ? 0 : value));
    if (palette.transparent_index === last) palette.transparent_index = -1;
    entry = Math.min(entry, palette.colors.length - 1);
    pixelsFromPalette(); showPalette(); draw();
  });
  // A ready palette: the sprite keeps its pixels' places, each pixel the nearest new colour.
  $('#palettePreset').on('change', function () {
    if (!this.value) return;
    const colors = PRESETS[this.value].slice();
    const old = palette;
    palette = { colors, transparent_index: -1, indices: [] };
    palette.indices = pixels.map(row => row.map(color => color === 'transparent' ? 0 : nearestEntry(color, colors)));
    if (old && old.transparent_index >= 0) palette.transparent_index = 0;
    entry = 0;
    this.value = '';
    pixelsFromPalette(); showPalette(); draw();
  });
  $('#newSprite').on('click', () => setSprite({ name: 'new_sprite', width: 16, height: 16, pixels: emptyPixels(16, 16) }));
  $('#resizeSprite').on('click', resize);
  $('#saveSprite').on('click', () => save().catch(err => Kit.toast(err.message, 'danger')));
  $('#eraser').on('click', function () { erase = !erase; $(this).toggleClass('btn-danger', erase).attr('aria-pressed', String(erase)); });
  $('#deleteSprite').on('click', () => remove().catch(err => Kit.toast(err.message, 'danger')));
  $('#spriteList').on('click', '.sprite-choice', function () { Kit.api('/api/sprites/' + encodeURIComponent($(this).data('id'))).then(setSprite).catch(err => Kit.toast(err.message, 'danger')); });
  $('#imageImport').on('change', function () { if (this.files[0]) importImage(this.files[0]); });
  $('#downloadPng').on('click', () => {
    const a = document.createElement('a');
    a.href = canvasToDataURL();
    a.download = ($('#spriteName').val() || 'sprite') + '.png';
    a.click();
  });
  $('#convertSprite').on('click', () => {
    save().then(() => Kit.api('/api/sprites/' + selectedId + '/convert', { method: 'POST', body: {} }))
      .then(result => { $('#spriteC').text(result.c_source); Kit.toast(tr('js.sprite_editor.sprite_c_artifact_created', 'Sprite C artifact created'), 'success'); })
      .catch(err => Kit.toast(err.message, 'danger'));
  });

  setSprite({ name: 'sprite', width: 16, height: 16, pixels: emptyPixels(16, 16) });
  loadSprites().catch(err => Kit.toast(err.message, 'danger'));
  // The IDE opens a sprite from its project tree.
  window.PRG32SpriteLab = {
    open(id) { return Kit.api('/api/sprites/' + encodeURIComponent(id)).then(setSprite); },
    create() { setSprite({ name: 'new_sprite', width: 16, height: 16, pixels: emptyPixels(16, 16) }); },
    reload: loadSprites,
  };
})();
