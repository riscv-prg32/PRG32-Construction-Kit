# Live tests: one step

Most of the kit's tests run on their own. A few talk to real services: a Cartridge Store,
a school's identity provider, Google Drive or OneDrive, the PRG32 firmware in QEMU. These
**live suites** run only against throwaway or test services, never a school's real data.

Run every live suite this computer can run:

```bash
python3 tools/run_live_suites.py --out live-evidence
```

| Suite | What it proves | It runs when |
|---|---|---|
| `store` | publishing and shared accounts (one username, signed in on the Store's own forms with their CSRF token and privacy notice) with a real Cartridge Store, started on 127.0.0.1 with test data | the CartridgeStore checkout is next to the kit, or `PRG32_CARTRIDGE_STORE_SOURCE` names one |
| `oidc-keycloak` | school sign-in with a real identity provider (Keycloak, started in Docker and thrown away) | Docker is running |
| `oidc-external` | school sign-in with an institution's **test** tenant | `PRG32_LIVE_OIDC_ISSUER` and the other settings in `identity_live_testing.md` are set |
| `cloud` | saving to Google Drive or OneDrive with a **test** account | `PRG32_LIVE_CLOUD=google` or `onedrive` and the settings in `cloud_storage.md` are set |
| `qemu` | the PRG32 firmware's whole audio recording equals the browser's | ESP-IDF is set up (`. $HOME/esp-idf/export.sh`) |

A suite whose service is missing is reported as **not run**, with the reason. It never
counts as passed, and a suite where every test was skipped is not a pass either.

Settings come from the environment only. Nothing secret is kept:

- `summary.json` lists which setting names were present, never their values;
- the logs replace the values of settings whose names contain SECRET, TOKEN or PASSWORD
  with `<redacted>`;
- they also drop the computer's name and show the home folder as `~`.

After ESP-IDF's `export.sh`, `python3` is ESP-IDF's own Python. Run the tool with the kit's
Python, for example `/usr/local/bin/python3 tools/run_live_suites.py ...`.

The run of 2026-10-21 is in `docs/evidence/live/2026-10-21/`:

- passed: Store (11), Keycloak (9), QEMU (1);
- not run, with no test tenant: the external school tenant and the cloud accounts.
