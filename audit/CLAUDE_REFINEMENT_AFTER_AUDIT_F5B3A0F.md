# Claude refinement note after the audit of f5b3a0f

Refine PRG32-Construction-Kit after the independent audit of
`f5b3a0ff3f261f424172e57b30602026bd1ffaca` (2026-10-23). Read `AGENTS.md`
and the current `audit/` deliverables first. Do not edit auditor-owned scores.

Result: **NO-GO, 132/156 (84.6%)**.

This score is the preserved result of the completed audit. The next audit must
add and independently score `I18N-01` and `PY-01`, increasing the maximum from
156 to 164 before any N/A handling. Do not infer scores from planned work.

`BLD-02` is now **4/4**. GitHub Actions run `39924578831` passed for the exact
audited SHA. Its production-image job ran the kit beside 300 processes in
another container using the same host UID, confirmed those processes were
hidden from the kit's `/proc`, and passed:

- the kernel-count RLIMIT_NPROC evidence gate;
- bubblewrap and build-budget tests;
- bounded fork-bomb behavior with no surviving children;
- AppArmor confinement;
- real and concurrent PRG32 cartridge builds;
- debugger/audio fixture rebuilds and production-container health.

Keep that workflow mandatory. `SEC-01` remains 3/4 because build processes still
share a host UID outside their namespaces; do not remove the mount, seccomp,
AppArmor, disk, time, memory, process and no-network layers.

## Phase 1 — merge the CartridgeStore identity patch

This is the main technical integration gate. The selected model is coherent:

- accounts match by email;
- the private username is shared between Kit and Store;
- a separate pseudonymous public handle is the only identity exposed in public
  Store surfaces;
- collisions never join accounts;
- ticket single-use, roles, scopes, notice acknowledgement, CSRF and Kit-side
  publisher authorization remain enforced.

The implementation currently lives in
`docs/upstream/cartridge-store-shared-identity.patch`. Retained clean-clone
evidence passes, but canonical CartridgeStore `4a3138b` is unpatched and the
default suite still fails three identity tests. Therefore this is not closed.

Required work:

1. have CartridgeStore maintainers review and merge the patch or an equivalent;
2. update the Kit's canonical Store pin and contract metadata;
3. regenerate `tests/fixtures/contract/`;
4. confirm `sso_protocol.py` remains byte-identical;
5. test migration of old accounts and username/email/handle collisions;
6. rerun Store tests and the full Kit Store/SSO/publishing suite from clean
   canonical checkouts without applying an out-of-tree patch.

Acceptance: zero identity failures against the pinned merged Store, and no
public API/catalog/score/review/multiplayer response exposes private username or
email.

## Phase 2 — complete deployment GDPR authorization

The repository's technical privacy implementation remains strong at 3/4, but
the actual deployment is still NO-GO. The controller, DPO or qualified counsel
must complete decisions D-0–D-10 with real facts:

- controller, privacy contact and DPO;
- applicable legal bases and Member-State education/children rules;
- completed DPIA, residual risks and any prior consultation;
- retention and backup periods;
- named processors, service regions, Article 28 agreements and transfer
  mechanisms;
- cloud/GitHub/publishing choices for minors and any valid consent procedure;
- staffed breach tabletop, contacts and supervisory authority;
- dated approval, owners, versions and privacy changelog.

Do not claim GDPR certification from automated tests and do not invent these
deployment decisions.

## Phase 3 — canonical audio ecosystem

Merge the SDK buzzer-retirement/audio-clock work and PRG32-QT firmware-engine
integration upstream. Then update pins and regenerate the language index,
contracts, PCM hashes, ADSR traces, QEMU/Qt/browser comparisons and buzzer search.
Resolve the remaining frame-triggered effect alignment.

## Phase 4 — external evidence

- physical PRG32 transfer and stereo eight-voice ADSR/pan capture;
- visible PRG32-QT desktop Import workflow;
- AudioStudio with a named screen reader;
- test-owned institutional OIDC, Google, Microsoft and GitHub scenarios.

PRG32-iOS remains unsupported; do not invent an interface.

## Phase 5 — multi-language product support

Internationalize the complete product in **English, Italian, Spanish, French
and German**, including the IDE, guest and account flows, Blockly, Sprite Lab,
AudioStudio, debugger, settings, validation/build diagnostics, publishing,
privacy notices, help and classroom documentation.

Use stable message keys, safe interpolation and a documented fallback locale.
Locale selection must persist appropriately, work offline and remain separate
from project semantics. Translation must never change saved Blocks JSON, game
IR, generated source or PRG32 cartridge bytes. Add automated catalog parity and
missing-key checks plus real-browser layout, keyboard and screen-reader coverage
for every locale, including pluralization, long strings and error paths.

Acceptance: all five locale catalogs have complete key parity; no reachable
user-facing string silently falls back because of a missing translation; the
PWA works offline in every locale; and the same fixture built under every locale
has byte-identical generated C, generated assembly and cartridge hashes.

## Phase 6 — Python projects

