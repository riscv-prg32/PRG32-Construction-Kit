// Tools > Color Picker (docs/color_picker.md): a colour as RGB24 (8 bits each of red, green, blue)
// and as RGB565, the PRG32 screen's format (5 bits red, 6 green, 5 blue in one 16-bit number).
// Everything happens in this page; nothing is sent anywhere.
(function () {
  // The conversions, kept apart from the page so they can be read (and tested) on their own.
  const PRG32Color = {
    rgb24(r, g, b) { return (r << 16) | (g << 8) | b; },
    // Keep the top 5, 6 and 5 bits of each channel: what the PRG32 screen can show.
    rgb565(r, g, b) { return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3); },
    // Back to 8 bits per channel, repeating the top bits so white stays white (0xFFFF -> #FFFFFF).
    rgb565ToRgb(value) {
      const r5 = (value >> 11) & 31, g6 = (value >> 5) & 63, b5 = value & 31;
      return { r: (r5 << 3) | (r5 >> 2), g: (g6 << 2) | (g6 >> 4), b: (b5 << 3) | (b5 >> 2) };
    },
    hex(value, digits) { return '0x' + value.toString(16).toUpperCase().padStart(digits, '0'); },
    // Binary in groups: RGB24 as 8-8-8 bits, RGB565 as 5-6-5 bits, one group per colour.
    binary(value, groups) {
      const bits = value.toString(2).padStart(groups.reduce((a, b) => a + b, 0), '0');
      let at = 0;
      return groups.map(size => { const part = bits.slice(at, at + size); at += size; return part; }).join(' ');
    },
    // The PRG32's named colours (prg32.h), and the nearest one to an RGB565 value.
    NAMED: { BLACK: 0x0000, WHITE: 0xFFFF, RED: 0xF800, GREEN: 0x07E0, BLUE: 0x001F, YELLOW: 0xFFE0, CYAN: 0x07FF, MAGENTA: 0xF81F },
    nearest(value) {
      const a = PRG32Color.rgb565ToRgb(value);
      let best = null, distance = Infinity;
      for (const [name, named] of Object.entries(PRG32Color.NAMED)) {
        const b = PRG32Color.rgb565ToRgb(named);
        const d = (a.r - b.r) ** 2 + (a.g - b.g) ** 2 + (a.b - b.b) ** 2;
        if (d < distance) { best = name; distance = d; }
      }
      return { name: 'PRG32_COLOR_' + best, exact: distance === 0 };
    }
  };
  window.PRG32Color = PRG32Color;

  const page = $('#colorPicker');
  if (!page.length) return;
  let current = { r: 255, g: 204, b: 0 };

  function clamp(value) { return Math.max(0, Math.min(255, Math.round(Number(value) || 0))); }
  function cssHex(c) { return '#' + [c.r, c.g, c.b].map(v => v.toString(16).toUpperCase().padStart(2, '0')).join(''); }

  function show(from) {
    const { r, g, b } = current;
    const v24 = PRG32Color.rgb24(r, g, b);
    const v565 = PRG32Color.rgb565(r, g, b);
    const back = PRG32Color.rgb565ToRgb(v565);
    const near = PRG32Color.nearest(v565);
    if (from !== 'picker') $('#colorInput').val(cssHex(current).toLowerCase());
    if (from !== 'hex') $('#hexInput').val(cssHex(current)).removeClass('is-invalid');
    for (const channel of ['r', 'g', 'b']) {
      if (from !== channel + 'Range') $('#' + channel + 'Range').val(current[channel]);
      if (from !== channel + 'Number') $('#' + channel + 'Number').val(current[channel]);
    }
    $('[data-out="rgb24-hex"]').text(PRG32Color.hex(v24, 6) + '  ' + cssHex(current));
    $('[data-out="rgb24-dec"]').text(String(v24));
    $('[data-out="rgb24-bin"]').text(PRG32Color.binary(v24, [8, 8, 8]));
    $('[data-out="rgb565-hex"]').text(PRG32Color.hex(v565, 4));
    $('[data-out="rgb565-dec"]').text(String(v565));
    $('[data-out="rgb565-bin"]').text(PRG32Color.binary(v565, [5, 6, 5]));
    $('[data-out="channels"]').text(tr('js.tools.channels_value', 'RGB24 R={r} G={g} B={b}; RGB565 R={r5}/31 G={g6}/63 B={b5}/31', {
      r, g, b, r5: v565 >> 11, g6: (v565 >> 5) & 63, b5: v565 & 31 }));
    $('[data-out="c"]').text(PRG32Color.hex(v565, 4) + ' /* ' + cssHex(back) + ' */');
    $('[data-out="nearest"]').text(near.name + (near.exact ? ' ' + tr('js.tools.exact', '(exactly this colour)') : ''));
    $('#swatch24').css('background-color', cssHex(current));
    $('#swatch565').css('background-color', cssHex(back));
  }

  $('#colorInput').on('input', function () {
    const value = this.value;
    current = { r: parseInt(value.slice(1, 3), 16), g: parseInt(value.slice(3, 5), 16), b: parseInt(value.slice(5, 7), 16) };
    show('picker');
  });
  $('#hexInput').on('input', function () {
    const match = /^#?([0-9a-fA-F]{6})$/.exec(this.value.trim());
    $(this).toggleClass('is-invalid', !match);
    if (!match) return;
    const hex = match[1];
    current = { r: parseInt(hex.slice(0, 2), 16), g: parseInt(hex.slice(2, 4), 16), b: parseInt(hex.slice(4, 6), 16) };
    show('hex');
  });
  for (const channel of ['r', 'g', 'b']) {
    $('#' + channel + 'Range, #' + channel + 'Number').on('input', function () {
      current = { ...current, [channel]: clamp(this.value) };
      show(this.id);
    });
  }
  $('#copyC').on('click', () => {
    const text = $('[data-out="c"]').text();
    (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject(new Error('no clipboard')))
      .then(() => Kit.toast(tr('js.tools.copied', 'Copied'), 'success'))
      .catch(() => Kit.toast(text, 'info'));
  });
  show('');
})();
