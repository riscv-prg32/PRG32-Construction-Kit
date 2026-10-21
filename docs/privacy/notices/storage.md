# Cookies and browser storage

*Notice version 1.0, from 2026-10-22.*

**In short:** this kit uses one cookie, only to keep you signed in, and keeps your own games,
settings and breakpoints in this browser. There is no advertising or tracking, and nothing is
shared with other sites.

- **The cookie:** `prg32_kit_session` keeps you signed in. It holds your account number and
  when you signed in, signed by the server so nobody can change it. It ends when you sign out,
  or a few hours after you signed in.
- **Browser storage:** without an account, your games, sprites and sounds are kept in this
  browser (IndexedDB `prg32-kit-guest`). Small preferences are kept there too, such as which code
  view you opened last, your debugger breakpoints, the last project in AudioStudio, and that you
  have read this note (localStorage keys starting with `prg32-`). The kit's own pages and libraries
  are cached so it opens without a connection; your games and account pages are never cached.
- **Why there is no "accept" button:** all of this is needed for the kit to work. EU law
  (the ePrivacy rules) asks for consent only for storage that is *not* needed, such as tracking,
  and the kit has none. The note at the bottom of the page only tells you what is kept.
- **What you can do:** delete everything at any time by clearing this site's data in your
  browser settings. Signing out removes the cookie.

The full list, with how long each item is kept: [/privacy#storage](/privacy#storage).
Who is responsible, and how to ask: [/privacy](/privacy).
