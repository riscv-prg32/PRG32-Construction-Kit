# Working offline

The kit's pages use only files from the kit itself (no Internet libraries), so
it keeps working on a school network without Internet access.

## For students

- If the kit's server cannot be reached, opening any kit page shows the
  **Offline** page instead of an error:
  - your **guest games**: blocks games you can build and **Play**, kept in this
    browser only (IndexedDB). **Save as file** downloads one; signing in later
    offers to move them into your account (`storage.md`);
  - the **offline player** (link on that page) plays a `.prg32` cartridge file
    from your computer.
- Your real projects are on the server: they open again when the connection
  is back (press **Try again**).
- A page that was already open keeps working (blocks, Play); saving and
  compiling wait for the server.

The offline page appears after you have opened the kit once with a working
connection in that browser.

## For teachers

- Nothing signed-in is ever stored for offline use: on a shared classroom
  computer the next student cannot see the previous student's projects.
- The libraries are listed with versions, licences and fingerprints in
  `static/vendor/VENDOR.json`; `python3 tools/vendor_assets.py --check`
  verifies them.
- The kit sends a strict Content Security Policy: pages may only load code
  from the kit, which blocks most script-injection attacks. Details: ADR-0012.
