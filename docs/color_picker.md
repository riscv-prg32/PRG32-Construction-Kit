# Tools → Color Picker

**Tools → Color Picker** (in the menu bar, also without an account) shows a colour the way a
PRG32 program writes it. Everything happens in your browser; nothing is sent anywhere.

1. Choose a colour with the colour box, type it as `#RRGGBB`, or move the red, green and blue
   sliders (0 to 255).
2. Read it in two formats and three number bases:

| Format | What it is | Example: `#FFCC00` |
| --- | --- | --- |
| RGB24 | 8 bits each of red, green and blue | `0xFFCC00` = 16763904 = `11111111 11001100 00000000` |
| RGB565 | the PRG32 screen's 16 bits: the top 5 bits of red, 6 of green, 5 of blue | `0xFE60` = 65120 = `11111 110011 00000` |

The binary is grouped one colour per group (8-8-8 and 5-6-5), so you can see which bits belong to
which colour.

The two swatches show the colour as you chose it and as the PRG32 screen shows it. RGB565 drops
the lowest bits, so `#FFCC00` becomes `#FFCF00` on the PRG32. **In C or assembly** gives the
value to paste into your code, for example `0xFE60 /* #FFCF00 */`, and **Copy** copies it. The
page also names the nearest of the PRG32's named colours (`PRG32_COLOR_YELLOW` and the others in
`prg32.h`).

The conversion is in `static/js/color_picker.js` (`PRG32Color`); `tests/test_color_picker_browser.py`
checks it against values worked out by hand.
