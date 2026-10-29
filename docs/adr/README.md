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
| [0007](0007-identity-and-roles.md) | OIDC with PKCE, issuer+subject linking, wider roles | Superseded by 0016 |
| [0008](0008-store-egress-policy.md) | Store egress policy: admin allow-list, public addresses only, pinned connections (H-01) | Accepted |
| [0009](0009-publish-authorization-and-confirmation.md) | Publishing needs the publisher role and a confirmed review (H-02) | Accepted |
| [0010](0010-build-sandbox.md) | Every compile runs in a bubblewrap sandbox (H-03) | Accepted |
| [0011](0011-design-baselines.md) | The design baseline and the briefs that refine it | Accepted |
| [0012](0012-offline-frontend-and-csp.md) | Self-contained frontend, root service worker and CSP | Accepted |
| [0013](0013-ide-shell-and-monaco.md) | IDE shell with Monaco, on Bootstrap + jQuery | Accepted |
| [0014](0014-ide-language-services.md) | Offline language services from a generated PRG32 index | Accepted |
| [0015](0015-source-and-block-debugger.md) | Source and block debugging from saved maps and DWARF | Accepted |
| [0016](0016-academic-identity-and-scoped-roles.md) | Academic identity with PKCE, issuer+subject accounts, scoped roles | Accepted |
| [0017](0017-storage-policy.md) | Guest and registered storage policy | Accepted |
| [0018](0018-shared-store-contract.md) | One versioned Store contract for the kit and the Cartridge Store | Accepted |
| [0019](0019-provider-neutral-cloud-storage.md) | Provider-neutral cloud storage (Google Drive, OneDrive) | Accepted |
| [0020](0020-delivery-targets-and-evidence.md) | Delivery targets the kit claims, and how evidence is recorded | Accepted |
| [0021](0021-firmware-audio-engine.md) | The PRG32 firmware's audio engine in the browser; the buzzer is obsolete | Accepted |
| [0022](0022-personal-data-and-rights.md) | Personal data: one inventory, rights the kit can carry out, the school decides | Accepted |
| [0023](0023-open-guest-workspace.md) | The kit opens without an account; guests keep their games in the browser | Accepted (amends 0017, 0012) |
| [0024](0024-one-ide.md) | One IDE: run builds for every project type, fixed project types, tools as tabs | Accepted (amends 0013, 0023) |
| [0025](0025-github-project-remote.md) | GitHub as a project's remote: a GitHub App, a folder of files per project | Accepted |
| [0026](0026-prg32-python-projects.md) | PRG32 Python projects, compiled ahead of time to the game IR | Accepted (amends 0001, 0024) |
| [0027](0027-interface-languages.md) | The interface in five languages, never in the build | Accepted |
| [0028](0028-one-deploy-tool.md) | One Deploy tool for a PRG32 console, PRG32-QT and QEMU | Accepted (builds on 0020) |
| [0029](0029-project-art-in-code.md) | Project art in code, by name, in every kind of project | Accepted (amends 0004) |
