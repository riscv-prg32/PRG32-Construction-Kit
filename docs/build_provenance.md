# What made this cartridge? (build provenance)

Every **Compile** records how the cartridge
was made. Teachers can use it to check a hand-in; students can use it to see
that the same game always gives the same cartridge.

## Where to find it

`GET /api/builds/<id>` returns the build; `metadata.provenance` holds the
record. Each `.prg32` artifact also carries its own `sha256` and `bytes` in
its metadata.

## What is recorded

| Field | Meaning |
| --- | --- |
| `kit` | This kit's version and commit (from `.git`, or `PRG32_KIT_REVISION` in the Docker image). |
| `sdk` | The PRG32 tools (`prg32` package) the kit's Python can import: installed?, version, commit. |
| `abi` | The portable cartridge ABI: name, version 1.6, hash `0x260f6136`. |
| `toolchain` | The RISC-V compiler name and the first line of its `--version`. |
| `build_command` | The build command with program names only (no folders, secret-looking options hidden) and a SHA-256 of the exact command. |
| `authoring`, `source_language` | `blocks`, `c` or `assembly`, and which file was compiled (`c` or `asm`). |
| `entry_prefix`, `required_features`, `cart_ram_kib`, `architectures_requested` | The build settings. |
| `source_sha256`, `sources` | SHA-256 (and size) of the compiled source and of every source file made. |
| `cartridges` | For every `.prg32`: architecture, file name, SHA-256, size. |
| `attempts` | For every architecture: did the compiler make a cartridge? |
| `status` | `ready` (cartridges made), `failed` (build tools present but the compiler refused, or packaging crashed), `source-only` (no build tools on this server). |
| `started_at`, `finished_at`, `build_id` | When and which build. |

Two builds of the same saved project with the same tools give the same
record except `build_id`, `started_at` and `finished_at`. The test suite
checks this, and with the real toolchain also checks that the cartridge
bytes are identical.

## What is *not* recorded

Server folders and secrets: the record, the build log and the API answers
show program names, `<build>/...` for the build's own folder, and drop other
absolute folders. The SDK revision is the one the kit's Python sees; a custom
`PRG32_BUILD_COMMAND` may use another copy (its fingerprint is in
`build_command.sha256`). A kit commit id does not show uncommitted local
changes.
