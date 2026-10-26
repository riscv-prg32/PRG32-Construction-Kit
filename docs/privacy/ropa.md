# Record of processing activities (Article 30) - PRG32 Construction Kit, field level

<!-- Generated from ropa.json by tools/render_ropa.py: edit the JSON, then run the tool. -->

Version 1.0, reviewed 2026-10-21. Owner: the operator's privacy lead (name it in decisions.md).

**Status:** TEMPLATE for the deploying school or operator: the kit's behaviour is described exactly; legal decisions are proposals.

**Controller:** the school or operator running the kit (fill in: name, address, contact, DPO).

Each item lists the database columns it covers (field level). Legal bases marked PROPOSED are
not decisions: see [decisions.md](decisions.md).

## account

| | |
|---|---|
| Data | who a person is in the kit |
| People | students, teachers and facilitators, administrators |
| Purpose | sign in; keep each person's work theirs; teachers' roles |
| Legal basis | Art. 6(1)(e) public task of the school (or 6(1)(b)/(f) for a private operator); PROPOSED - not decided: the controller confirms with its DPO (decisions.md) |
| Special categories | none collected; usernames should not reveal health, religion or similar (notice to staff) |
| Who can see it | the person; administrators; teachers see usernames of their class members |
| Recipients | the Cartridge Store when shared accounts are on (sso.py); the hosting provider (processor) |
| Where | the server chosen by the operator (configure in the EU/EEA, see processors_and_transfers.md) |
| Kept for | while the account exists; switched-off accounts are listed for review (retention.py) |
| Deleted by | erasure request (privacy.erase_account) or the administrator's delete with items |
| Transfers | none by the kit; Cartridge Store only if the operator runs it outside the EEA |
| Review owner | the operator's privacy lead (name it in decisions.md) |
| Next review | 2027-10-21 or on any change to the kit's data model |
| Fields | `users`: id, username, email, role, kit_role, created_at, updated_at, last_login, disabled_at, session_epoch, restricted_at; `user_groups`: user_id, group_id |

## credentials

| | |
|---|---|
| Data | passwords, API tokens and sign-up links (all stored as hashes) |
| People | students, teachers, administrators |
| Purpose | authentication; scripted access the person asked for |
| Legal basis | same as account; PROPOSED - not decided: the controller confirms with its DPO (decisions.md) |
| Special categories | none |
| Who can see it | nobody reads them in clear: only hashes are stored; the person lists and revokes their tokens |
| Recipients | an email provider (SMTP, processor) carries the sign-up link |
| Where | the server chosen by the operator (configure in the EU/EEA, see processors_and_transfers.md) |
| Kept for | tokens until revoked or expired; sign-up links one day after expiry or use (retention.py) |
| Deleted by | erasure; token revocation; retention |
| Transfers | SMTP provider: see processors_and_transfers.md |
| Review owner | the operator's privacy lead (name it in decisions.md) |
| Next review | 2027-10-21 or on any change to the kit's data model |
| Fields | `users`: password_hash; `api_tokens`: id, user_id, token_hash, label, created_at, last_used, scopes, expires_at; `registration_tokens`: id, email, token_hash, created_at, expires_at, used_at |

## school_identity

