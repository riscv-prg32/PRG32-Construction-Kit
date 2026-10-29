# Using the kit without an account

## For students

Open the kit and start: you do not need an account to make games. The badge
**Guest: games stay in this browser** in the menu bar says you are not signed in.

- **Projects:** make a new game or copy an example. Your games are listed here.
- **IDE and editor:** Blocks, C or assembly. **Generate** shows the C and the RISC-V assembly
  your blocks make, line by line, just as with an account. **Play** runs a Blocks game in the
  simulator.
- **Sprite Lab**, **Backgrounds** and **AudioStudio:** draw sprites and maps and compose sounds
  for your game, then use them by name in Blocks, Python, C or assembly (`project_art.md`). An
  example with art, such as Star Catcher, comes with its sprites, background and sound.
- **Player:** play any `.prg32` cartridge file from your computer.

Everything is kept **in this browser, on this computer**. Nobody else sees it, and it can be
lost if the browser's data is cleared, so use **Export** to save a game as a file.

Some things need an account, because the server has to keep them or build them:

- **Compile** (a real cartridge for the console or PRG32-QT) and the compiler check;
- **Publish** to the Cartridge Store, **Classes**, project **History**, cloud copies;
- **recorded samples** in AudioStudio.

When you try one, the kit says **Sign in to keep going**. Nothing is lost: after you sign in on
this browser, the Projects page offers to **move your games into your account**, with their
sprites, backgrounds and sounds.

## For teachers and administrators

- The kit opens without an account by default. To make every page ask for a sign-in, turn on
  **Sign-in required for every page** (Settings, Access) or set
  `PRG32_KIT_LOGIN_REQUIRED=1`. `PRG32_GUEST_MODE=off` also closes the guest workspace.
- The server keeps nothing for guests: no projects, files or logs of what they made. To show
  the generated code or play a sound, it works on what the browser sends and forgets it
  (`/api/guest/*`, ADR-0023). Each address may make a limited number of these requests per hour.
- The generated C and assembly come from the same validators and generators as for an
  account, so a guest sees exactly what the class will build.
- Privacy: the short notice is `guest` ([notices/guest.md](privacy/notices/guest.md)); the
  record of processing lists `browser_storage` and `guest_requests`.
