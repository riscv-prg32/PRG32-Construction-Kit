window.PRG32Blocks = (function () {
  let workspace = null;

  const COLORS = [
    ['black', 'BLACK'], ['white', 'WHITE'], ['red', 'RED'], ['green', 'GREEN'], ['blue', 'BLUE'],
    ['yellow', 'YELLOW'], ['cyan', 'CYAN'], ['magenta', 'MAGENTA'], ['orange', 'ORANGE'], ['pink', 'PINK']
  ];
  const BUTTONS = [['left', 'LEFT'], ['right', 'RIGHT'], ['up', 'UP'], ['down', 'DOWN'], ['A', 'A'], ['B', 'B'], ['start', 'START'], ['select', 'SELECT']];

  function defineBlocks() {
    if (Blockly.Blocks.prg32_on_start) return;
    Blockly.common.defineBlocksWithJsonArray([
      { type: 'prg32_on_start', message0: 'when game starts %1 %2', args0: [{ type: 'input_dummy' }, { type: 'input_statement', name: 'DO' }], colour: 40, tooltip: 'Runs once when the cartridge starts.' },
      { type: 'prg32_update', message0: 'every frame update %1 %2', args0: [{ type: 'input_dummy' }, { type: 'input_statement', name: 'DO' }], colour: 210, tooltip: 'Runs game logic once per frame.' },
      { type: 'prg32_draw', message0: 'every frame draw %1 %2', args0: [{ type: 'input_dummy' }, { type: 'input_statement', name: 'DO' }], colour: 160, tooltip: 'Draws the frame once per frame.' },
      { type: 'prg32_set_state', message0: 'set %1 to %2', args0: [{ type: 'field_input', name: 'VAR', text: 'score' }, { type: 'field_input', name: 'VALUE', text: '0' }], previousStatement: null, nextStatement: null, colour: 260, tooltip: 'Create or assign an integer state variable.' },
      { type: 'prg32_change_state', message0: 'change %1 by %2', args0: [{ type: 'field_input', name: 'VAR', text: 'score' }, { type: 'field_input', name: 'DELTA', text: '1' }], previousStatement: null, nextStatement: null, colour: 260, tooltip: 'Add a number to an integer state variable.' },
      { type: 'prg32_clamp_state', message0: 'keep %1 between %2 and %3', args0: [{ type: 'field_input', name: 'VAR', text: 'player_x' }, { type: 'field_input', name: 'LOW', text: '0' }, { type: 'field_input', name: 'HIGH', text: '304' }], previousStatement: null, nextStatement: null, colour: 260, tooltip: 'Clamp a variable to a safe range.' },
      { type: 'prg32_if_button', message0: 'if button %1 pressed %2 %3', args0: [{ type: 'field_dropdown', name: 'BUTTON', options: BUTTONS }, { type: 'input_dummy' }, { type: 'input_statement', name: 'DO' }], previousStatement: null, nextStatement: null, colour: 15, tooltip: 'Run blocks when a PRG32 button is pressed.' },
      { type: 'prg32_if_touching', message0: 'if rect %1 %2 %3 %4 touches rect %5 %6 %7 %8 %9 %10', args0: [
        { type: 'field_input', name: 'AX', text: 'player_x' }, { type: 'field_input', name: 'AY', text: 'player_y' }, { type: 'field_input', name: 'AW', text: '16' }, { type: 'field_input', name: 'AH', text: '16' },
        { type: 'field_input', name: 'BX', text: 'enemy_x' }, { type: 'field_input', name: 'BY', text: 'enemy_y' }, { type: 'field_input', name: 'BW', text: '16' }, { type: 'field_input', name: 'BH', text: '16' },
        { type: 'input_dummy' }, { type: 'input_statement', name: 'DO' }
      ], previousStatement: null, nextStatement: null, colour: 15, tooltip: 'Use PRG32 rectangle hitbox collision.' },
      { type: 'prg32_clear_screen', message0: 'clear screen %1', args0: [{ type: 'field_dropdown', name: 'COLOR', options: COLORS }], previousStatement: null, nextStatement: null, colour: 160, tooltip: 'Fill the PRG32 viewport.' },
      { type: 'prg32_draw_rect', message0: 'draw rectangle x %1 y %2 w %3 h %4 color %5', args0: [{ type: 'field_input', name: 'X', text: '0' }, { type: 'field_input', name: 'Y', text: '0' }, { type: 'field_input', name: 'W', text: '16' }, { type: 'field_input', name: 'H', text: '16' }, { type: 'field_dropdown', name: 'COLOR', options: COLORS }], previousStatement: null, nextStatement: null, colour: 160, tooltip: 'Draw a filled rectangle.' },
      { type: 'prg32_draw_text', message0: 'draw text %1 at x %2 y %3 fg %4 bg %5', args0: [{ type: 'field_input', name: 'TEXT', text: 'HELLO' }, { type: 'field_input', name: 'X', text: '8' }, { type: 'field_input', name: 'Y', text: '8' }, { type: 'field_dropdown', name: 'FG', options: COLORS }, { type: 'field_dropdown', name: 'BG', options: COLORS }], previousStatement: null, nextStatement: null, colour: 160, tooltip: 'Draw 8x8 text.' },
      { type: 'prg32_play_beep', message0: 'play beep freq %1 ms %2', args0: [{ type: 'field_input', name: 'FREQ', text: '880' }, { type: 'field_input', name: 'MS', text: '80' }], previousStatement: null, nextStatement: null, colour: 300, tooltip: 'Play a short sound.' },
      { type: 'prg32_comment', message0: 'comment %1', args0: [{ type: 'field_input', name: 'TEXT', text: 'explain this idea' }], previousStatement: null, nextStatement: null, colour: 90, tooltip: 'A note for students and generated C.' }
    ]);
  }

  const toolbox = `
  <xml xmlns="https://developers.google.com/blockly/xml">
    <category name="Game" colour="40">
      <block type="prg32_on_start"></block>
      <block type="prg32_update"></block>
      <block type="prg32_draw"></block>
      <block type="prg32_comment"></block>
    </category>
    <category name="State" colour="260">
      <block type="prg32_set_state"></block>
      <block type="prg32_change_state"></block>
      <block type="prg32_clamp_state"></block>
    </category>
    <category name="Input & Logic" colour="15">
      <block type="prg32_if_button"></block>
      <block type="prg32_if_touching"></block>
    </category>
    <category name="Drawing" colour="160">
      <block type="prg32_clear_screen"></block>
      <block type="prg32_draw_rect"></block>
      <block type="prg32_draw_text"></block>
    </category>
    <category name="Audio" colour="300">
      <block type="prg32_play_beep"></block>
    </category>
  </xml>`;

  function init(elementId) {
    defineBlocks();
    workspace = Blockly.inject(elementId, {
      toolbox,
      trashcan: true,
      scrollbars: true,
      sounds: false,
      zoom: { controls: true, wheel: true, startScale: 0.88, maxScale: 2.0, minScale: 0.35, scaleSpeed: 1.1 },
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

  return { init, save, load, getWorkspace, defineBlocks };
})();
