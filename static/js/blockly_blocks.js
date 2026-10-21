window.PRG32Blocks = (function () {
  let workspace = null;

  const COLORS = [
    ['black', 'BLACK'], ['white', 'WHITE'], ['red', 'RED'], ['green', 'GREEN'], ['blue', 'BLUE'],
    ['yellow', 'YELLOW'], ['cyan', 'CYAN'], ['magenta', 'MAGENTA'], ['orange', 'ORANGE'], ['pink', 'PINK'],
    ['gray', 'GRAY'], ['dark gray', 'DARK_GRAY'], ['brown', 'BROWN'], ['purple', 'PURPLE'], ['navy', 'NAVY'], ['lime', 'LIME']
  ];
  const BUTTONS = [['left', 'LEFT'], ['right', 'RIGHT'], ['up', 'UP'], ['down', 'DOWN'], ['A', 'A'], ['B', 'B'], ['start', 'START'], ['select', 'SELECT'],
    ['player 2 left', 'P2_LEFT'], ['player 2 right', 'P2_RIGHT'], ['player 2 up', 'P2_UP'], ['player 2 down', 'P2_DOWN'], ['player 2 A', 'P2_A'], ['player 2 B', 'P2_B']];

  const text = (name, value) => ({ type: 'field_input', name, text: String(value) });
  const color = (name) => ({ type: 'field_dropdown', name, options: COLORS });
  const stmt = (def) => Object.assign({ previousStatement: null, nextStatement: null }, def);

  // Eight 'row' lines for an 8x8 picture: '#' is a lit pixel, '.' is empty.
  function pictureRows(start, rows) {
    const message = [];
    const args = [];
    for (let r = 0; r < 8; r++) {
      message.push('%' + (start + r * 2) + ' %' + (start + r * 2 + 1));
      args.push(text('ROW' + r, (rows && rows[r]) || '........'), { type: 'input_dummy' });
    }
    return { message: message.join(' '), args };
  }

  function pictureBlock(type, head, headArgs, colour, tooltip, rows) {
    const picture = pictureRows(headArgs.length + 2, rows);
    return stmt({
      type,
      message0: head + ' %' + (headArgs.length + 1) + ' ' + picture.message,
      args0: headArgs.concat([{ type: 'input_dummy' }], picture.args),
      colour,
      tooltip
    });
  }

  const SHIP = ['...##...', '..####..', '.##..##.', '########', '########', '.#.##.#.', '#......#', '........'];

  function defineBlocks() {
    if (Blockly.Blocks.prg32_on_start) return;
    Blockly.common.defineBlocksWithJsonArray([
      // Game lifecycle
      { type: 'prg32_on_start', message0: 'when game starts %1 %2', args0: [{ type: 'input_dummy' }, { type: 'input_statement', name: 'DO' }], colour: 40, tooltip: 'Runs once when the cartridge starts (C: <prefix>_init).' },
      { type: 'prg32_update', message0: 'every frame update %1 %2', args0: [{ type: 'input_dummy' }, { type: 'input_statement', name: 'DO' }], colour: 210, tooltip: 'Runs game logic once per frame (C: <prefix>_update).' },
      { type: 'prg32_draw', message0: 'every frame draw %1 %2', args0: [{ type: 'input_dummy' }, { type: 'input_statement', name: 'DO' }], colour: 160, tooltip: 'Draws the frame once per frame (C: <prefix>_draw).' },
      stmt({ type: 'prg32_comment', message0: 'comment %1', args0: [text('TEXT', 'explain this idea')], colour: 90, tooltip: 'A note for students; it becomes a C comment.' }),
      stmt({ type: 'prg32_splash', message0: 'show splash title %1 subtitle %2 for %3 ms background %4 text %5 accent %6', args0: [text('TITLE', 'MY GAME'), text('SUBTITLE', 'PRESS START'), text('MS', 1500), color('BG'), color('FG'), color('ACCENT')], colour: 40, tooltip: 'PRG32 splash screen (prg32_splash_show_game). Use it in "when game starts".' }),

      // Variables
      stmt({ type: 'prg32_set_state', message0: 'set %1 to %2', args0: [text('VAR', 'score'), text('VALUE', 0)], colour: 260, tooltip: 'Create or assign a whole-number variable.' }),
      stmt({ type: 'prg32_change_state', message0: 'change %1 by %2', args0: [text('VAR', 'score'), text('DELTA', 1)], colour: 260, tooltip: 'Add a number to a variable.' }),
      stmt({ type: 'prg32_clamp_state', message0: 'keep %1 between %2 and %3', args0: [text('VAR', 'player_x'), text('LOW', 0), text('HIGH', 304)], colour: 260, tooltip: 'Clamp a variable to a safe range.' }),
      stmt({ type: 'prg32_wrap_state', message0: 'wrap %1 around %2 to %3', args0: [text('VAR', 'ship_x'), text('LOW', 0), text('HIGH', 319)], colour: 260, tooltip: 'Leaving one side brings the value back on the other side.' }),
      stmt({ type: 'prg32_random_state', message0: 'set %1 to random from %2 to %3', args0: [text('VAR', 'target_x'), text('LOW', 0), text('HIGH', 304)], colour: 260, tooltip: 'Inclusive PRG32 random whole number.' }),

      // Lists
      stmt({ type: 'prg32_list_create', message0: 'make list %1 with %2 items, all %3', args0: [text('LIST', 'bricks'), text('SIZE', 10), text('VALUE', 0)], colour: 290, tooltip: 'A list of whole numbers (1 to 1024 items). Read an item in any field with name[position]; positions start at 0.' }),
      stmt({ type: 'prg32_list_set', message0: 'set item %1 of %2 to %3', args0: [text('INDEX', 0), text('LIST', 'bricks'), text('VALUE', 1)], colour: 290, tooltip: 'Positions outside the list are ignored.' }),
      stmt({ type: 'prg32_list_change', message0: 'change item %1 of %2 by %3', args0: [text('INDEX', 0), text('LIST', 'bricks'), text('DELTA', 1)], colour: 290, tooltip: 'Add a number to one item.' }),

      // Logic
      stmt({ type: 'prg32_if', message0: 'if %1 %2 %3', args0: [text('COND', 'score > 9'), { type: 'input_dummy' }, { type: 'input_statement', name: 'DO' }], colour: 15, tooltip: 'Runs the blocks inside when the condition is not 0.' }),
      stmt({ type: 'prg32_if_else', message0: 'if %1 %2 %3 else %4', args0: [text('COND', 'lives > 0'), { type: 'input_dummy' }, { type: 'input_statement', name: 'DO' }, { type: 'input_statement', name: 'ELSE' }], colour: 15, tooltip: 'Choose between two groups of blocks.' }),
      stmt({ type: 'prg32_repeat', message0: 'repeat with %1 from %2 to %3 %4 %5', args0: [text('VAR', 'i'), text('FROM', 0), text('TO', 9), { type: 'input_dummy' }, { type: 'input_statement', name: 'DO' }], colour: 15, tooltip: 'Counts from the first number to the last (at most 1024 times).' }),
      stmt({ type: 'prg32_if_touching', message0: 'if rect %1 %2 %3 %4 touches rect %5 %6 %7 %8 %9 %10', args0: [
        text('AX', 'player_x'), text('AY', 'player_y'), text('AW', 16), text('AH', 16),
        text('BX', 'enemy_x'), text('BY', 'enemy_y'), text('BW', 16), text('BH', 16),
        { type: 'input_dummy' }, { type: 'input_statement', name: 'DO' }
      ], colour: 15, tooltip: 'PRG32 rectangle hitbox collision (prg32_sprite_hitbox): x, y, width, height.' }),

      // Input
      stmt({ type: 'prg32_if_button', message0: 'if button %1 is held %2 %3', args0: [{ type: 'field_dropdown', name: 'BUTTON', options: BUTTONS }, { type: 'input_dummy' }, { type: 'input_statement', name: 'DO' }], colour: 20, tooltip: 'Runs every frame while the button is down.' }),
      stmt({ type: 'prg32_if_button_once', message0: 'if button %1 was just pressed %2 %3', args0: [{ type: 'field_dropdown', name: 'BUTTON', options: BUTTONS }, { type: 'input_dummy' }, { type: 'input_statement', name: 'DO' }], colour: 20, tooltip: 'Runs once per press (edge detection).' }),

      // Drawing
      stmt({ type: 'prg32_clear_screen', message0: 'clear screen %1', args0: [color('COLOR')], colour: 160, tooltip: 'Fill the 320x200 PRG32 game viewport.' }),
      stmt({ type: 'prg32_draw_rect', message0: 'draw rectangle x %1 y %2 w %3 h %4 color %5', args0: [text('X', 0), text('Y', 0), text('W', 16), text('H', 16), color('COLOR')], colour: 160, tooltip: 'Filled rectangle.' }),
      stmt({ type: 'prg32_draw_frame', message0: 'draw outline x %1 y %2 w %3 h %4 color %5', args0: [text('X', 0), text('Y', 0), text('W', 16), text('H', 16), color('COLOR')], colour: 160, tooltip: 'Rectangle border only.' }),
      stmt({ type: 'prg32_draw_rect_rgb', message0: 'draw rectangle x %1 y %2 w %3 h %4 color value %5', args0: [text('X', 0), text('Y', 0), text('W', 16), text('H', 16), text('RGB', 'rgb(255, 128, 0)')], colour: 160, tooltip: 'Colour from an expression: rgb(r, g, b) or an RGB565 number.' }),
      stmt({ type: 'prg32_draw_pixel', message0: 'draw pixel x %1 y %2 color %3', args0: [text('X', 0), text('Y', 0), color('COLOR')], colour: 160, tooltip: 'One pixel.' }),
      stmt({ type: 'prg32_draw_line', message0: 'draw line from x %1 y %2 to x %3 y %4 color %5', args0: [text('X1', 0), text('Y1', 0), text('X2', 16), text('Y2', 16), color('COLOR')], colour: 160, tooltip: "Bresenham's line algorithm." }),
      stmt({ type: 'prg32_draw_circle', message0: 'draw %1 circle x %2 y %3 radius %4 color %5', args0: [{ type: 'field_dropdown', name: 'FILL', options: [['outline', 'OUTLINE'], ['filled', 'FILLED']] }, text('X', 160), text('Y', 100), text('R', 8), color('COLOR')], colour: 160, tooltip: 'Midpoint circle algorithm.' }),
      stmt({ type: 'prg32_draw_text', message0: 'draw text %1 at x %2 y %3 fg %4 bg %5', args0: [text('TEXT', 'HELLO'), text('X', 8), text('Y', 8), color('FG'), color('BG')], colour: 160, tooltip: 'PRG32 8x8 font text.' }),
      stmt({ type: 'prg32_draw_number', message0: 'draw number %1 at x %2 y %3 fg %4 bg %5', args0: [text('VALUE', 'score'), text('X', 8), text('Y', 8), color('FG'), color('BG')], colour: 160, tooltip: 'Show a whole number (score, lives, ...).' }),
      pictureBlock('prg32_draw_bitmap', 'draw picture x %1 y %2 color %3 size %4', [text('X', 0), text('Y', 0), color('COLOR'), text('SCALE', 2)], 160, 'An 8x8 picture: # is lit, . is see-through. Size 2 makes it 16x16.', SHIP),

      // Sprites and tiles
      pictureBlock('prg32_draw_sprite8', 'draw 8x8 sprite x %1 y %2 fg %3 bg %4', [text('X', 0), text('Y', 0), color('FG'), color('BG')], 330, 'PRG32 sprite API (prg32_sprite_draw_8x8): 1-bit 8x8 sprite.', SHIP),
      pictureBlock('prg32_tile_define', 'define tile %1 fg %2 bg %3', [text('ID', 1), color('FG'), color('BG')], 330, 'PRG32 tile API (prg32_tile_define): an 8x8 tile picture with its two colours.', ['########', '#......#', '#.####.#', '#.#..#.#', '#.#..#.#', '#.####.#', '#......#', '########']),
      stmt({ type: 'prg32_playfield_clear', message0: 'fill playfield layer %1 with tile %2', args0: [text('LAYER', 0), text('ID', 0)], colour: 330, tooltip: 'Playfields are 64 x 32 tiles; layer 0 or 1.' }),
      stmt({ type: 'prg32_playfield_put', message0: 'put tile %1 on layer %2 at column %3 row %4', args0: [text('ID', 1), text('LAYER', 0), text('TX', 0), text('TY', 0)], colour: 330, tooltip: 'Read it back in any field with tile(layer, column, row).' }),
      stmt({ type: 'prg32_playfield_scroll', message0: 'scroll playfield layer %1 to x %2 y %3', args0: [text('LAYER', 0), text('X', 0), text('Y', 0)], colour: 330, tooltip: 'Pixel scroll position of one layer.' }),
      stmt({ type: 'prg32_playfield_camera', message0: 'move playfield camera to x %1 y %2', args0: [text('X', 0), text('Y', 0)], colour: 330, tooltip: 'Camera position shared by both layers.' }),
      stmt({ type: 'prg32_playfield_draw', message0: 'draw playfield layer %1 %2', args0: [text('LAYER', 0), { type: 'field_dropdown', name: 'TRANSPARENT', options: [['opaque', 'OPAQUE'], ['tile 0 see-through', 'TRANSPARENT']] }], colour: 330, tooltip: 'Draw the visible 40 x 25 tiles of a playfield layer.' }),

      // Palette
      stmt({ type: 'prg32_palette_set', message0: 'palette index %1 color %2', args0: [text('INDEX', 1), color('COLOR')], colour: 180, tooltip: 'Assign an RGB565 colour to a palette entry.' }),
      stmt({ type: 'prg32_clear_indexed', message0: 'clear screen with palette index %1', args0: [text('INDEX', 0)], colour: 180, tooltip: 'Clear with a palette index.' }),
      stmt({ type: 'prg32_draw_rect_indexed', message0: 'draw indexed rectangle x %1 y %2 w %3 h %4 index %5', args0: [text('X', 0), text('Y', 0), text('W', 16), text('H', 16), text('INDEX', 1)], colour: 180, tooltip: 'Rectangle in a palette colour.' }),
      stmt({ type: 'prg32_draw_pixel_indexed', message0: 'draw indexed pixel x %1 y %2 index %3', args0: [text('X', 0), text('Y', 0), text('INDEX', 1)], colour: 180, tooltip: 'Pixel in a palette colour.' }),

      // Sound
      stmt({ type: 'prg32_play_beep', message0: 'play beep freq %1 ms %2', args0: [text('FREQ', 880), text('MS', 80)], colour: 300, tooltip: 'Short sound on mixer channel 0.' }),
      stmt({ type: 'prg32_audio_note', message0: 'play MIDI note %1 on channel %2 for %3 ms', args0: [text('NOTE', 60), text('CHANNEL', 0), text('MS', 250)], colour: 300, tooltip: 'PRG32 mixer note with the default instrument.' }),
      stmt({ type: 'prg32_audio_stop', message0: 'stop sound on channel %1', args0: [text('CHANNEL', 0)], colour: 300, tooltip: 'prg32_audio_note_off.' }),
      stmt({ type: 'prg32_audio_volume', message0: 'set master volume to %1', args0: [text('VOLUME', 200)], colour: 300, tooltip: '0 (silent) to 255 (loudest).' }),

      // Scores and status
      stmt({ type: 'prg32_band_text', message0: 'show in status band %1 number %2', args0: [text('TEXT', 'SCORE'), text('VALUE', 'score')], colour: 60, tooltip: 'Text (and a number) in the firmware game-info band under the game. Leave number empty for text only.' }),
      stmt({ type: 'prg32_score_submit', message0: 'save high score %1', args0: [text('VALUE', 'score')], colour: 60, tooltip: 'Store a score for the current player (prg32_score_submit_current_player).' }),
      stmt({ type: 'prg32_scoreboard_show', message0: 'show scoreboard titled %1', args0: [text('TITLE', 'HIGH SCORES')], colour: 60, tooltip: 'Firmware scoreboard; waits until A, B or START is pressed.' }),
      stmt({ type: 'prg32_player_name', message0: "ask the player's name", colour: 60, tooltip: 'Firmware on-screen keyboard for the score name (prg32_score_player_prompt).' }),

      // Multiplayer
      stmt({ type: 'prg32_mp_join', message0: 'join multiplayer game', colour: 230, tooltip: 'Join the Cartridge Store relay for this game (prg32_multiplayer_join). Use it in "when game starts".' }),
      stmt({ type: 'prg32_mp_share', message0: 'share my position x %1 y %2 look %3', args0: [text('X', 'player_x'), text('Y', 'player_y'), text('LOOK', 0)], colour: 230, tooltip: 'Send your position every frame. Read others with peers(), peer_x(i), peer_y(i), peer_look(i).' }),

      // AudioStudio (docs/audio_studio.md): sounds made for this project
      stmt({ type: 'prg32_soundtrack_stop', message0: 'stop soundtrack', colour: 300, tooltip: 'The soundtrack stops; notes already playing fade out.' }),
      stmt({ type: 'prg32_sound_stop_all', message0: 'stop all sounds', colour: 300, tooltip: 'Every voice goes silent at once.' })
    ]);
    defineAudioStudioBlocks();
  }

  // The names of this project's AudioStudio sound effects and soundtracks (the editor sets them).
  let audioNames = { effects: [], soundtracks: [] };

  function setAudioNames(names) {
    audioNames = { effects: (names && names.effects) || [], soundtracks: (names && names.soundtracks) || [] };
  }

  // A dropdown of AudioStudio names that keeps a saved name even when it is not (or not yet)
  // in the list, so loading a project never changes what a block plays.
  function audioNameField(kind) {
    class AudioNameField extends Blockly.FieldDropdown {
      constructor() {
        super(function () {
          const names = audioNames[kind].slice();
          const current = this.getValue ? this.getValue() : '';
          if (current && !names.includes(current)) names.push(current);
          return names.length ? names.map(name => [name, name]) : [['(make one in AudioStudio)', '']];
        });
      }
      doClassValidation_(value) { return typeof value === 'string' ? value : null; }
      getText_() { return this.getValue() || '(make one in AudioStudio)'; }
    }
    return new AudioNameField();
  }

  function defineAudioStudioBlocks() {
    if (Blockly.Blocks.prg32_sound_effect) return;
    Blockly.Blocks.prg32_sound_effect = {
      init() {
        this.appendDummyInput().appendField('play sound effect').appendField(audioNameField('effects'), 'EFFECT');
        this.setPreviousStatement(true);
        this.setNextStatement(true);
        this.setColour(300);
        this.setTooltip('A sound effect made in AudioStudio: its instrument, note, length and voice.');
      }
    };
    Blockly.Blocks.prg32_soundtrack_play = {
      init() {
        this.appendDummyInput().appendField('play soundtrack').appendField(audioNameField('soundtracks'), 'TRACK');
        this.setPreviousStatement(true);
        this.setNextStatement(true);
        this.setColour(300);
        this.setTooltip('A soundtrack made in AudioStudio: voice N plays instrument N.');
      }
    };
  }

  const toolbox = `
  <xml xmlns="https://developers.google.com/blockly/xml">
    <category name="Game" colour="40">
      <block type="prg32_on_start"></block>
      <block type="prg32_update"></block>
      <block type="prg32_draw"></block>
      <block type="prg32_comment"></block>
      <block type="prg32_splash"></block>
    </category>
    <category name="Variables" colour="260">
      <label text="Fields accept: 3, x + 1, abs(x), min(a, b), sin(angle), random(1, 6), frame()"></label>
      <block type="prg32_set_state"></block>
      <block type="prg32_change_state"></block>
      <block type="prg32_clamp_state"></block>
      <block type="prg32_wrap_state"></block>
      <block type="prg32_random_state"></block>
    </category>
    <category name="Lists" colour="290">
      <label text="Read an item with name[position]; the first position is 0"></label>
      <block type="prg32_list_create"></block>
      <block type="prg32_list_set"></block>
      <block type="prg32_list_change"></block>
    </category>
    <category name="Logic" colour="15">
      <block type="prg32_if"></block>
      <block type="prg32_if_else"></block>
      <block type="prg32_repeat"></block>
      <block type="prg32_if_touching"></block>
    </category>
    <category name="Input" colour="20">
      <block type="prg32_if_button"></block>
      <block type="prg32_if_button_once"></block>
    </category>
    <category name="Drawing" colour="160">
      <block type="prg32_clear_screen"></block>
      <block type="prg32_draw_rect"></block>
      <block type="prg32_draw_frame"></block>
      <block type="prg32_draw_rect_rgb"></block>
      <block type="prg32_draw_pixel"></block>
      <block type="prg32_draw_line"></block>
      <block type="prg32_draw_circle"></block>
      <block type="prg32_draw_text"></block>
      <block type="prg32_draw_number"></block>
      <block type="prg32_draw_bitmap"></block>
    </category>
    <category name="Sprites &amp; Tiles" colour="330">
      <block type="prg32_draw_sprite8"></block>
      <block type="prg32_tile_define"></block>
      <block type="prg32_playfield_clear"></block>
      <block type="prg32_playfield_put"></block>
      <block type="prg32_playfield_scroll"></block>
      <block type="prg32_playfield_camera"></block>
      <block type="prg32_playfield_draw"></block>
    </category>
    <category name="Palette" colour="180">
      <block type="prg32_palette_set"></block>
      <block type="prg32_clear_indexed"></block>
      <block type="prg32_draw_rect_indexed"></block>
      <block type="prg32_draw_pixel_indexed"></block>
    </category>
    <category name="Sound" colour="300">
      <block type="prg32_play_beep"></block>
      <block type="prg32_audio_note"></block>
      <block type="prg32_audio_stop"></block>
      <block type="prg32_audio_volume"></block>
      <block type="prg32_sound_effect"></block>
      <block type="prg32_soundtrack_play"></block>
      <block type="prg32_soundtrack_stop"></block>
      <block type="prg32_sound_stop_all"></block>
    </category>
    <category name="Scores &amp; Status" colour="60">
      <block type="prg32_band_text"></block>
      <block type="prg32_score_submit"></block>
      <block type="prg32_scoreboard_show"></block>
      <block type="prg32_player_name"></block>
    </category>
    <category name="Multiplayer" colour="230">
      <label text="Other players: peers(), peer_x(i), peer_y(i), peer_look(i)"></label>
      <block type="prg32_mp_join"></block>
      <block type="prg32_mp_share"></block>
    </category>
  </xml>`;

  function init(elementId) {
    defineBlocks();
    workspace = Blockly.inject(elementId, {
      toolbox,
      trashcan: true,
      scrollbars: true,
      sounds: false,
      // Blockly's icons from the kit itself, not from a Google server (offline, CSP).
      media: '/static/vendor/blockly/11.2.1/media/',
      zoom: { controls: true, wheel: true, startScale: 0.75, maxScale: 2.0, minScale: 0.2, scaleSpeed: 1.1 },
      grid: { spacing: 20, length: 3, colour: '#d1d5db', snap: true }
    });
    return workspace;
  }

  function save() {
    if (!workspace) return {};
    return Blockly.serialization.workspaces.save(workspace);
  }

  function load(json) {
    if (!workspace) return;
    workspace.clear();
    if (json && Object.keys(json).length) {
      Blockly.serialization.workspaces.load(json, workspace);
    }
  }

  function getWorkspace() { return workspace; }

  return { init, save, load, getWorkspace, defineBlocks, setAudioNames };
})();
