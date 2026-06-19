(function () {
  const canvas = document.getElementById('spriteCanvas');
  const ctx = canvas.getContext('2d');
  let width = 16;
  let height = 16;
  let pixels = [];
  let selectedId = null;
  let erase = false;

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

  function setSprite(sprite) {
    selectedId = sprite.id || null;
    width = Number(sprite.width || 16);
    height = Number(sprite.height || 16);
    pixels = Array.isArray(sprite.pixels) && sprite.pixels.length ? sprite.pixels : emptyPixels(width, height);
    $('#spriteId').val(selectedId || '');
    $('#spriteName').val(sprite.name || 'sprite');
    $('#spriteWidth').val(width);
    $('#spriteHeight').val(height);
    draw();
  }

  function currentPayload() {
    return {
      name: $('#spriteName').val() || 'sprite',
      width,
      height,
      pixels,
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
    return Kit.api('/api/sprites').then(data => {
      const html = data.sprites.map(sprite => `<button class="list-group-item list-group-item-action sprite-choice ${sprite.id === selectedId ? 'active' : ''}" data-id="${sprite.id}">${Kit.escape(sprite.name)} <span class="small">${sprite.width}x${sprite.height}</span></button>`).join('');
      $('#spriteList').html(html || '<div class="list-group-item text-muted">No sprites yet.</div>');
      if (!selectedId && data.sprites[0]) setSprite(data.sprites[0]);
    });
  }

  function save() {
    const payload = currentPayload();
    const method = selectedId ? 'PUT' : 'POST';
    const url = selectedId ? '/api/sprites/' + selectedId : '/api/sprites';
    return Kit.api(url, { method, body: payload }).then(sprite => {
      Kit.toast('Sprite saved', 'success');
      setSprite(sprite);
      loadSprites();
    });
  }

  function resize() {
    width = Math.max(4, Math.min(64, Number($('#spriteWidth').val() || 16)));
    height = Math.max(4, Math.min(64, Number($('#spriteHeight').val() || 16)));
    pixels = emptyPixels(width, height);
    draw();
  }

  function paint(event) {
    const rect = canvas.getBoundingClientRect();
    const cell = Math.floor(Math.min(canvas.width / width, canvas.height / height));
    const x = Math.floor((event.clientX - rect.left) * (canvas.width / rect.width) / cell);
    const y = Math.floor((event.clientY - rect.top) * (canvas.height / rect.height) / cell);
    if (x < 0 || y < 0 || x >= width || y >= height) return;
    pixels[y][x] = erase ? 'transparent' : $('#paintColor').val();
    draw();
  }

  function importImage(file) {
    const img = new Image();
    img.onload = function () {
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
      draw();
    };
    img.src = URL.createObjectURL(file);
  }

  let mouseDown = false;
  canvas.addEventListener('mousedown', event => { mouseDown = true; paint(event); });
  canvas.addEventListener('mousemove', event => { if (mouseDown) paint(event); });
  window.addEventListener('mouseup', () => { mouseDown = false; });

  $('#newSprite').on('click', () => setSprite({ name: 'new_sprite', width: 16, height: 16, pixels: emptyPixels(16, 16) }));
  $('#resizeSprite').on('click', resize);
  $('#saveSprite').on('click', () => save().catch(err => Kit.toast(err.message, 'danger')));
  $('#eraser').on('click', function () { erase = !erase; $(this).toggleClass('btn-danger', erase); });
  $('#spriteList').on('click', '.sprite-choice', function () { Kit.api('/api/sprites/' + $(this).data('id')).then(setSprite); });
  $('#imageImport').on('change', function () { if (this.files[0]) importImage(this.files[0]); });
  $('#downloadPng').on('click', () => {
    const a = document.createElement('a');
    a.href = canvasToDataURL();
    a.download = ($('#spriteName').val() || 'sprite') + '.png';
    a.click();
  });
  $('#convertSprite').on('click', () => {
    save().then(() => Kit.api('/api/sprites/' + selectedId + '/convert', { method: 'POST', body: {} }))
      .then(result => { $('#spriteC').text(result.c_source); Kit.toast('Sprite C artifact created', 'success'); })
      .catch(err => Kit.toast(err.message, 'danger'));
  });

  setSprite({ name: 'sprite', width: 16, height: 16, pixels: emptyPixels(16, 16) });
  loadSprites().catch(err => Kit.toast(err.message, 'danger'));
})();
