"""A technical rehearsal of the breach playbook on a throwaway kit (docs/privacy/breach_playbook.md).

    python3 tools/breach_rehearsal.py --out docs/privacy/exercises/2026-10-21-breach-rehearsal

It is NOT a staffed exercise: the controller, DPO and school leadership were not involved.
It checks that the kit gives the evidence and the controls the playbook relies on, and
writes a record with the playbook's fields.

Scenario (synthetic people only, addresses from the documentation ranges of RFC 5737):

1. Five synthetic pupils in class "3B". Pupil s03's password is guessed or leaked.
2. Someone else signs in as s03 from 203.0.113.50, downloads s03's personal data, makes
   an API token and reads s03's projects with it.
3. The incident lead finds it in the audit log, contains it (ends s03's sessions, revokes
   the token, resets the password), preserves the evidence with SHA-256, and records the
   assessment and the notification decision against the 72-hour clock.

Into --out: timeline.json, audit-extract.json (the incident's audit events), record.md.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ADMIN_PASSWORD = "rehearsal-admin-password-1"
PUPIL_PASSWORD = "rehearsal-pupil-password-1"
OFFICE, ATTACKER = "198.51.100.10", "203.0.113.50"


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def browser(app, address: str, login: tuple[str, str] | None):
    client = app.test_client()
    client.environ_base.update({"REMOTE_ADDR": address, "HTTP_X_PRG32_KIT": "1"})
    if login:
        response = client.post("/auth/login", data={"username": login[0], "password": login[1]})
        assert response.status_code == 302, response.get_data(as_text=True)[:200]
    return client


def run(out: Path) -> dict:
    from prg32_construction_kit import create_app

    timeline: list[dict] = []

    def mark(step: str, what: str, **facts) -> None:
        timeline.append({"at": now(), "step": step, "what": what, **facts})

    with tempfile.TemporaryDirectory() as folder:
        data = Path(folder)
        app = create_app({"TESTING": True, "DATA_DIR": data, "DB_PATH": data / "kit.sqlite",
                          "BUILD_ROOT": data / "builds", "ARTIFACT_ROOT": data / "artifacts",
                          "ADMIN_PASSWORD": ADMIN_PASSWORD, "SSO_SECRET": "", "SSO_PEER_URL": ""})
        admin = browser(app, OFFICE, ("admin", ADMIN_PASSWORD))
        klass = admin.post("/api/classes", json={"name": "3B"}).get_json()
        ids = {}
        for number in range(1, 6):
            name = f"s{number:02d}"
            made = admin.post("/api/users", json={"username": name, "email": f"{name}@rehearsal.test",
                                                  "password": PUPIL_PASSWORD}).get_json()
            ids[name] = made["id"]
            admin.post(f"/api/classes/{klass['id']}/members", json={"username": name})
            pupil = browser(app, OFFICE, (name, PUPIL_PASSWORD))
            pupil.post("/api/projects", json={"title": f"{name}'s game"})
        mark("setup", "throwaway kit: 5 synthetic pupils in class 3B, one project each")

        # --- the incident (what the attacker does) --------------------------------------------
        browser(app, ATTACKER, None).post("/auth/login", data={"username": "s03", "password": "wrong-guess"})
        attacker = browser(app, ATTACKER, ("s03", PUPIL_PASSWORD))
        stolen = attacker.get("/api/me/privacy/export").get_json()
        token = attacker.post("/auth/tokens", json={"label": "x", "scopes": ["read"]}).get_json()["token"]
        api = app.test_client()
        api.environ_base.update({"REMOTE_ADDR": ATTACKER})
        read = api.get("/api/projects", headers={"Authorization": f"Bearer {token}"}).get_json()
        projects = read.get("projects", read) if isinstance(read, dict) else read
        owners = {project.get("owner_id") for project in projects}
        mark("incident", "someone signs in as s03 from the attacker's address, downloads s03's data, "
             "makes an API token and reads projects with it",
             tables_in_download=sorted(key for key, rows in stolen["tables"].items() if rows),
             projects_read={"own": sum(project.get("owner_id") == ids["s03"] for project in projects),
                            "shared_examples_without_owner": sum(project.get("owner_id") is None for project in projects),
                            "other_pupils": sum(project.get("owner_id") not in (None, ids["s03"]) for project in projects)},
             other_pupils_reachable=bool(owners - {None, ids["s03"]}))

        # --- T0: detection --------------------------------------------------------------------
        events = admin.get("/api/admin/audit?limit=500").get_json()["events"]
        suspicious = [event for event in events if event.get("client") == ATTACKER]
        t0 = now()
        mark("T0 detection", "the audit log shows sign-in activity and a data download for s03 from an address "
             "never seen before", t0=t0, events_from_that_address=len(suspicious),
             actions=sorted({event["action"] for event in suspicious}))

        # --- containment ------------------------------------------------------------------------
        admin.post(f"/api/users/{ids['s03']}/sessions/revoke")
        tokens_gone = admin.post(f"/api/users/{ids['s03']}/deactivate").status_code == 200   # deletes its tokens
        admin.put(f"/api/users/{ids['s03']}", json={"password": "rehearsal-new-password-2"})
        admin.post(f"/api/users/{ids['s03']}/reactivate")
        still_works = api.get("/api/projects", headers={"Authorization": f"Bearer {token}"}).status_code
        attacker_session = attacker.get("/api/projects").status_code
        mark("containment", "sessions ended, account switched off and on again (its API tokens are deleted), "
             "password reset", token_after=still_works, attacker_session_after=attacker_session,
             tokens_deleted=tokens_gone)

        # --- evidence -----------------------------------------------------------------------------
        events = admin.get("/api/admin/audit?limit=500").get_json()["events"]
        incident = [event for event in events
                    if event.get("client") == ATTACKER or str(event.get("target_id")) == str(ids["s03"])]
        extract = json.dumps({"exported_at": now(), "events": incident}, indent=1, sort_keys=True) + "\n"
        out.mkdir(parents=True, exist_ok=True)
        (out / "audit-extract.json").write_text(extract)
        mark("evidence", "audit events of the incident exported", file="audit-extract.json",
             sha256=hashlib.sha256(extract.encode()).hexdigest(), events=len(incident))

    # --- assessment and decision (the playbook's fields; a person decides these for real) ------
    deadline = (datetime.datetime.fromisoformat(t0) + datetime.timedelta(hours=72)).isoformat(timespec="seconds")
    assessment = {
        "people": 1, "children": True,
        "data": "one pupil's account details (username, email, class), notice records, own projects and the "
                "audit events about them; no other pupil's data; no password or token in clear",
        "consequences": "the pupil's email and school class known to an unauthorised person; their games read",
        "risk": "risk (not high): a minor's contact details and school class disclosed; contained within minutes",
        "notify_authority": "yes, within 72 hours of T0 (" + deadline + "), because a minor's data was disclosed "
                            "and the risk is not unlikely",
        "tell_the_person": "Art. 34 not required (not high risk); the school's policy is to tell the pupil and family "
                           "anyway, with what to do (new password, watch for phishing)",
        "processors_to_tell": "none involved",
        "measures": ["sessions ended", "API tokens deleted", "password reset",
                     "consider: alert on sign-ins from new addresses (finding F-2)"],
    }
    mark("assessment", "risk assessed and notification decided (rehearsed by the maintainers; a real "
         "decision is the controller's and the DPO's)", deadline_72h=deadline)
    findings = [
        {"id": "F-1", "finding": "Local sign-ins were not in the audit log before this work; added (login, "
                                 "login_failed with the address, never the typed text)", "status": "fixed"},
        {"id": "F-2", "finding": "No alert on sign-ins from a new address: detection relies on someone reading the "
                                 "audit log", "status": "open"},
        {"id": "F-3", "finding": "Ordinary reads of projects are not audited (S-5): the extent of what an API "
                                 "token read is inferred from its scope and last_used", "status": "open"},
        {"id": "F-4", "finding": "Contacts in the playbook are blank until the controller fills them in (D-10)",
         "status": "open"},
    ]
    record = {"exercise": "technical rehearsal (not a staffed exercise)", "run_at": now(), "t0": t0,
              "deadline_72h": deadline, "timeline": timeline, "assessment": assessment, "findings": findings}
    (out / "timeline.json").write_text(json.dumps(record, indent=1) + "\n")
    lines = ["# Breach rehearsal", "", f"Run {record['run_at']} with `tools/breach_rehearsal.py`. **A technical "
             "rehearsal by the kit's maintainers, not a staffed exercise:** the controller, the DPO and school "
             "leadership were not involved (decision D-10).", "",
             "Synthetic people only. The addresses come from the RFC 5737 documentation ranges.", "",
             "## Timeline", "", "| When (UTC) | Step | What |", "|---|---|---|"]
    lines += [f"| {item['at']} | {item['step']} | {item['what']} |" for item in timeline]
    lines += ["", f"72-hour deadline from T0: **{deadline}**.", "", "## Assessment and decision (rehearsed)", "",
              "| | |", "|---|---|"]
    lines += [f"| {key.replace('_', ' ')} | {', '.join(value) if isinstance(value, list) else value} |"
              for key, value in assessment.items()]
    lines += ["", "## Findings", "", "| Id | Finding | Status |", "|---|---|---|"]
    lines += [f"| {item['id']} | {item['finding']} | {item['status']} |" for item in findings]
    lines += ["", "Evidence: `audit-extract.json`, with its SHA-256 in `timeline.json`."]
    (out / "record.md").write_text("\n".join(lines) + "\n")
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    record = run(args.out)
    for item in record["timeline"]:
        print(f"{item['at']}  {item['step']}: {item['what']}")
    print(f"Record written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
