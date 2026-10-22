# Processors, subprocessors and international transfers

**Version 1.0, 2026-10-21. Status: TEMPLATE.** The kit runs only the services the operator
switches on. Each row is filled in by the controller for its own deployment (D-6, D-7 in
[decisions.md](decisions.md)).

## Register

| Service | Switched on by | Personal data it receives | Role | Location / transfer | Agreement (Art. 28 or other) | Status |
|---|---|---|---|---|---|---|
| Hosting (servers, storage, backups) | always | everything in [ropa.md](ropa.md) | processor | **choose the EU/EEA**; record the provider and region | DPA required | to be filled in |
| Email (SMTP) | `PRG32_SMTP_HOST` | email address, sign-up link | processor | provider's | DPA required | to be filled in |
| School identity provider (OIDC/SAML) | admin settings or `PRG32_OIDC_*` | redirect only. The kit *receives* issuer, subject, email and role. | the school's existing processor | the school's | the school's existing DPA | to be confirmed |
| Google Drive | `PRG32_CLOUD_GOOGLE_*` and the person's consent | the person's projects, written to a folder the app created (`drive.file` scope) | separate controller for the person's account; processor for school-managed Workspace accounts | **USA** possible: EU-US Data Privacy Framework (Google LLC certified) plus SCCs in Google's terms | Google Workspace for Education DPA if school accounts; personal accounts: none | D-6 |
| Microsoft OneDrive | `PRG32_CLOUD_ONEDRIVE_*` and the person's consent | as above (`Files.ReadWrite.AppFolder`) | as above | **USA** possible: EU-US DPF (Microsoft certified), EU Data Boundary for business accounts | Microsoft Products and Services DPA if school accounts | D-6 |
| GitHub | `PRG32_CLOUD_GITHUB_*` and the person's consent | the person's projects, committed as files to a repository the person installed the kit's GitHub App on (Contents read/write, Metadata read; ADR-0025) | separate controller for the person's account; processor for GitHub Enterprise or GitHub Education accounts the school manages | **USA**: EU-US DPF (GitHub, Inc. / Microsoft certified) plus SCCs in GitHub's terms | GitHub Data Protection Agreement if school accounts; personal accounts: none | D-6 |
| PRG32 Cartridge Store | a publish profile; `PRG32_SSO_PEER_URL` for shared accounts | published games, author name; with shared accounts: username, email, role, password hash | same controller, or joint/separate controller if another organisation runs it | where the Store runs | Art. 26 arrangement or controller agreement if another organisation (D-7) | D-7 |

The kit sends nothing anywhere else: no telemetry, no analytics, no CDN (every browser
library is served from the kit itself, ADR-0012).

## Article 28 checklist for each processor

For each processor, record in [decisions.md](decisions.md) that its agreement covers:

- [ ] processing only on documented instructions, including on transfers (28(3)(a));
- [ ] confidentiality of its staff (28(3)(b));
- [ ] Article 32 security measures, described (28(3)(c));
- [ ] subprocessors only with authorisation, and **notice of changes**, with the right to object (28(2), 28(4));
- [ ] help with rights requests and with Articles 32 to 36 (28(3)(e)(f));
- [ ] **deletion or return of all data at the end**, including backups, and a date (28(3)(g));
- [ ] audits and information (28(3)(h));
- [ ] **breach notification without undue delay**, so the controller can meet 72 hours (Art. 33(2)).

## Transfer assessment (Chapter V)

| Flow | Mechanism | Supplementary measures | Assessment |
|---|---|---|---|
| Cloud copies to Google/Microsoft/GitHub (USA possible) | DPF adequacy decision (2023) for certified recipients; SCCs as fallback | Optional and consent-based. Only the person's own projects, in an app folder. Tokens encrypted at rest and revocable. | The controller decides whether to allow it for minors (D-6). The kit can switch it off entirely (no `PRG32_CLOUD_*` settings). |
| Hosting outside the EEA | none by default | — | **Avoid.** If unavoidable: SCCs plus a transfer impact assessment, recorded here. |
| Cartridge Store outside the EEA | — | — | Run it in the EEA, or assess as above. |

## Settings that create a transfer, and the kit's warnings

The kit cannot know where a service runs. The operator checks these settings against the
register above before going live:

- `PRG32_CLOUD_GOOGLE_CLIENT_ID`, `PRG32_CLOUD_ONEDRIVE_CLIENT_ID`: cloud copies on;
- `PRG32_SMTP_HOST`: email via that provider;
- `PRG32_OIDC_*`, and identity providers added under Admin → School sign-in;
- `PRG32_SSO_PEER_URL`: shared accounts with a Cartridge Store;
- publish profiles with a Store URL (only Stores the administrator allowed, `PRG32_STORE_ALLOWED_ORIGINS`).

## Change notification

When a processor announces a new subprocessor, the privacy lead:

1. updates this register;
2. checks the transfer;
3. objects within the period in the agreement if needed;
4. records it in [CHANGELOG.md](CHANGELOG.md).
