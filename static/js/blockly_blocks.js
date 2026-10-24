window.PRG32Blocks = (function () {
  let workspace = null;

  const COLORS = [
    [tr('js.blockly_blocks.color_black', 'black'), 'BLACK'], [tr('js.blockly_blocks.color_white', 'white'), 'WHITE'], [tr('js.blockly_blocks.color_red', 'red'), 'RED'], [tr('js.blockly_blocks.color_green', 'green'), 'GREEN'], [tr('js.blockly_blocks.color_blue', 'blue'), 'BLUE'],
    [tr('js.blockly_blocks.color_yellow', 'yellow'), 'YELLOW'], [tr('js.blockly_blocks.color_cyan', 'cyan'), 'CYAN'], [tr('js.blockly_blocks.color_magenta', 'magenta'), 'MAGENTA'], [tr('js.blockly_blocks.color_orange', 'orange'), 'ORANGE'], [tr('js.blockly_blocks.color_pink', 'pink'), 'PINK'],
    [tr('js.blockly_blocks.color_gray', 'gray'), 'GRAY'], [tr('js.blockly_blocks.dark_gray', 'dark gray'), 'DARK_GRAY'], [tr('js.blockly_blocks.color_brown', 'brown'), 'BROWN'], [tr('js.blockly_blocks.color_purple', 'purple'), 'PURPLE'], [tr('js.blockly_blocks.color_navy', 'navy'), 'NAVY'], [tr('js.blockly_blocks.color_lime', 'lime'), 'LIME']
  ];
  const BUTTONS = [[tr('js.blockly_blocks.button_left', 'left'), 'LEFT'], [tr('js.blockly_blocks.button_right', 'right'), 'RIGHT'], [tr('js.blockly_blocks.button_up', 'up'), 'UP'], [tr('js.blockly_blocks.button_down', 'down'), 'DOWN'], ['A', 'A'], ['B', 'B'], [tr('js.blockly_blocks.button_start', 'start'), 'START'], [tr('js.blockly_blocks.button_select', 'select'), 'SELECT'],
    [tr('js.blockly_blocks.player_2_left', 'player 2 left'), 'P2_LEFT'], [tr('js.blockly_blocks.player_2_right', 'player 2 right'), 'P2_RIGHT'], [tr('js.blockly_blocks.player_2_up', 'player 2 up'), 'P2_UP'], [tr('js.blockly_blocks.player_2_down', 'player 2 down'), 'P2_DOWN'], ['player 2 A', 'P2_A'], ['player 2 B', 'P2_B']];

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
      { type: 'prg32_on_start', message0: tr('js.blockly_blocks.when_game_starts_1_2', 'when game starts %1 %2'), args0: [{ type: 'input_dummy' }, { type: 'input_statement', name: 'DO' }], colour: 40, tooltip: tr('js.blockly_blocks.runs_once_when_starts', 'Runs once when the cartridge starts (C: <prefix>_init).') },
      { type: 'prg32_update', message0: tr('js.blockly_blocks.every_frame_update_1_2', 'every frame update %1 %2'), args0: [{ type: 'input_dummy' }, { type: 'input_statement', name: 'DO' }], colour: 210, tooltip: tr('js.blockly_blocks.runs_game_logic', 'Runs game logic once per frame (C: <prefix>_update).') },
      { type: 'prg32_draw', message0: tr('js.blockly_blocks.every_frame_draw_1_2', 'every frame draw %1 %2'), args0: [{ type: 'input_dummy' }, { type: 'input_statement', name: 'DO' }], colour: 160, tooltip: tr('js.blockly_blocks.draws_the_frame', 'Draws the frame once per frame (C: <prefix>_draw).') },
      stmt({ type: 'prg32_comment', message0: tr('js.blockly_blocks.comment_1', 'comment %1'), args0: [text('TEXT', tr('js.blockly_blocks.explain_this_idea', 'explain this idea'))], colour: 90, tooltip: tr('js.blockly_blocks.a_note_for_students_it_becomes', 'A note for students; it becomes a C comment.') }),
      stmt({ type: 'prg32_splash', message0: tr('js.blockly_blocks.show_splash_title_1_subtitle_2', 'show splash title %1 subtitle %2 for %3 ms background %4 text %5 accent %6'), args0: [text('TITLE', 'MY GAME'), text('SUBTITLE', 'PRESS START'), text('MS', 1500), color('BG'), color('FG'), color('ACCENT')], colour: 40, tooltip: tr('js.blockly_blocks.prg32_splash_screen_prg32_splash_show', 'PRG32 splash screen (prg32_splash_show_game). Use it in "when game starts".') }),

      // Variables
      stmt({ type: 'prg32_set_state', message0: tr('js.blockly_blocks.set_1_to_2', 'set %1 to %2'), args0: [text('VAR', 'score'), text('VALUE', 0)], colour: 260, tooltip: tr('js.blockly_blocks.create_or_assign_a_whole_number', 'Create or assign a whole-number variable.') }),
      stmt({ type: 'prg32_change_state', message0: tr('js.blockly_blocks.change_1_by_2', 'change %1 by %2'), args0: [text('VAR', 'score'), text('DELTA', 1)], colour: 260, tooltip: tr('js.blockly_blocks.add_a_number_to_a_variable', 'Add a number to a variable.') }),
      stmt({ type: 'prg32_clamp_state', message0: tr('js.blockly_blocks.keep_1_between_2_and_3', 'keep %1 between %2 and %3'), args0: [text('VAR', 'player_x'), text('LOW', 0), text('HIGH', 304)], colour: 260, tooltip: tr('js.blockly_blocks.clamp_a_variable_to_a_safe', 'Clamp a variable to a safe range.') }),
      stmt({ type: 'prg32_wrap_state', message0: tr('js.blockly_blocks.wrap_1_around_2_to_3', 'wrap %1 around %2 to %3'), args0: [text('VAR', 'ship_x'), text('LOW', 0), text('HIGH', 319)], colour: 260, tooltip: tr('js.blockly_blocks.leaving_one_side_brings_the_value', 'Leaving one side brings the value back on the other side.') }),
      stmt({ type: 'prg32_random_state', message0: tr('js.blockly_blocks.set_1_to_random_from_2', 'set %1 to random from %2 to %3'), args0: [text('VAR', 'target_x'), text('LOW', 0), text('HIGH', 304)], colour: 260, tooltip: tr('js.blockly_blocks.inclusive_prg32_random_whole_number', 'Inclusive PRG32 random whole number.') }),

      // Lists
      stmt({ type: 'prg32_list_create', message0: tr('js.blockly_blocks.make_list_1_with_2_items', 'make list %1 with %2 items, all %3'), args0: [text('LIST', 'bricks'), text('SIZE', 10), text('VALUE', 0)], colour: 290, tooltip: tr('js.blockly_blocks.a_list_of_whole_numbers_1', 'A list of whole numbers (1 to 1024 items). Read an item in any field with name[position]; positions start at 0.') }),
      stmt({ type: 'prg32_list_set', message0: tr('js.blockly_blocks.set_item_1_of_2_to', 'set item %1 of %2 to %3'), args0: [text('INDEX', 0), text('LIST', 'bricks'), text('VALUE', 1)], colour: 290, tooltip: tr('js.blockly_blocks.positions_outside_the_list_are_ignored', 'Positions outside the list are ignored.') }),
      stmt({ type: 'prg32_list_change', message0: tr('js.blockly_blocks.change_item_1_of_2_by', 'change item %1 of %2 by %3'), args0: [text('INDEX', 0), text('LIST', 'bricks'), text('DELTA', 1)], colour: 290, tooltip: tr('js.blockly_blocks.add_a_number_to_one_item', 'Add a number to one item.') }),

      // Logic
      stmt({ type: 'prg32_if', message0: tr('js.blockly_blocks.if_1_2_3', 'if %1 %2 %3'), args0: [text('COND', 'score > 9'), { type: 'input_dummy' }, { type: 'input_statement', name: 'DO' }], colour: 15, tooltip: tr('js.blockly_blocks.runs_the_blocks_inside_when_the', 'Runs the blocks inside when the condition is not 0.') }),
      stmt({ type: 'prg32_if_else', message0: tr('js.blockly_blocks.if_1_2_3_else_4', 'if %1 %2 %3 else %4'), args0: [text('COND', 'lives > 0'), { type: 'input_dummy' }, { type: 'input_statement', name: 'DO' }, { type: 'input_statement', name: 'ELSE' }], colour: 15, tooltip: tr('js.blockly_blocks.choose_between_two_groups_of_blocks', 'Choose between two groups of blocks.') }),
      stmt({ type: 'prg32_repeat', message0: tr('js.blockly_blocks.repeat_with_1_from_2_to', 'repeat with %1 from %2 to %3 %4 %5'), args0: [text('VAR', 'i'), text('FROM', 0), text('TO', 9), { type: 'input_dummy' }, { type: 'input_statement', name: 'DO' }], colour: 15, tooltip: tr('js.blockly_blocks.counts_from_the_first_number_to', 'Counts from the first number to the last (at most 1024 times).') }),
      stmt({ type: 'prg32_if_touching', message0: tr('js.blockly_blocks.if_rect_1_2_3_4', 'if rect %1 %2 %3 %4 touches rect %5 %6 %7 %8 %9 %10'), args0: [
        text('AX', 'player_x'), text('AY', 'player_y'), text('AW', 16), text('AH', 16),
        text('BX', 'enemy_x'), text('BY', 'enemy_y'), text('BW', 16), text('BH', 16),
        { type: 'input_dummy' }, { type: 'input_statement', name: 'DO' }
      ], colour: 15, tooltip: tr('js.blockly_blocks.prg32_rectangle_hitbox_collision_prg32_s', 'PRG32 rectangle hitbox collision (prg32_sprite_hitbox): x, y, width, height.') }),

      // Input
      stmt({ type: 'prg32_if_button', message0: tr('js.blockly_blocks.if_button_1_is_held_2', 'if button %1 is held %2 %3'), args0: [{ type: 'field_dropdown', name: 'BUTTON', options: BUTTONS }, { type: 'input_dummy' }, { type: 'input_statement', name: 'DO' }], colour: 20, tooltip: tr('js.blockly_blocks.runs_every_frame_while_the_button', 'Runs every frame while the button is down.') }),
      stmt({ type: 'prg32_if_button_once', message0: tr('js.blockly_blocks.if_button_1_was_just_pressed', 'if button %1 was just pressed %2 %3'), args0: [{ type: 'field_dropdown', name: 'BUTTON', options: BUTTONS }, { type: 'input_dummy' }, { type: 'input_statement', name: 'DO' }], colour: 20, tooltip: tr('js.blockly_blocks.runs_once_per_press_edge_detection', 'Runs once per press (edge detection).') }),

      // Drawing
      stmt({ type: 'prg32_clear_screen', message0: tr('js.blockly_blocks.clear_screen_1', 'clear screen %1'), args0: [color('COLOR')], colour: 160, tooltip: tr('js.blockly_blocks.fill_the_320x200_prg32_game_viewport', 'Fill the 320x200 PRG32 game viewport.') }),
      stmt({ type: 'prg32_draw_rect', message0: tr('js.blockly_blocks.draw_rectangle_x_1_y_2', 'draw rectangle x %1 y %2 w %3 h %4 color %5'), args0: [text('X', 0), text('Y', 0), text('W', 16), text('H', 16), color('COLOR')], colour: 160, tooltip: tr('js.blockly_blocks.filled_rectangle', 'Filled rectangle.') }),
      stmt({ type: 'prg32_draw_frame', message0: tr('js.blockly_blocks.draw_outline_x_1_y_2', 'draw outline x %1 y %2 w %3 h %4 color %5'), args0: [text('X', 0), text('Y', 0), text('W', 16), text('H', 16), color('COLOR')], colour: 160, tooltip: tr('js.blockly_blocks.rectangle_border_only', 'Rectangle border only.') }),
      stmt({ type: 'prg32_draw_rect_rgb', message0: tr('js.blockly_blocks.draw_rectangle_x_1_y_2_2', 'draw rectangle x %1 y %2 w %3 h %4 color value %5'), args0: [text('X', 0), text('Y', 0), text('W', 16), text('H', 16), text('RGB', 'rgb(255, 128, 0)')], colour: 160, tooltip: tr('js.blockly_blocks.colour_from_an_expression_rgb_r', 'Colour from an expression: rgb(r, g, b) or an RGB565 number.') }),
      stmt({ type: 'prg32_draw_pixel', message0: tr('js.blockly_blocks.draw_pixel_x_1_y_2', 'draw pixel x %1 y %2 color %3'), args0: [text('X', 0), text('Y', 0), color('COLOR')], colour: 160, tooltip: tr('js.blockly_blocks.one_pixel', 'One pixel.') }),
      stmt({ type: 'prg32_draw_line', message0: tr('js.blockly_blocks.draw_line_from_x_1_y', 'draw line from x %1 y %2 to x %3 y %4 color %5'), args0: [text('X1', 0), text('Y1', 0), text('X2', 16), text('Y2', 16), color('COLOR')], colour: 160, tooltip: "Bresenham's line algorithm." }),
      stmt({ type: 'prg32_draw_circle', message0: tr('js.blockly_blocks.draw_1_circle_x_2_y', 'draw %1 circle x %2 y %3 radius %4 color %5'), args0: [{ type: 'field_dropdown', name: 'FILL', options: [[tr('js.blockly_blocks.outline', 'outline'), 'OUTLINE'], [tr('js.blockly_blocks.filled', 'filled'), 'FILLED']] }, text('X', 160), text('Y', 100), text('R', 8), color('COLOR')], colour: 160, tooltip: tr('js.blockly_blocks.midpoint_circle_algorithm', 'Midpoint circle algorithm.') }),
      stmt({ type: 'prg32_draw_text', message0: tr('js.blockly_blocks.draw_text_1_at_x_2', 'draw text %1 at x %2 y %3 fg %4 bg %5'), args0: [text('TEXT', 'HELLO'), text('X', 8), text('Y', 8), color('FG'), color('BG')], colour: 160, tooltip: tr('js.blockly_blocks.prg32_8x8_font_text', 'PRG32 8x8 font text.') }),
      stmt({ type: 'prg32_draw_number', message0: tr('js.blockly_blocks.draw_number_1_at_x_2', 'draw number %1 at x %2 y %3 fg %4 bg %5'), args0: [text('VALUE', 'score'), text('X', 8), text('Y', 8), color('FG'), color('BG')], colour: 160, tooltip: tr('js.blockly_blocks.show_a_whole_number_score_lives', 'Show a whole number (score, lives, ...).') }),
      pictureBlock('prg32_draw_bitmap', tr('js.blockly_blocks.draw_picture_x_1_y_2', 'draw picture x %1 y %2 color %3 size %4'), [text('X', 0), text('Y', 0), color('COLOR'), text('SCALE', 2)], 160, tr('js.blockly_blocks.an_8x8_picture_is_lit_is', 'An 8x8 picture: # is lit, . is see-through. Size 2 makes it 16x16.'), SHIP),

      // Sprites and tiles
      pictureBlock('prg32_draw_sprite8', tr('js.blockly_blocks.draw_8x8_sprite_x_1_y', 'draw 8x8 sprite x %1 y %2 fg %3 bg %4'), [text('X', 0), text('Y', 0), color('FG'), color('BG')], 330, tr('js.blockly_blocks.prg32_sprite_api_prg32_sprite_draw', 'PRG32 sprite API (prg32_sprite_draw_8x8): 1-bit 8x8 sprite.'), SHIP),
      pictureBlock('prg32_tile_define', tr('js.blockly_blocks.define_tile_1_fg_2_bg', 'define tile %1 fg %2 bg %3'), [text('ID', 1), color('FG'), color('BG')], 330, tr('js.blockly_blocks.prg32_tile_api_prg32_tile_define', 'PRG32 tile API (prg32_tile_define): an 8x8 tile picture with its two colours.'), ['########', '#......#', '#.####.#', '#.#..#.#', '#.#..#.#', '#.####.#', '#......#', '########']),
      stmt({ type: 'prg32_playfield_clear', message0: tr('js.blockly_blocks.fill_playfield_layer_1_with_tile', 'fill playfield layer %1 with tile %2'), args0: [text('LAYER', 0), text('ID', 0)], colour: 330, tooltip: tr('js.blockly_blocks.playfields_are_64_x_32_tiles', 'Playfields are 64 x 32 tiles; layer 0 or 1.') }),
      stmt({ type: 'prg32_playfield_put', message0: tr('js.blockly_blocks.put_tile_1_on_layer_2', 'put tile %1 on layer %2 at column %3 row %4'), args0: [text('ID', 1), text('LAYER', 0), text('TX', 0), text('TY', 0)], colour: 330, tooltip: tr('js.blockly_blocks.read_it_back_in_any_field', 'Read it back in any field with tile(layer, column, row).') }),
      stmt({ type: 'prg32_playfield_scroll', message0: tr('js.blockly_blocks.scroll_playfield_layer_1_to_x', 'scroll playfield layer %1 to x %2 y %3'), args0: [text('LAYER', 0), text('X', 0), text('Y', 0)], colour: 330, tooltip: tr('js.blockly_blocks.pixel_scroll_position_of_one_layer', 'Pixel scroll position of one layer.') }),
      stmt({ type: 'prg32_playfield_camera', message0: tr('js.blockly_blocks.move_playfield_camera_to_x_1', 'move playfield camera to x %1 y %2'), args0: [text('X', 0), text('Y', 0)], colour: 330, tooltip: tr('js.blockly_blocks.camera_position_shared_by_both_layers', 'Camera position shared by both layers.') }),
      stmt({ type: 'prg32_playfield_draw', message0: tr('js.blockly_blocks.draw_playfield_layer_1_2', 'draw playfield layer %1 %2'), args0: [text('LAYER', 0), { type: 'field_dropdown', name: 'TRANSPARENT', options: [[tr('js.blockly_blocks.opaque', 'opaque'), 'OPAQUE'], [tr('js.blockly_blocks.tile_0_see_through', 'tile 0 see-through'), 'TRANSPARENT']] }], colour: 330, tooltip: tr('js.blockly_blocks.draw_the_visible_40_x_25', 'Draw the visible 40 x 25 tiles of a playfield layer.') }),

      // Palette
      stmt({ type: 'prg32_palette_set', message0: tr('js.blockly_blocks.palette_index_1_color_2', 'palette index %1 color %2'), args0: [text('INDEX', 1), color('COLOR')], colour: 180, tooltip: tr('js.blockly_blocks.assign_an_rgb565_colour_to_a', 'Assign an RGB565 colour to a palette entry.') }),
      stmt({ type: 'prg32_clear_indexed', message0: tr('js.blockly_blocks.clear_screen_with_palette_index_1', 'clear screen with palette index %1'), args0: [text('INDEX', 0)], colour: 180, tooltip: tr('js.blockly_blocks.clear_with_a_palette_index', 'Clear with a palette index.') }),
      stmt({ type: 'prg32_draw_rect_indexed', message0: tr('js.blockly_blocks.draw_indexed_rectangle_x_1_y', 'draw indexed rectangle x %1 y %2 w %3 h %4 index %5'), args0: [text('X', 0), text('Y', 0), text('W', 16), text('H', 16), text('INDEX', 1)], colour: 180, tooltip: tr('js.blockly_blocks.rectangle_in_a_palette_colour', 'Rectangle in a palette colour.') }),
      stmt({ type: 'prg32_draw_pixel_indexed', message0: tr('js.blockly_blocks.draw_indexed_pixel_x_1_y', 'draw indexed pixel x %1 y %2 index %3'), args0: [text('X', 0), text('Y', 0), text('INDEX', 1)], colour: 180, tooltip: tr('js.blockly_blocks.pixel_in_a_palette_colour', 'Pixel in a palette colour.') }),

      // Sound
      stmt({ type: 'prg32_play_beep', message0: tr('js.blockly_blocks.play_beep_freq_1_ms_2', 'play beep freq %1 ms %2'), args0: [text('FREQ', 880), text('MS', 80)], colour: 300, tooltip: tr('js.blockly_blocks.short_sound_on_mixer_channel_0', 'Short sound on mixer channel 0.') }),
      stmt({ type: 'prg32_audio_note', message0: tr('js.blockly_blocks.play_midi_note_1_on_channel', 'play MIDI note %1 on channel %2 for %3 ms'), args0: [text('NOTE', 60), text('CHANNEL', 0), text('MS', 250)], colour: 300, tooltip: tr('js.blockly_blocks.prg32_mixer_note_with_the_default', 'PRG32 mixer note with the default instrument.') }),
      stmt({ type: 'prg32_audio_stop', message0: tr('js.blockly_blocks.stop_sound_on_channel_1', 'stop sound on channel %1'), args0: [text('CHANNEL', 0)], colour: 300, tooltip: 'prg32_audio_note_off.' }),
      stmt({ type: 'prg32_audio_volume', message0: tr('js.blockly_blocks.set_master_volume_to_1', 'set master volume to %1'), args0: [text('VOLUME', 200)], colour: 300, tooltip: tr('js.blockly_blocks.0_silent_to_255_loudest', '0 (silent) to 255 (loudest).') }),

      // Scores and status
      stmt({ type: 'prg32_band_text', message0: tr('js.blockly_blocks.show_in_status_band_1_number', 'show in status band %1 number %2'), args0: [text('TEXT', 'SCORE'), text('VALUE', 'score')], colour: 60, tooltip: tr('js.blockly_blocks.text_and_a_number_in_the', 'Text (and a number) in the firmware game-info band under the game. Leave number empty for text only.') }),
      stmt({ type: 'prg32_score_submit', message0: tr('js.blockly_blocks.save_high_score_1', 'save high score %1'), args0: [text('VALUE', 'score')], colour: 60, tooltip: tr('js.blockly_blocks.store_a_score_for_the_current', 'Store a score for the current player (prg32_score_submit_current_player).') }),
      stmt({ type: 'prg32_scoreboard_show', message0: tr('js.blockly_blocks.show_scoreboard_titled_1', 'show scoreboard titled %1'), args0: [text('TITLE', 'HIGH SCORES')], colour: 60, tooltip: tr('js.blockly_blocks.firmware_scoreboard_waits_until_a_b', 'Firmware scoreboard; waits until A, B or START is pressed.') }),
      stmt({ type: 'prg32_player_name', message0: "ask the player's name", colour: 60, tooltip: tr('js.blockly_blocks.firmware_on_screen_keyboard_for_the', 'Firmware on-screen keyboard for the score name (prg32_score_player_prompt).') }),

      // Multiplayer
      stmt({ type: 'prg32_mp_join', message0: tr('js.blockly_blocks.join_multiplayer_game', 'join multiplayer game'), colour: 230, tooltip: tr('js.blockly_blocks.join_the_cartridge_store_relay_for', 'Join the Cartridge Store relay for this game (prg32_multiplayer_join). Use it in "when game starts".') }),
      stmt({ type: 'prg32_mp_share', message0: tr('js.blockly_blocks.share_my_position_x_1_y', 'share my position x %1 y %2 look %3'), args0: [text('X', 'player_x'), text('Y', 'player_y'), text('LOOK', 0)], colour: 230, tooltip: tr('js.blockly_blocks.send_your_position_every_frame_read', 'Send your position every frame. Read others with peers(), peer_x(i), peer_y(i), peer_look(i).') }),

      // AudioStudio (docs/audio_studio.md): sounds made for this project
      stmt({ type: 'prg32_soundtrack_stop', message0: tr('js.blockly_blocks.stop_soundtrack', 'stop soundtrack'), colour: 300, tooltip: tr('js.blockly_blocks.the_soundtrack_stops_notes_already_playi', 'The soundtrack stops; notes already playing fade out.') }),
      stmt({ type: 'prg32_sound_stop_all', message0: tr('js.blockly_blocks.stop_all_sounds', 'stop all sounds'), colour: 300, tooltip: tr('js.blockly_blocks.every_voice_goes_silent_at_once', 'Every voice goes silent at once.') })
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
          return names.length ? names.map(name => [name, name]) : [[tr('js.blockly_blocks.make_one_in_audiostudio', '(make one in AudioStudio)'), '']];
        });
      }
      doClassValidation_(value) { return typeof value === 'string' ? value : null; }
      getText_() { return this.getValue() || tr('js.blockly_blocks.make_one_in_audiostudio', '(make one in AudioStudio)'); }
    }
    return new AudioNameField();
  }

  function defineAudioStudioBlocks() {
    if (Blockly.Blocks.prg32_sound_effect) return;
    Blockly.Blocks.prg32_sound_effect = {
      init() {
        this.appendDummyInput().appendField(tr('js.blockly_blocks.play_sound_effect', 'play sound effect')).appendField(audioNameField('effects'), 'EFFECT');
        this.setPreviousStatement(true);
        this.setNextStatement(true);
        this.setColour(300);
        this.setTooltip(tr('js.blockly_blocks.a_sound_effect_made_in_audiostudio', 'A sound effect made in AudioStudio: its instrument, note, length and voice.'));
      }
    };
    Blockly.Blocks.prg32_soundtrack_play = {
      init() {
        this.appendDummyInput().appendField(tr('js.blockly_blocks.play_soundtrack', 'play soundtrack')).appendField(audioNameField('soundtracks'), 'TRACK');
        this.setPreviousStatement(true);
        this.setNextStatement(true);
        this.setColour(300);
        this.setTooltip(tr('js.blockly_blocks.a_soundtrack_made_in_audiostudio_voice', 'A soundtrack made in AudioStudio: voice N plays instrument N.'));
      }
    };
  }

  // Text put into the toolbox XML (category names, hints): escaped for an XML attribute.
  const xml = value => String(value).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
  const toolbox = `
  <xml xmlns="https://developers.google.com/blockly/xml">
    <category name="${xml(tr('js.blockly_blocks.category_game', 'Game'))}" colour="40">
      <block type="prg32_on_start"></block>
      <block type="prg32_update"></block>
      <block type="prg32_draw"></block>
      <block type="prg32_comment"></block>
      <block type="prg32_splash"></block>
    </category>
    <category name="${xml(tr('js.blockly_blocks.category_variables', 'Variables'))}" colour="260">
      <label text="${xml(tr('js.blockly_blocks.label_fields_accept_3_x_1_abs', 'Fields accept: 3, x + 1, abs(x), min(a, b), sin(angle), random(1, 6), frame()'))}"></label>
      <block type="prg32_set_state"></block>
      <block type="prg32_change_state"></block>
      <block type="prg32_clamp_state"></block>
      <block type="prg32_wrap_state"></block>
      <block type="prg32_random_state"></block>
    </category>
    <category name="${xml(tr('js.blockly_blocks.category_lists', 'Lists'))}" colour="290">
      <label text="${xml(tr('js.blockly_blocks.label_read_an_item_with_name_position', 'Read an item with name[position]; the first position is 0'))}"></label>
      <block type="prg32_list_create"></block>
      <block type="prg32_list_set"></block>
      <block type="prg32_list_change"></block>
    </category>
    <category name="${xml(tr('js.blockly_blocks.category_logic', 'Logic'))}" colour="15">
      <block type="prg32_if"></block>
      <block type="prg32_if_else"></block>
      <block type="prg32_repeat"></block>
      <block type="prg32_if_touching"></block>
    </category>
    <category name="${xml(tr('js.blockly_blocks.category_input', 'Input'))}" colour="20">
      <block type="prg32_if_button"></block>
      <block type="prg32_if_button_once"></block>
    </category>
    <category name="${xml(tr('js.blockly_blocks.category_drawing', 'Drawing'))}" colour="160">
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
    <category name="${xml(tr('js.blockly_blocks.category_sprites_tiles', 'Sprites & Tiles'))}" colour="330">
      <block type="prg32_draw_sprite8"></block>
      <block type="prg32_tile_define"></block>
      <block type="prg32_playfield_clear"></block>
      <block type="prg32_playfield_put"></block>
      <block type="prg32_playfield_scroll"></block>
      <block type="prg32_playfield_camera"></block>
      <block type="prg32_playfield_draw"></block>
    </category>
    <category name="${xml(tr('js.blockly_blocks.category_palette', 'Palette'))}" colour="180">
      <block type="prg32_palette_set"></block>
      <block type="prg32_clear_indexed"></block>
      <block type="prg32_draw_rect_indexed"></block>
      <block type="prg32_draw_pixel_indexed"></block>
    </category>
    <category name="${xml(tr('js.blockly_blocks.category_sound', 'Sound'))}" colour="300">
      <block type="prg32_play_beep"></block>
      <block type="prg32_audio_note"></block>
      <block type="prg32_audio_stop"></block>
      <block type="prg32_audio_volume"></block>
      <block type="prg32_sound_effect"></block>
      <block type="prg32_soundtrack_play"></block>
      <block type="prg32_soundtrack_stop"></block>
      <block type="prg32_sound_stop_all"></block>
    </category>
    <category name="${xml(tr('js.blockly_blocks.category_scores_status', 'Scores & Status'))}" colour="60">
      <block type="prg32_band_text"></block>
      <block type="prg32_score_submit"></block>
      <block type="prg32_scoreboard_show"></block>
      <block type="prg32_player_name"></block>
    </category>
    <category name="${xml(tr('js.blockly_blocks.category_multiplayer', 'Multiplayer'))}" colour="230">
      <label text="${xml(tr('js.blockly_blocks.label_other_players_peers_peer_x_i', 'Other players: peers(), peer_x(i), peer_y(i), peer_look(i)'))}"></label>
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
