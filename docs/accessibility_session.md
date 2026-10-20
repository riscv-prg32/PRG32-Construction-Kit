# A keyboard and screen-reader session

The automated browser tests check keyboard-only workflows and run an axe-core scan
(`ide.md`, *Keyboard*). They cannot tell whether a person using a screen reader can
actually make a game. That needs a real session, by a person, recorded here.

**Status:** no session has been conducted yet.

## How to run one (about 45 minutes)

Use one of: NVDA with Firefox or Chrome (Windows), VoiceOver with Safari (macOS,
Cmd+F5), or ChromeVox (Chromebook). Do not use the mouse. Note for each task whether it
was done, how long it took, and anything that was not announced or could not be
reached.

| # | Task | Done? | Notes |
| --- | --- | --- | --- |
| 1 | Sign in; find the list of projects and hear how many there are | | |
| 2 | Create a project from an example | | |
| 3 | Open it in the IDE; move between the file tree, the editor, the problems and the output | | |
| 4 | Add a block from the toolbox to the workspace and change one of its fields | | |
| 5 | Find a problem in the Problems list and go to its line | | |
| 6 | Save (Ctrl+S); hear that it was saved; handle the "saved in another window" question | | |
| 7 | Compile; hear the result; download the PRG32 cartridge | | |
| 8 | Play it in the Player; start, pause, step a frame | | |
| 9 | In the debugger, set a breakpoint on a line, run to it, read a variable | | |
| 10 | Sign out | | |

## Recording the result

Add a row to the table below and open an issue for every problem found, with the task
number.

| Date | Screen reader, browser, system | Kit commit | Tasks done | Issues |
| --- | --- | --- | --- | --- |
| | | | | |
