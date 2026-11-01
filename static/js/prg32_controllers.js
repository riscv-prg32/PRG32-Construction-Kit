// Game controllers and the on-screen stick, for the Player and the quick Blocks preview.
//
// PRG32 has one player per console: every controller plugged into this computer drives that one
// player (a second player is a second console, through multiplayer). Nothing here leaves the
// browser and nothing is stored. See docs/game_controllers.md.
//
// The stick follows the firmware's rules (components/prg32/prg32_joystick_analog.c), so a game
// feels the same here and on a console with an analog stick:
//   - an axis runs from -127 (left, up) to 127 (right, down) and reads 0 at rest;
//   - small movements near the middle (the deadzone) read 0, so a released stick does not drift;
//   - a direction button turns on at a tilt of 40 and off below 24, so a stick held near that
//     tilt does not flicker.
window.PRG32Controllers = (function () {
  'use strict';

  const BITS = { LEFT: 1, RIGHT: 2, UP: 4, DOWN: 8, A: 16, B: 32, SELECT: 64, C: 128, D: 256, L: 512, R: 1024 };
  const FULL_SCALE = 127;
  const DEADZONE = 12;       // CONFIG_PRG32_JOYSTICK_AXIS_DEADZONE
  const TURN_ON = 40;        // CONFIG_PRG32_JOYSTICK_DIRECTION_THRESHOLD
  const TURN_OFF = 24;       // three fifths of it, as in the firmware

  // Browsers number the buttons of a "standard" controller by position, whatever is printed on them.
  // The four action buttons and the bumpers are the same ones PRG32-QT uses.
  const STANDARD_BUTTONS = {
    0: BITS.A, 1: BITS.B, 2: BITS.C, 3: BITS.D,    // bottom, right, left, top
    4: BITS.L, 5: BITS.R, 6: BITS.L, 7: BITS.R,    // bumpers, and the triggers behind them
    8: BITS.SELECT, 9: BITS.SELECT,                // back/view and start/menu
    12: BITS.UP, 13: BITS.DOWN, 14: BITS.LEFT, 15: BITS.RIGHT   // the cross
  };
  // Any other controller: its first six buttons in order, the rest as Select (as PRG32-QT does).
  const OTHER_BUTTONS = {
    0: BITS.A, 1: BITS.B, 2: BITS.C, 3: BITS.D, 4: BITS.L, 5: BITS.R,
    6: BITS.SELECT, 7: BITS.SELECT, 8: BITS.SELECT, 9: BITS.SELECT
  };

  // One axis of a controller (-1..1) in the firmware's units, with the deadzone taken out.
  function axisValue(raw) {
    const value = Math.max(-1, Math.min(1, Number(raw) || 0)) * FULL_SCALE;
    const size = Math.abs(value);
    if (size <= DEADZONE) return 0;
    const scaled = Math.round((size - DEADZONE) * FULL_SCALE / (FULL_SCALE - DEADZONE));
    return value < 0 ? -scaled : scaled;
  }

  // One controller as { mask, x, y }.
  function readPad(pad) {
    const table = pad.mapping === 'standard' ? STANDARD_BUTTONS : OTHER_BUTTONS;
    let mask = 0;
    (pad.buttons || []).forEach((button, index) => {
      if (table[index] && (button === true || button === 1 || (button && button.pressed))) mask |= table[index];
    });
    const axes = pad.axes || [];
    return { mask, x: axisValue(axes[0]), y: axisValue(axes[1]) };
  }

  class Hub {
    constructor(source) {
      this.source = source;           // what navigator.getGamepads is, or a test's stand-in
      this.screen = { x: 0, y: 0, used: false };
      this.directions = 0;            // the direction bits the stick holds on now
      this.names = [];
    }

    pads() {
      let list = [];
      try {
        list = this.source ? Array.from(this.source() || []) : [];
      } catch (error) {
        list = [];                    // a page where the Gamepad API is not allowed has no controllers
      }
      return list.filter(pad => pad && pad.connected !== false);
    }

    // On/off with a gap between the two tilts, as the firmware does for each direction.
    direction(bit, tilt) {
      if (tilt >= TURN_ON) this.directions |= bit;
      else if (tilt < TURN_OFF) this.directions &= ~bit;
    }

    // The buttons and the stick right now: { mask, x, y, stick }. Call once per frame.
    poll() {
      const pads = this.pads();
      this.names = pads.map(pad => String(pad.id || ''));
      let mask = 0;
      let x = 0;
      let y = 0;
      let stick = this.screen.used;
      if (typeof document === 'undefined' || document.visibilityState !== 'hidden') {
        pads.forEach(pad => {
          const now = readPad(pad);
          mask |= now.mask;
          if (!x) x = now.x;
          if (!y) y = now.y;
          if ((pad.axes || []).length >= 2) stick = true;
        });
        if (!x) x = this.screen.x;
        if (!y) y = this.screen.y;
      }
      this.direction(BITS.LEFT, -x);
      this.direction(BITS.RIGHT, x);
      this.direction(BITS.UP, -y);
      this.direction(BITS.DOWN, y);
      return { mask: mask | this.directions, x, y, stick };
    }

    // The on-screen stick: both axes from -1 to 1.
    setScreenStick(x, y) {
      this.screen.used = true;
      this.screen.x = axisValue(x);
      this.screen.y = axisValue(y);
    }
  }

  const source = typeof navigator !== 'undefined' && navigator.getGamepads ? () => navigator.getGamepads() : null;
  const hub = new Hub(source);

  // <div data-analog-stick><span></span></div>: drag the knob; it springs back when let go.
  function bindScreenStick(element) {
    const knob = element.querySelector('span');
    let pointer = null;
    const show = (x, y) => {
      if (knob) knob.style.transform = `translate(${x * 100}%, ${y * 100}%)`;
      hub.setScreenStick(x, y);
    };
    const move = event => {
      const box = element.getBoundingClientRect();
      const radius = box.width / 2 || 1;
      let x = (event.clientX - box.left - radius) / radius;
      let y = (event.clientY - box.top - box.height / 2) / radius;
      const length = Math.hypot(x, y);
      if (length > 1) { x /= length; y /= length; }
      show(x, y);
    };
    const release = event => {
      if (event.pointerId !== pointer) return;
      pointer = null;
      show(0, 0);
    };
    element.addEventListener('pointerdown', event => {
      event.preventDefault();
      pointer = event.pointerId;
      element.setPointerCapture(pointer);
      move(event);
    });
    element.addEventListener('pointermove', event => { if (event.pointerId === pointer) move(event); });
    element.addEventListener('pointerup', release);
    element.addEventListener('pointercancel', release);
    element.addEventListener('lostpointercapture', release);
    element.addEventListener('contextmenu', event => event.preventDefault());
  }

  // <span data-controller-status></span>: which controller is connected. A browser shows a
  // controller to a page only after one of its buttons is pressed, so the text says to press one.
  function bindStatus(element) {
    const show = () => {
      const names = hub.pads().map(pad => String(pad.id || '').slice(0, 60));
      element.textContent = names.length
        ? tr('js.controllers.connected', 'Game controller: {name}', { name: names.join(', ') })
        : tr('js.controllers.none', 'Game controller: press one of its buttons to use it');
    };
    window.addEventListener('gamepadconnected', show);
    window.addEventListener('gamepaddisconnected', show);
    show();
  }

  if (typeof document !== 'undefined') {
    const start = () => {
      document.querySelectorAll('[data-analog-stick]').forEach(bindScreenStick);
      document.querySelectorAll('[data-controller-status]').forEach(bindStatus);
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
    else start();
  }

  return { hub, Hub, axisValue, readPad, BITS };
})();
