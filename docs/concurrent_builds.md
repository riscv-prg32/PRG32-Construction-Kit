# Many Students Building at Once

In a lab, thirty students may click **Compile Cartridge** or **Download .prg32**
in the same minute. Some of them may have the same project open in two
browser windows too. The kit is designed for that.

## What keeps builds apart

- **Every build has its own folder.** Each click creates a new build record
  with a unique id, and the kit writes `game.c`, the bundle and the `.prg32`
  files to `data/builds/<build_id>/`. Two builds never share a file, even when
  they come from the same project.
- **Every cartridge has its own download link.** The download button uses the
  artifact id of *your* build, so you always get the cartridge you compiled.
- **The PRG32 compiler works in a private temporary folder** for each build.

## The waiting line (build slots)

Compiling starts a real compiler, which needs CPU and memory. The server
allows a fixed number of compilers at a time, called *build slots*. A build
takes a free slot, compiles, and returns the slot. If all slots are busy, the
next build waits its turn. That's why a build can take longer when the whole
class compiles at once.

If a build waits longer than the queue timeout, the editor shows:

> All N cartridge build slots are busy. Wait a moment, then compile again.

Nothing is broken. Click the button again after a few seconds.

| Setting | Default | Meaning |
| --- | --- | --- |
| `PRG32_MAX_PARALLEL_BUILDS` | number of CPU cores | compilers running at the same time |
| `PRG32_BUILD_QUEUE_TIMEOUT` | `180` | seconds a build waits for a free slot |

The slots are small lock files in `data/builds/.slots/`. They are shared by all
threads and worker processes of one server, and a crashed process frees its
slot automatically.

## The same project in two windows

The editor saves your project and then asks the server to build it. If you
(or a classmate sharing the project) saved a *different* version from another
window in between, the server doesn't compile the wrong version. It answers:

> This project was changed in another browser window after you saved it.
> Reload the project to see the newest version, then compile again.

Saving itself is "last save wins": the newest save replaces the older one.
Building never overwrites a save. For example, it won't replace Advanced C
source saved from another window.

## Running the server for a class

- `python app.py` uses Flask's threaded server. It handles several students
  at once and works well on a teacher laptop.
- The Docker image runs gunicorn with 2 worker processes and 16 threads each.
  Change these with `PRG32_KIT_WORKERS` and `PRG32_KIT_THREADS`. Builds that
  wait for a slot keep a thread busy, so keep the thread count above the
  number of students likely to compile at the same moment.
- SQLite is fine for a classroom. For a larger multi-replica deployment, use
  PostgreSQL (see `docker.md`).
