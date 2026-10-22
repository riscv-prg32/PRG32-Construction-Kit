# The build sandbox: why a student's code cannot harm the server

When you press **Compile**, the server runs the RISC-V compiler on
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
and Ubuntu 24.04 restricts unprivileged user namespaces. Use the kit's own
profile, `docker/apparmor/prg32-kit`: docker-default plus user namespaces and
mounts inside them (the container still has no capabilities of its own).

```bash
sudo apparmor_parser -r -W docker/apparmor/prg32-kit
```

Then add `apparmor=prg32-kit` to `security_opt` in `docker-compose.yml` (or
`--security-opt apparmor=prg32-kit` to `docker run`). Neither
`apparmor=unconfined` nor `kernel.apparmor_restrict_unprivileged_userns=0` is
needed. To load it at every boot, copy it to `/etc/apparmor.d/`.

CI loads this profile and runs the sandbox escape and disk tests confined by it,
with the user-namespace restriction on. The first run (kit `7373f4b`) failed: the
first profile allowed too few mounts and capabilities for bubblewrap. The current
profile follows Ubuntu's own bubblewrap profile and passed in CI at `c0d115e` (31
sandbox and disk tests, bubblewrap required, user-namespace restriction on). Hosts without AppArmor (Docker Desktop)
need only the seccomp profile.

## Settings

| Variable | Default | Meaning |
| --- | --- | --- |
| `PRG32_BUILD_SANDBOX` | `auto` (`bwrap` in the image) | `bwrap`: required, builds refused without it. `rlimit`: limits only. `auto`: bwrap if it works, else rlimit, never on a production server. |
| `PRG32_BUILD_MEMORY_MB` | `1536` | Memory per compile. |
| `PRG32_BUILD_MAX_PROCESSES` | `128` | Processes a compile may add. |
| `PRG32_BUILD_RO_PATHS` | empty | Extra read-only folders for a custom `PRG32_BUILD_COMMAND`. |
| `PRG32_BUILD_MAX_MB` | `256` | Disk one build folder may use; the build is stopped beyond it. |
| `PRG32_BUILD_ROOT_MAX_MB` | `4096` | Disk all builds together may use (finished ones included); a build that would not fit is refused (507) before it starts. `0` = no total budget. |

## Limits we know about

- Disk: each file is capped (64 MiB), each build folder (`PRG32_BUILD_MAX_MB`,
  checked four times a second, so a build can overshoot by what it writes in a
  quarter of a second), and all builds together (`PRG32_BUILD_ROOT_MAX_MB`, by
  reservation before a build starts). A build runs inside its own folder in both
  modes.
- All builds run as the same server user outside their namespaces; they are
  kept apart by mounts (each sees only its own folder), not by user ids. Per-build
  user ids were evaluated and not adopted: they need privileges the container
  deliberately drops (ADR-0010, amendment).
- The process limit counts all of the kit user's processes, so a fork bomb is
  bounded by "what exists now + 128", not by an exact per-build count. "What
  exists now" is what the kernel counts, which in Docker includes every process
  of the same user id on the host (other containers too): the guard asks the
  kernel for it (it tries to start a process under smaller and smaller limits)
  instead of counting `/proc`, which a container or the sandbox cannot see whole.

Design record: `adr/0010-build-sandbox.md`.
