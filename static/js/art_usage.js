// "Use it in your game" in Sprite Lab, Backgrounds and AudioStudio (docs/project_art.md): the line
// that uses the sprite, background or sound being edited, in Blocks, PRG32 Python, C or assembly.
// The lines come from the server (GET /api/projects/<id>/art, project_assets.usage), which the IDE
// loads and announces with the 'prg32:art' event; nothing here works out a C name by itself.
(function () {
  'use strict';
  let info = null;
  const INCLUDE = { c: '#include "prg32_assets.h"   /* once, below #include "prg32.h" */',
                    asm: '#include "prg32_assets.S"   /* once, on a line of its own */' };

  // The project's own language until the student picks another one in the list.
  function language(panel) {
    const select = panel.find('.art-usage-language');
    const mode = window.PRG32Ide && window.PRG32Ide.mode;
    if (!select.data('chosen') && mode && select.val() !== mode) select.val(mode);
    return select.val() || 'blocks';
  }

  function blocksLine(kind, entry) {
    if (kind === 'sprites') return `${tr('js.blockly_blocks.draw_sprite', 'draw sprite')} ${entry.title} x 10 y 20`;
    if (kind === 'backgrounds') {
      return `${tr('js.blockly_blocks.load_background', 'load background')} ${entry.title}\n` +
        `${tr('js.blockly_blocks.draw_background', 'draw background')} ${entry.title}`;
    }
    if (kind === 'effects') return `${tr('js.blockly_blocks.play_sound_effect', 'play sound effect')} ${entry.title}`;
    return `${tr('js.blockly_blocks.play_soundtrack', 'play soundtrack')} ${entry.title}`;
  }

  function lineOf(kind, entry, lang) {
    return lang === 'blocks' ? blocksLine(kind, entry) : entry[lang];
  }

  function render(panel) {
    const kind = panel.data('art-usage');
    const lang = language(panel);
    const code = panel.find('.art-usage-code');
    if (!info) { code.text(tr('js.art_usage.open_a_project', 'Open a project to see how its code uses this.')); return; }
    const lines = [];
    if (INCLUDE[lang]) lines.push(INCLUDE[lang], '');
    if (kind === 'sound') {
      const sounds = [...info.usage.effects.map(entry => ['effects', entry]), ...info.usage.soundtracks.map(entry => ['soundtracks', entry])];
      if (!sounds.length) { code.text(tr('js.art_usage.no_sounds_yet', 'No sound effects or soundtracks yet.')); return; }
      sounds.forEach(([group, entry]) => lines.push(lineOf(group, entry, lang)));
    } else {
      const name = String($(panel.data('name-input')).val() || '');
      const entry = (info.usage[kind] || []).find(item => item.title === name);
      if (!entry) {
        code.text(kind === 'sprites' ? tr('js.art_usage.save_the_sprite_first', 'Save the sprite: then its line for your game is shown here.')
          : tr('js.art_usage.save_the_background_first', 'Save the background: then its lines for your game are shown here.'));
        return;
      }
      lines.push(lineOf(kind, entry, lang));
    }
    code.text(lines.join('\n'));
  }

  function renderAll() { $('[data-art-usage]').each(function () { render($(this)); }); }

  $(document).on('prg32:art', (event, data) => {
    info = data;
    renderAll();
  });
  $(document).on('ide:tab', renderAll);
  $(document).on('change', '[data-art-usage] .art-usage-language', function () {
    $(this).data('chosen', true);
    render($(this).closest('[data-art-usage]'));
  });
  $(document).on('input', '#spriteName, #backgroundName', renderAll);
  window.PRG32ArtUsage = { render: renderAll };
})();
