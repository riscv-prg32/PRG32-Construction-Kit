# ADR-0027: The interface in five languages, never in the build

**Status:** Accepted (2026-10-24).

## Context

The kit is used in Italian, Spanish, French and German classrooms as well as English ones. The
audit brief adds I18N-01: complete, accessible interfaces in English, Italian, Spanish, French
and German, with locale choice and fallback that work offline, and builds that stay
byte-identical whatever the language.

## Decision

1. **One catalog per language**, `static/i18n/<locale>.json`: a flat object, message key ->
   text. `{name}` marks a value filled in when the message is shown; every language has the same
   names (Blockly's `%1` inputs likewise). A key ending in `.one`/`.other` is a plural pair. The
   English catalog is the reference: the four others have exactly its keys.
2. **The server draws pages in the reader's language** with `t(key, **values)`, a Jinja global
   (`prg32_construction_kit/i18n.py`). The language is the `prg32_locale` cookie if the reader
   chose one, else the best supported language of `Accept-Language`, else English. Pages say
   `<html lang>` and `Vary: Accept-Language, Cookie`.
3. **Scripts translate with `tr(key, 'English', values)`.** The English stays in the script, so
   the code reads like plain code and still works where no catalog is loaded (Node.js tools and
   tests); a test checks it equals the English catalog. The browser copies of the catalogs
   (`static/i18n/<locale>.js`, written by `tools/build_i18n.py`) load with plain script tags under
   the strict CSP, and the service worker caches them, so the offline pages translate too
   (`data-i18n` attributes, filled in by `static/js/i18n.js`).
4. **Choosing a language** (the menu in the top bar, also on the offline page) stores the choice
   in the `prg32_locale` cookie and in localStorage `prg32-kit-locale`, saves unsaved IDE work,
   and reloads. Both are listed in the storage notice (version 1.1) and on `/privacy#storage`.
5. **The language never reaches the build.** Generators, the Python compiler, the packager,
   source maps and provenance do not import `i18n`. Generated C and assembly keep their English
   teaching comments in every interface language (they are artifacts, made the same every
   time); the build of a saved project is byte-identical in all five languages
   (`tests/test_i18n.py`).
6. **Privacy notices** keep one version per notice; each has its summary in the five languages
   (`privacy_notices.json` `translations`). What the kit records as shown does not depend on the
   language.
7. **Missing text falls back** to English, then to the key, so a page never breaks. Tests fail on
   a missing key, a placeholder that differs, an untranslated message that is not a reviewed
   cognate (`tests/fixtures/i18n/same_as_english.json`), text in a template outside `t()`, and
   HTML text built by scripts outside `tr()`.

## Consequences

- A new message means an entry in all five catalogs and `python3 tools/build_i18n.py`.
- Generated code comments, the PRG32 Python compiler's server diagnostics, the server's API error
  messages, Blockly's and Monaco's own menus, and the long-form documentation in `docs/` stay in English; the editor's live checks
  and the explanations under each problem are translated. `docs/i18n.md` lists what is and is
  not translated, and the classroom quick start exists in all five languages.
- The 8x8 PRG32 font has only ASCII: texts a game shows on the console are the student's own and
  are never translated by the kit.
