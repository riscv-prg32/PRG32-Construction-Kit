# Architecture decision records

Short records of decisions for the full-IDE work. Each has a status:
**Accepted** (in force), **Proposed** (waiting for the project owner), or
**Superseded**.

| ADR | Title | Status |
| --- | --- | --- |
| [0001](0001-project-manifest.md) | Versioned `prg32.project.json` and portable project archive | Accepted |
| [0002](0002-evolve-flask-backend.md) | Evolve the Flask backend instead of rewriting it | Accepted |
| [0003](0003-wasm-runtime-from-qt-core.md) | Browser runtime is the PRG32-QT core compiled to WebAssembly | Accepted (G4) |
| [0004](0004-handwritten-assembly-mode.md) | Handwritten assembly authoring mode | Accepted (option 2) |
| [0005](0005-build-isolation.md) | Server builds first, browser toolchain after a measured spike | Accepted |
| [0006](0006-shared-debug-protocol.md) | One debug protocol shared with PRG32-QT | Proposed |
| [0007](0007-identity-and-roles.md) | OIDC with PKCE, issuer+subject linking, wider roles | Proposed |
