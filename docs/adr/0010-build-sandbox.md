# ADR-0010: Every compile runs in a bubblewrap sandbox (audit H-03)

**Status:** Accepted (2026-10-18; runtime chosen by the project owner)

## Context

Student C and assembly are validated (`source_project.py`), but the compiler
then ran as the web service's user with its whole environment, filesystem and
network (audit H-03). A validator bypass or a compiler bug would have given a
student the kit's database, secret key, other students' builds and the
network. The remediation plan made the isolation runtime the owner's choice:
bubblewrap inside the kit image, a separate build-worker container, or a
Docker container per build (needs the Docker socket, equivalent to root).

## Decision

Every compiler run goes through `build_sandbox.py`:

1. **bubblewrap** (`PRG32_BUILD_SANDBOX=bwrap`, the Docker image default):
   new user, PID, network, IPC, UTS and cgroup namespaces (`--unshare-all`);
   no network interface but loopback; `--cap-drop ALL`; `--clearenv` with a
   short allow-list (`PATH`, `PYTHONPATH`, `LANG`, `LC_ALL`,
   `SOURCE_DATE_EPOCH`, private `TMPDIR`/`HOME`); read-only mounts of the
   system, Python, the PRG32 SDK and the RISC-V compiler only (never the
   data folder or a parent of it); the build's own folder as the only
   writable mount; a fresh size-limited `/tmp`; no `/proc`; a read-only root;
   `--die-with-parent`, `--new-session`.
2. A **seccomp filter** (`seccomp_filter`, x86_64 and aarch64) refuses with
   EPERM: `ptrace`, `mount`/`umount2`/`pivot_root`/`chroot`, `unshare`,
   `setns`, `clone` with namespace flags, `mknod`/`mknodat`, kernel modules,
   `kexec`, `bpf`, `perf_event_open`, `userfaultfd`, keyring calls,
   `process_vm_*`, handle-based opens, swap and reboot; `clone3` returns
   ENOSYS; the x32 ABI and other architectures are killed.
3. **`build_guard.py`** (stdlib only, the only kit code inside the sandbox):
   RLIMIT_CPU, RLIMIT_AS, RLIMIT_NPROC (this user's processes now + an
   allowance, counted outside), RLIMIT_FSIZE, RLIMIT_NOFILE, no core files,
   umask 077; runs the compiler in its own process group, kills the group at
   the timeout (exit 124), caps stdout/stderr.
4. **Docker:** the container needs `docker/seccomp-kit.json` = Docker's own
   default profile (moby/profiles `seccomp/v0.2.4`, kept unchanged next to
   it) plus one rule allowing `clone`, `unshare`, `mount`, `umount2`,
   `pivot_root`, `setns` for bubblewrap; no added capabilities,
   `no-new-privileges`, `cap_drop: ALL`. Without it the start-up check fails
   and the container does not start.
5. **No silent downgrade:** `auto` falls back to limits-only (`rlimit`, not an
   isolation boundary) only outside production; production and `bwrap`
   refuse builds when bubblewrap does not work. Provenance records the mode.

## Consequences and limits

- **AppArmor hosts** (Ubuntu 24.04): Docker's `docker-default` profile denies
  the mounts bubblewrap makes and the host restricts unprivileged user
  namespaces. CI uses `apparmor=unconfined` plus
  `kernel.apparmor_restrict_unprivileged_userns=0`; a tailored AppArmor
  profile is a follow-up. Docker Desktop (no AppArmor) needs only the
  seccomp profile.
- **Not enforced:** a total disk quota for a build folder (only per-file size,
  `/tmp` size and the wall-clock limit), cgroup CPU shares, and a per-build
  UID (namespaced, but all builds share the kit user outside). RLIMIT_NPROC is
  per user, so a fork bomb is bounded by "existing + allowance".
- The kit container itself runs with a slightly larger seccomp allowance
  than Docker's default (the six namespace calls); compilers run under the
  much stricter kit filter.