Add Python as a fixed project type without weakening the validator-first build
boundary. Python is an authoring language, not a cartridge runtime: do not embed
CPython or MicroPython and never execute student Python during validation or
builds. Adopt this ahead-of-time pipeline:

```text
saved Python source
  -> parse only with a pinned grammar and strict resource limits
  -> allow-listed, statically checked PRG32 Python AST
  -> deterministic language-neutral game IR
  -> inspectable commented C and, on request, RISC-V assembly
  -> existing sandboxed PRG32 toolchain
  -> PRG32 cartridge
```

### 6.1 — specify PRG32 Python

Write an ADR and versioned language specification before exposing the project
type. The first teachable subset should provide explicit `init`, `update` and
`draw` functions; fixed-width integers, Booleans and bounded strings; statically
typed variables and functions; assignments, arithmetic, comparisons, Boolean
expressions, conditionals and bounded loops; fixed-size collections known at
compile time; and one `prg32` module containing only portable ABI functions for
graphics, input, sprites, assets and eight-voice stereo audio.

Specify integer ranges and overflow, negative division/remainder, evaluation
order, short-circuiting, truth values, string limits, loop bounds and resource
ceilings. Do not inherit Python's arbitrary-precision integers, dynamic typing
or allocation implicitly. Unsupported constructs receive stable diagnostic codes,
precise source ranges and a simple supported alternative.

### 6.2 — parse and validate without execution

Parse with a pinned grammar; parsing must not import or run the program. Enforce
limits on source bytes, AST nodes, nesting, symbols, functions, control-flow
complexity, generated IR and output. Walk an explicit AST allow-list and reject
arbitrary imports, `eval`, `exec`, reflection, dynamic attributes, filesystem,
network, processes, threads, native extensions, dynamic allocation, unbounded
collections, coroutines, generators and all undocumented syntax.

Build a typed symbol table, resolve every call against the approved PRG32 API and
lower only validated nodes into the shared game IR. The browser may mirror checks
for fast feedback, but server validation is authoritative and IDE completion must
suggest only syntax and APIs that it accepts.

### 6.3 — deterministic generation and provenance

Generate C and assembly only from validated IR, with stable declaration/symbol
ordering and per-Python-line teaching comments. Do not emit timestamps, host
paths, random identifiers or locale-dependent content. Retain stable provenance
on every IR node and implement the mapping `Python source range -> IR node ->
generated C/assembly lines -> cartridge address`. Debug markers must leave the
normal generated files and cartridge bytes unchanged.

Record the PRG32 Python grammar/language version, IR version, ABI/toolchain
versions and source/AST/IR/generated-source/cartridge hashes in build provenance.
Build identical fixtures in separate processes and under every supported UI
locale; all normalized IR, source, map and cartridge hashes must match.

### 6.4 — project and IDE integration

Add a migrated, versioned representation such as `source_mode: "python"`,
`source_python` and `python_language_version`. The Python text is authoritative;
generated C, assembly and source maps use artifact CRUD. Preserve optimistic
version conflicts, quotas, ownership, history, archive/import/export, guest
IndexedDB behavior and explicit conversion. A project's type remains immutable
outside the documented conversion route.

Provide Monaco syntax, completion, navigation and diagnostics; deterministic
save/import/export; source-mapped run/debug; inspectable generated-source tabs;
assets, Sprite Lab, AudioStudio and packaging integration; and accessible,
localized error messages whose stable codes and source ranges do not vary by
locale.

### 6.5 — verification and rollout

Start behind a capability flag until arithmetic/control flow/functions, graphics,
input and eight-voice stereo audio fixtures pass parser/validator, deterministic
generation, real cartridge builds, browser and PRG32-QT execution, source-mapped
debugging and malicious-input tests. Compare equivalent Blocks and Python programs
through the same IR; compare generated C and assembly with the RV32 trace harness.
Cover fixed-width edge cases, negative division/remainder, evaluation order,
short-circuiting, loop ceilings, deep/oversized AST denial of service, diagnostic
escaping and every prohibited host capability.

Acceptance: generated C and assembly remain visible teaching material; repeat
builds from identical project data are byte-identical across processes and UI
locales; Python cannot bypass the game IR or existing build isolation; error maps
identify the original Python range; and retained real-toolchain cartridges behave
the same in the browser and PRG32-QT reference paths.

## Preserve

Preserve deterministic inspectable generated C and assembly, validator-first
compilation, isolated per-build folders, byte-identical debug cartridges,
eight firmware-engine voices, no buzzer, local-only guest projects, ephemeral
guest run builds, version conflicts, sealed least-privilege tokens, strict CSP,
vendored browser libraries, the one-IDE/fixed-project-type model, and every
production sandbox layer.

## Reaudit handoff

Return exact canonical commits, merged Store migration and privacy proof,
completed deployment privacy decisions, exact test counts and CI links,
browser/toolchain/device matrix, canonical audio commits and all remaining
limitations. Include five-locale catalog and browser evidence, locale-independent
artifact hashes, the documented Python subset and schema, parser/validator
negative tests, source maps, generated C/assembly and real cartridge hashes.
Request reassessment only when the remaining hard gates are
evidenced, not merely implemented as local patches.
