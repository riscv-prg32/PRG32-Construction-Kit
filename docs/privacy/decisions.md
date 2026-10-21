# Decisions and open questions

**Version 1.0, 2026-10-21.** Each line is a decision only the deploying controller can make,
with its DPO or counsel. The kit's maintainers have only proposed answers.

**A deployment is NO-GO while any line marked "release blocker" is open.** The status is
checked by `tests/test_privacy_records.py`: a release record that claims GDPR readiness while
a blocker is open fails.

| Id | Decision | Proposal (kit maintainers) | Owner | Release blocker | Status | Decided on | Reference |
|---|---|---|---|---|---|---|---|
| D-0 | Name the controller, its privacy lead and its DPO; set `PRG32_PRIVACY_CONTROLLER` and `PRG32_PRIVACY_CONTACT` | the school or operator running the kit | controller | yes | open | | [README.md](README.md) |
| D-1 | Is a DPIA required? Carry it out and record the result | yes: children at school plus another criterion | controller + DPO | yes | open | | [children_dpia_dpo.md](children_dpia_dpo.md) |
| D-2 | Member State law: the public-task basis, and the Article 8 age | name the national education law; the age per country | controller + DPO | yes | open | | [children_dpia_dpo.md](children_dpia_dpo.md) |
| D-3 | Consent for optional services from minors: collect it, or switch the services off | switch cloud copies off unless the school collects parental consent | controller | yes (if cloud is on) | open | | [roles_and_legal_bases.md](roles_and_legal_bases.md) |
| D-4 | Legal basis for each activity | as proposed in roles_and_legal_bases.md | controller + DPO | yes | open | | [roles_and_legal_bases.md](roles_and_legal_bases.md) |
| D-5 | Retention periods, including the request register and server logs | the defaults in retention.md | controller | yes | open | | [retention.md](retention.md) |
| D-6 | Cloud providers: allowed or not; school-managed or personal accounts; transfer assessment | off by default; if on, school-managed accounts with the school's DPA | controller + DPO | yes (if cloud is on) | open | | [processors_and_transfers.md](processors_and_transfers.md) |
| D-7 | Cartridge Store: who runs it; the role; the agreement | the same school runs it; otherwise an Art. 26 arrangement | controller | yes (if the Store is used) | open | | [processors_and_transfers.md](processors_and_transfers.md) |
| D-8 | DPO or counsel review of this whole folder | needed before go-live | DPO | yes | open: no review yet | | [children_dpia_dpo.md](children_dpia_dpo.md) |
| D-9 | Processors: hosting and email agreements (Art. 28 checklist) | EU/EEA hosting | controller | yes | open | | [processors_and_transfers.md](processors_and_transfers.md) |
| D-10 | Breach contacts and the supervisory authority; a staffed exercise | fill in the playbook; a tabletop with the named people | controller | yes | open: a technical rehearsal only, 2026-10-21 | | [breach_playbook.md](breach_playbook.md) |
| D-11 | Store bearer tokens are stored in clear (S-1): accept the risk or require encryption | encrypt them, as cloud tokens are | controller + maintainers | no | open | | [security_article32.md](security_article32.md) |

When a decision is made:

1. write the decision, the date and the owner into its row;
2. change the record it affects;
3. add a line to [CHANGELOG.md](CHANGELOG.md).