| | |
|---|---|
| Data | the school sign-in link: issuer, subject, email |
| People | students, teachers |
| Purpose | school sign-in (ADR-0016), never joining accounts by email |
| Legal basis | Art. 6(1)(e) (school) ; PROPOSED - not decided: the controller confirms with its DPO (decisions.md) |
| Special categories | none |
| Who can see it | the person; administrators |
| Recipients | none: the identity provider sent it |
| Where | the server chosen by the operator (configure in the EU/EEA, see processors_and_transfers.md) |
| Kept for | while the account exists |
| Deleted by | erasure; unlinking on the Account page |
| Transfers | none by the kit (the identity provider is the school's own processor) |
| Review owner | the operator's privacy lead (name it in decisions.md) |
| Next review | 2027-10-21 or on any change to the kit's data model |
| Fields | `external_identities`: id, user_id, provider, issuer, subject, email, created_at, last_login; `users`: external_provider, external_id |

## classes

| | |
|---|---|
| Data | classes and who is in them, with their role |
| People | students, teachers |
| Purpose | teachers supervising their students' work (read only) |
| Legal basis | Art. 6(1)(e) (school); PROPOSED - not decided: the controller confirms with its DPO (decisions.md) |
| Special categories | none; class names should not reveal special needs |
| Who can see it | members of the class; administrators |
| Recipients | none |
| Where | the server chosen by the operator (configure in the EU/EEA, see processors_and_transfers.md) |
| Kept for | until the class is deleted |
| Deleted by | erasure removes membership; teachers delete classes |
| Transfers | none |
| Review owner | the operator's privacy lead (name it in decisions.md) |
| Next review | 2027-10-21 or on any change to the kit's data model |
| Fields | `classes`: id, name, created_by, created_at; `class_members`: class_id, user_id, role, added_at |

## student_work

| | |
|---|---|
| Data | games, block programs, source code, sprites, sounds, assets and their history |
| People | students, teachers |
| Purpose | making games: the teaching activity itself |
| Legal basis | Art. 6(1)(e) (school); PROPOSED - not decided: the controller confirms with its DPO (decisions.md) |
| Special categories | none expected; free text (titles, author, comments in code) may contain anything a student types: notices ask for nicknames |
| Who can see it | the owner; teachers of their classes (read only); administrators |
| Recipients | the Cartridge Store when the person publishes; their own cloud account when they connect one |
| Where | the server chosen by the operator (configure in the EU/EEA, see processors_and_transfers.md) |
| Kept for | until deleted; 'Recently deleted' for PRG32_KIT_TRASH_DAYS (30) then removed |
| Deleted by | the owner; retention; erasure |
| Transfers | only by the person's own choice (cloud, publishing) |
| Review owner | the operator's privacy lead (name it in decisions.md) |
| Next review | 2027-10-21 or on any change to the kit's data model |
| Fields | `projects`: id, title, description, author, tags, blocks_json, game_json, deleted_at, version, created_at, updated_at, owner_id; `project_revisions`: id, project_id, owner_id, created_at, seq, reason, manifest, source, assets, digest, child_ids; `sprites`: id, project_id, name, width, height, pixels, data_url, palette, created_at, updated_at, owner_id; `assets`: id, project_id, name, kind, content_type, data, version, created_at, updated_at, owner_id |

## builds

| | |
|---|---|
| Data | builds, compiler logs, generated C and assembly, cartridges, debug maps, uploaded files |
| People | students, teachers |
| Purpose | compiling games; downloading cartridges |
| Legal basis | as student work; PROPOSED - not decided: the controller confirms with its DPO (decisions.md) |
| Special categories | none |
| Who can see it | the owner; class teachers (read); administrators |
| Recipients | none; the build sandbox has no network |
| Where | the server chosen by the operator (configure in the EU/EEA, see processors_and_transfers.md); files in <data>/builds/<build_id>/ and <data>/artifacts/ |
| Kept for | the newest PRG32_KIT_KEEP_BUILDS (10) builds per project |
| Deleted by | retention; erasure (with their folders and files) |
| Transfers | none |
| Review owner | the operator's privacy lead (name it in decisions.md) |
| Next review | 2027-10-21 or on any change to the kit's data model |
| Fields | `builds`: id, project_id, status, log, c_artifact_id, bundle_artifact_id, metadata, created_at, updated_at, owner_id; `artifacts`: id, project_id, sprite_id, kind, name, content_type, path, text_content, metadata, created_at, updated_at, owner_id |

## cloud

| | |
|---|---|
| Data | connected Google Drive, OneDrive or GitHub account, the chosen GitHub repository and branch, and which projects are synced |
| People | students, teachers |
| Purpose | copies of the person's own games in their own cloud folder or GitHub repository (ADR-0019, ADR-0025) |
| Legal basis | Art. 6(1)(a) consent of the person (or a parent, below the national age: decisions.md); PROPOSED - not decided: the controller confirms with its DPO (decisions.md) |
| Special categories | none |
| Who can see it | the person; tokens are encrypted and never shown to anyone |
| Recipients | Google, Microsoft or GitHub, chosen by the person |
| Where | the server chosen by the operator (configure in the EU/EEA, see processors_and_transfers.md); the copies are in the person's own cloud account |
| Kept for | until disconnected; tokens are revoked at Google and GitHub on disconnect |
| Deleted by | disconnect; erasure (revokes where possible) |
| Transfers | Google LLC / Microsoft Corp. / GitHub, Inc. (Microsoft): EU-US Data Privacy Framework and SCCs; transfer assessment in processors_and_transfers.md |
| Review owner | the operator's privacy lead (name it in decisions.md) |
| Next review | 2027-10-21 or on any change to the kit's data model |
| Fields | `cloud_accounts`: id, user_id, provider, account_id, account_name, scopes, tokens, needs_reconnect, connected_at, options; `cloud_links`: id, user_id, provider, account_id, project_id, file_id, remote_revision, content_sha256, local_version, synced_at |

## publishing

| | |
|---|---|
| Data | Store profiles (with the Store's bearer token, encrypted at rest and never returned by the API) and what was published where |
| People | students with the publisher role, teachers |
| Purpose | publishing games to the Cartridge Store, each version once |
| Legal basis | Art. 6(1)(e) or (a) depending on whether publishing is part of the course; PROPOSED - not decided: the controller confirms with its DPO (decisions.md) |
| Special categories | none |
| Who can see it | the person; administrators |
| Recipients | the Cartridge Store chosen |
| Where | the server chosen by the operator (configure in the EU/EEA, see processors_and_transfers.md) |
| Kept for | while the account exists |
| Deleted by | erasure; the Store's copies are listed for its operator |
| Transfers | only to the Store's location |
| Review owner | the operator's privacy lead (name it in decisions.md) |
| Next review | 2027-10-21 or on any change to the kit's data model |
| Fields | `publish_profiles`: id, name, store_url, bearer_token, token_set_at, created_at, updated_at, owner_id; `publish_attempts`: id, digest, user_id, profile_id, artifact_id, state, result, store_host, cartridge_id, cartridge_version, bundle_sha256, created_at, updated_at |

## deployment

| | |
|---|---|
| Data | which cartridge was put on which console, PRG32-QT or QEMU, in which slot, each step's log, the target's answers and a screenshot; the consoles and PRG32-QT addresses an administrator registered; performance evaluations of the PRG32 Evaluation cartridge on those targets (each run's numbers) |
| People | students, teachers |
| Purpose | running a student's game on a classroom PRG32 console or emulator, and showing them whether it worked |
| Legal basis | Art. 6(1)(e) (part of the course); PROPOSED - not decided: the controller confirms with its DPO (decisions.md) |
| Special categories | none |
| Who can see it | the person; administrators |
| Recipients | none: the console, PRG32-QT or QEMU receives the cartridge only, never a name |
| Where | the server chosen by the operator (configure in the EU/EEA, see processors_and_transfers.md) |
| Kept for | while the account exists |
| Deleted by | erasure deletes the deployments, the evaluations and their folders; a registered console stays, without who registered it |
| Transfers | none |
| Review owner | the operator's privacy lead (name it in decisions.md) |
| Next review | 2027-10-21 or on any change to the kit's data model |
| Fields | `deployments`: id, owner_id, project_id, artifact_id, target, target_kind, target_name, slot, status, progress, cancel_requested, log, result, created_at, updated_at; `deploy_targets`: id, name, kind, url, notes, created_by, created_at; `evaluations`: id, owner_id, project_id, artifact_id, target, target_kind, target_name, slot, repetitions, warm_up, status, progress, cancel_requested, log, result, created_at, updated_at |

## security_log

| | |
|---|---|
| Data | audit events (who did what, when, from which address; API-token use; sign-ins from new addresses) and sign-in counters (hashed) |
| People | everyone who signs in or tries to |
| Purpose | security, accountability and incident investigation (Art. 32, 33) |
| Legal basis | Art. 6(1)(c)/(e) or (f): security of processing; PROPOSED - not decided: the controller confirms with its DPO (decisions.md) |
| Special categories | none |
| Who can see it | administrators only |
| Recipients | none |
| Where | the server chosen by the operator (configure in the EU/EEA, see processors_and_transfers.md) |
| Kept for | PRG32_KIT_AUDIT_DAYS (365); counters minutes |
| Deleted by | retention; erasure pseudonymises the person and drops their address |
| Transfers | none |
| Review owner | the operator's privacy lead (name it in decisions.md) |
| Next review | 2027-10-21 or on any change to the kit's data model |
| Fields | `audit_events`: id, created_at, actor_id, actor_name, action, target_type, target_id, outcome, client, metadata; `auth_throttle`: key, window_start, attempts |

## shared_accounts

| | |
|---|---|
| Data | account changes waiting to reach the Cartridge Store; used single sign-on tickets |
| People | students, teachers |
| Purpose | one account for the kit and the Cartridge Store (shared accounts, optional) |
| Legal basis | as account; PROPOSED - not decided: the controller confirms with its DPO (decisions.md) |
| Special categories | none |
| Who can see it | nobody reads it; the kit sends it |
| Recipients | the Cartridge Store |
| Where | the server chosen by the operator (configure in the EU/EEA, see processors_and_transfers.md) |
| Kept for | until delivered; tickets until they expire (minutes) |
| Deleted by | delivery; erasure |
| Transfers | only to the Store's location |
| Review owner | the operator's privacy lead (name it in decisions.md) |
| Next review | 2027-10-21 or on any change to the kit's data model |
| Fields | `sso_outbox`: email, payload, created_at, attempts; `sso_nonces`: nonce, expires_at |

## privacy_records

| | |
|---|---|
| Data | which notice versions a person was shown; rights requests and their outcome |
| People | students, teachers, staff handling requests |
| Purpose | showing that notices were given and requests answered (Art. 5(2), 12) |
| Legal basis | Art. 6(1)(c) legal obligation; PROPOSED - not decided: the controller confirms with its DPO (decisions.md) |
| Special categories | the free-text details may hold anything: staff keep them short |
| Who can see it | the person (their own); administrators |
| Recipients | none |
| Where | the server chosen by the operator (configure in the EU/EEA, see processors_and_transfers.md) |
| Kept for | notices: while the account exists; open requests always; answered requests PRG32_KIT_PRIVACY_REQUEST_DAYS after the answer (0 = keep; the controller decides, decisions.md D-5), under a pseudonym after erasure |
| Deleted by | erasure (notices); requests pseudonymised |
| Transfers | none |
| Review owner | the operator's privacy lead (name it in decisions.md) |
| Next review | 2027-10-21 or on any change to the kit's data model |
| Fields | `privacy_notice_records`: id, user_id, notice, version, context, shown_at; `privacy_requests`: id, user_id, subject_ref, kind, details, status, verified_by, received_at, due_at, extension_reason, handled_by, completed_at, outcome |

## configuration

| | |
|---|---|
| Data | school sign-in settings, the admin Settings page values (sealed secrets) and group names (no person) |
| People | none |
| Purpose | running the kit |
| Legal basis | not personal data |
| Special categories | none |
| Who can see it | administrators |
| Recipients | none |
| Where | the server chosen by the operator (configure in the EU/EEA, see processors_and_transfers.md) |
| Kept for | while used |
| Deleted by | administrators |
| Transfers | none |
| Review owner | the operator's privacy lead (name it in decisions.md) |
| Next review | 2027-10-21 or on any change to the kit's data model |
| Fields | `identity_providers`: id, slug, name, issuer, client_id, client_secret_ref, scopes, role_claim, role_map, new_account_role, allowed_domains, enabled, created_at, updated_at; `groups`: id, name, created_at; `site_settings`: key, value, updated_at, revision |

## Outside the database

| Store | Data | Where | Kept for | Deleted by | Personal |
|---|---|---|---|---|---|
| session_cookie | signed session cookie: account id, session number, sign-in time | the person's browser | PERMANENT_SESSION_LIFETIME (fixed from sign-in) | signing out; ending all sessions; erasure invalidates it | yes |
| browser_storage | cookie prg32_locale: the interface language chosen; IndexedDB prg32-kit-guest: guest games; localStorage prg32-*: code view per project, debugger breakpoints and view, last AudioStudio project, interface language for offline pages, Day or Night colours, storage notice read (list on /privacy#storage) | the person's browser only | until the person clears it | the person (Clear site data); a guest's games are never kept on the server | yes |
| service_worker_cache | static files only, never signed-in pages | the browser | until the next cache version | automatic | no |
| build_folders | <data>/builds/<build_id>/: sources and outputs of one build | the server chosen by the operator (configure in the EU/EEA, see processors_and_transfers.md) | as builds | with the build | yes |
| artifact_files | <data>/artifacts/: uploads and AudioStudio samples (one folder per owner) | the server chosen by the operator (configure in the EU/EEA, see processors_and_transfers.md) | as artifacts | with the artifact (retention.delete_artifact); erasure removes the owner's sample folder | yes |
| backups | tools/backup_restore.py archives: the whole database, folders and the secret key | chosen by the operator; keep encrypted, in the EEA | PRG32_KIT_BACKUP_DAYS (35), enforced with backup_restore.py prune | prune; after a restore, prg32-privacy-reapply with the erasure register | yes |
| server_logs | web server and proxy access logs (addresses, times, paths), application errors | the operator's servers | set by the operator: recommended 14 days (retention.md) | log rotation | yes |
| email | sign-up and password emails | the operator's SMTP provider and the person's mailbox | the provider's | the provider's | yes |
| tickets_in_transit | single sign-on tickets and OAuth codes and tokens, in transit | between the browser, the kit, the Store and the providers (HTTPS) | minutes; refresh tokens encrypted at rest (cloud) | expiry | yes |
| support_evidence | screenshots, logs and recordings kept as release evidence (docs/evidence) | the kit's repository | kept with the release | never contains real people: synthetic users only (visual manifest checks) | no |
| guest_requests | a guest's blocks, code, sound or sprite, sent to generate code, preview sound or build the game to run it (ADR-0023, ADR-0024) | server memory, and for a run build a private build folder removed as soon as the cartridge is read | none: not written, not logged | automatic at the end of the request | no |
| deployment_folders | each deployment's screenshot, QEMU flash copy and serial log (DATA_DIR/deployments/<id>/); each evaluation's dataset (DATA_DIR/evaluations/<id>/dataset.json) | the server's data folder | while the account exists | erasure deletes the folders with the deployments | yes |
