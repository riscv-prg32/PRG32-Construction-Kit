# Setup Guide

## Requirements

- Python 3.11 or newer.
- A modern browser.
- Optional: the PRG32 Python build module/toolchain when real `.prg32` files are required.
- Optional: a PRG32 Cartridge Store instance when publishing from the app.

## Local Python setup

```bash
git clone https://github.com/your-org/PRG32-Construction-Kit.git
cd PRG32-Construction-Kit
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open:

```text
http://127.0.0.1:5090/
```

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `PRG32_KIT_DATA` | `data` | Persistent data directory. |
| `PRG32_KIT_DB` | `$PRG32_KIT_DATA/construction_kit.sqlite` | SQLite path. |
| `DATABASE_URL` | unset | SQLAlchemy URL; overrides the SQLite path. |
| `PRG32_KIT_PORT` | `5090` | HTTP port. |
| `PRG32_STORE_URL` | `http://127.0.0.1:5080` | Default Cartridge Store URL. |
| `PRG32_BUILD_COMMAND` | `python3 -m prg32 cartridge build` | Command used by Compile Cartridge. |
| `SECRET_KEY` | development value | Flask session secret. Change for shared deployments. |

## Initialize or reset data

The database is created automatically. To reset a development checkout:

```bash
rm -rf data
python app.py
```

A starter project, starter sprite, and local publish profile are seeded when the database is empty.

## Database choice

SQLAlchemy abstracts all application database access. SQLite remains the
default because it needs no database server and works well for local use and a
small classroom. Existing `construction_kit.sqlite` files retain the same table
and column layout and can be opened directly after this update.

For a shared production deployment, use PostgreSQL rather than a SQLite file.
It handles concurrent writers, backups, permissions, and multiple application
workers more reliably. Install the production dependencies and set a URL:

```bash
pip install -r requirements-production.txt
export DATABASE_URL="postgresql+psycopg://prg32:password@database/prg32_kit"
python app.py
```

Do not commit the production password. Inject `DATABASE_URL` through the
hosting platform's secret or environment configuration.

## PRG32 toolchain check

The app can generate C without a PRG32 toolchain. To also create real `.prg32` cartridge files, make sure this works in the same shell or container:

```bash
python3 -m prg32 cartridge build --help
```

Then open a project and click **Compile Cartridge**.
