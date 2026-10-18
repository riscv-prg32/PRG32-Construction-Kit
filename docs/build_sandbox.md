# The build sandbox: why a student's code cannot harm the server

When you press **Compile Cartridge**, the server runs the RISC-V compiler on
the student's C or assembly. The kit checks that code first, but a compiler is
a large program, so every compile also runs **inside a sandbox**.

## For teachers

Inside the sandbox a compile:

- has **no network** (it cannot reach the Internet or the school network);
- sees the operating system, Python, the PRG32 tools and the compiler
  **read-only**;
- can write **only its own build folder** and an empty temporary folder;
- cannot see the kit's database, secret key, other students' builds or the
  server's settings (passwords, tokens);
- cannot start new sandboxes, debug other programs, mount disks or create
  device files;
- is stopped when it uses too much CPU time, memory, processes or file space,
  or runs longer than `PRG32_BUILD_TIMEOUT`, and nothing it started keeps
  running.

The start-up check shows it:

```text
  OK    build sandbox: bubblewrap (no network, read-only SDK, private build folder)
```

Each build's provenance (`build_provenance.md`) records `"sandbox": "bwrap"`.

## Setting it up

| Where | What to do |
| --- | --- |
| Docker Compose | Nothing: `docker-compose.yml` already sets `security_opt: seccomp=./docker/seccomp-kit.json`, `no-new-privileges` and `cap_drop: ALL`. |
| `docker run` | Add `--security-opt seccomp=$PWD/docker/seccomp-kit.json --security-opt no-new-privileges:true --cap-drop ALL`. |
| Linux without Docker | Install `bubblewrap` and set `PRG32_BUILD_SANDBOX=bwrap`. Unprivileged user namespaces must be allowed. |
| A teacher's laptop (macOS) | bubblewrap is Linux-only. `auto` uses limits only (`rlimit`): fine for one trusted user, **not** for a class server. |

`docker/seccomp-kit.json` is Docker's own default seccomp profile plus one rule
allowing the six system calls bubblewrap needs to build its sandbox
(`clone`, `unshare`, `mount`, `umount2`, `pivot_root`, `setns`). Regenerate it
with `python3 tools/make_seccomp_profile.py`.

### AppArmor hosts (Ubuntu 24.04 and others)

Docker's `docker-default` AppArmor profile forbids the mounts bubblewrap makes,
and Ubuntu 24.04 restricts unprivileged user namespaces. Today the tested
setting (CI) is:

```bash
sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0
# and in docker-compose.yml, under security_opt:  - apparmor=unconfined
```

This removes AppArmor confinement from the kit container (the seccomp profile,
no-new-privileges, dropped capabilities and the sandbox itself stay). A
tailored AppArmor profile is planned.

## Settings

| Variable | Default | Meaning |
| --- | --- | --- |
| `PRG32_BUILD_SANDBOX` | `auto` (`bwrap` in the image) | `bwrap`: required, builds refused without it. `rlimit`: limits only. `auto`: bwrap if it works, else rlimit, never on a production server. |
| `PRG32_BUILD_MEMORY_MB` | `1536` | Memory per compile. |
| `PRG32_BUILD_MAX_PROCESSES` | `128` | Processes a compile may add. |
| `PRG32_BUILD_RO_PATHS` | empty | Extra read-only folders for a custom `PRG32_BUILD_COMMAND`. |

## Limits we know about

- No total disk quota per build folder: files are capped one by one (64 MiB),
  `/tmp` is capped (256 MiB), and the time limit stops runaway writers.
- All builds run as the same server user outside their namespaces; they are
  kept apart by mounts (each sees only its own folder), not by user ids.
- The process limit counts all of the kit user's processes, so a fork bomb is
  bounded by "what exists now + 128", not by an exact per-build count.

Design record: `adr/0010-build-sandbox.md`.
