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
   allowance; see the 2026-10-22 amendment), RLIMIT_FSIZE, RLIMIT_NOFILE, no core files,
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

## Amendment (2026-10-20, after audit `fea31c0`)

- **AppArmor:** `docker/apparmor/prg32-kit` replaces `apparmor=unconfined` on
  AppArmor hosts: docker-default's rules plus `userns`, the namespace-local
  capabilities and the mounts bubblewrap makes. CI runs the sandbox and disk tests
  confined by it with `kernel.apparmor_restrict_unprivileged_userns=1`.
- **Disk:** each build folder is capped (`build_guard.py --disk-budget`), and all
  builds together reserve space before they start (`build_budget.py`); a full build
  area answers 507 and writes nothing. Builds run inside their folder in `rlimit`
  mode too.
- **Per-build user ids, evaluated:** a setuid helper or `newuidmap` needs root or
  `CAP_SETUID` in the container, which contradicts `cap_drop: ALL` and
  `no-new-privileges`; one rootless container per build costs seconds per compile
  on classroom servers. Not adopted. Separation stays by mount namespaces (a build
  sees only its own folder, read-only system, no network, no `/proc`), with the
  per-user process limit and the disk budgets above.

## Amendment (2026-10-22, every build failing on a Docker server)

- **Process limit:** the kit counted "this user's processes now" in `/proc` outside
  the sandbox. The kernel counts every process of the user id on the whole host, and
  a container's `/proc` shows only its own, so on a server where uid 1000 also runs
  other containers the limit fell below what already existed and every compile
  failed with "Resource temporarily unavailable". `build_guard.py` now measures the
  kernel's own count (`processes_the_kernel_counts`: a binary search over soft
  RLIMIT_NPROC values with short forks, about 20, a few milliseconds) and sets the
  hard limit to that count + `PRG32_BUILD_MAX_PROCESSES`. `--processes` is the
  allowance; `tests/test_build_sandbox.py` checks both that a build starts beside
  many other processes and that the allowance still stops a fork bomb.
- **Linux proof (2026-10-23, audit of `fe2e2c4`):** the CI container job starts a
  second container running 300 processes as the kit's user id, outside the kit
  container. With that load, `tools/process_limit_evidence.py` must find at least 250
  of the user's processes hidden from the kit's `/proc` (so the old limit would have
  refused every build), then `tests/test_build_sandbox.py`, `tests/test_build_budget.py`
  (bwrap required) and `tools/check_build.py` must pass. The fork-bomb test also
  checks that the bomb is refused within the allowance and that none of its processes
  outlives the build. The logs and JSON are kept as `same-uid-*` in the container
  evidence artifact.
