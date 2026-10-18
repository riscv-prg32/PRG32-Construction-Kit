# ADR-0012: Self-contained frontend, root service worker and Content Security Policy

**Status:** Accepted (2026-10-18, refinement phase 1)

## Context

The pages loaded Bootstrap, Bootstrap Icons and jQuery from jsDelivr/code.jquery.com
and Blockly from unpkg; Blockly also fetched its icons from a Google server. A
cold offline start was impossible, a strict CSP could not be set, and the
audit flagged missing provenance (M-02). The service worker was registered at
`/static/service-worker.js`, so its scope was `/static/` and it never
controlled the kit's pages.

## Decision

1. **Vendored, pinned libraries** in `static/vendor/<name>/<version>/`:
   Bootstrap 5.3.3, Bootstrap Icons 1.11.3, jQuery 3.7.1 (MIT) and Blockly
   11.2.1 with its media (Apache-2.0). `tools/vendor_assets.py` downloads them
   with `npm pack`, checks each tarball against the registry's integrity hash,
   copies only the needed files plus licences, and writes `VENDOR.json`
   (version, licence, source, integrity, SHA-256 per file). `--check`
   re-verifies offline. Blockly's licence text comes from its repository at
   tag `blockly-v11.2.1` with a pinned SHA-256. Monaco follows in phase 2.
2. **Content Security Policy** on every response:
   `default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self'`
   plus the SHA-256 of the two stylesheets Blockly 11.2.1 injects;
   `img-src 'self' data: blob:`; `font-src`, `connect-src`, `worker-src`,
   `manifest-src 'self'`; `media-src 'self' data: blob:`; `object-src 'none'`;
   `base-uri 'self'`; `frame-ancestors 'none'`; `form-action 'self'` plus the
   linked Cartridge Store origin for single sign-on. No `unsafe-inline`, no
   `unsafe-eval`. `wasm-unsafe-eval` exists only so the browser can compile the
   PRG32 core. Inline scripts, `<style>` blocks and `style=` attributes were
   moved to static files and CSS classes.
3. **Caching headers:** pages and API answers `Cache-Control: no-store`;
   `static/vendor/` (versioned paths) `public, max-age=31536000, immutable`.
4. **Service worker at `/service-worker.js`** (public route,
   `Service-Worker-Allowed: /`), scope `/`. It still caches static files only;
   page navigations always go to the network and, when the server cannot be
   reached, get the static **offline page** (`/static/offline.html`): an
   editable Blockly scratchpad with the Blocks preview, kept in the browser
   only, plus `/static/offline-player.html` for local `.prg32` files on the
   WebAssembly core. Old registrations under `/static/` are removed.
   `static/service-worker.lock.json` fingerprints the cached files; a test
   fails if they change without a new `CACHE_NAME`.

## Consequences

- The documented offline subset is: scratchpad blocks, Blocks preview, local
  cartridge player. Signed-in projects need the server (they are never cached);
  guest projects in IndexedDB are phase 6.
- Upgrading Blockly needs `tools/vendor_assets.py`, the new style hashes (the
  browser test reports them) and a cache bump.
- Browser tests (`tests/test_browser_offline.py`) use Playwright with Chrome or
  Playwright's Chromium and skip without them; CI installs Chromium.
