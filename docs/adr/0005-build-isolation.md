# ADR-0005: Server builds first, browser toolchain after a measured spike

**Status:** Accepted

## Context

Server builds are real and tested (`packager.py`, CI container job) but run
GCC directly inside the kit's process sandbox. Validation of C is a guard,
not an OS sandbox. A browser toolchain (Clang/LLD to WebAssembly targeting
RV32) is unmeasured.

## Decision

- Server builds stay the supported path. Before guests or the public internet
  may build, builds move into a per-build container (no network, read-only
  root, CPU/memory/time limits) — tracked in G3.
- Every build records toolchain provenance: compiler version, SDK commit,
  ABI hash, and SHA-256 of each `.prg32` (G3).
- A browser toolchain is a time-boxed spike that measures download size,
  memory and compile time before any commitment.
