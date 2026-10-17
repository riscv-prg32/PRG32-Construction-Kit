# Deployment examples

Ready-to-copy files for running PRG32-Construction-Kit with **cartridge builds
switched on**. The full walk-through is `docs/install_cartridge_build.md`.

| File | Use it for |
| --- | --- |
| `classroom.env` | All build and server settings in one place. Copy to `.env` for Docker Compose or systemd. |
| `start-kit.sh` | macOS / Linux laptop: finds the RISC-V compiler, runs the build check, starts the kit. |
| `prg32-kit.service` | Linux server without Docker (systemd + gunicorn). |

After any install, run the build check in the same environment as the server:

```bash
python tools/check_build.py --students 4 --windows 2
```
