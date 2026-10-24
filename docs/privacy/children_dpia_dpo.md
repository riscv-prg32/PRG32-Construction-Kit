# Children, DPIA and DPO

**Version 1.0, 2026-10-21. Status: screening by the kit's maintainers. The controller and its
DPO decide.** Decisions go to [decisions.md](decisions.md).

## Children's data and Member State rules

The kit is made for pupils from about 11 to 16 years old. So:

- **Notices** are written for that age: short sentences, what it means for them, where to ask
  ([notices/](notices/)). Each notice has a version, and the version shown is recorded.
- **Consent** is used only for the optional services (cloud copies; publishing if it is not
  part of the course). Article 8 sets the age at which a child may consent alone to an
  information-society service. It is between 13 and 16 depending on the Member State: for
  example 14 in Italy and Spain, 15 in France, 16 in Germany and the Netherlands, 13 in
  Belgium and Denmark. Below that age a parent consents. **The kit does not know a pupil's age
  or check parental consent itself.** The controller decides how consent is collected
  (school form, parent portal) or switches those services off (D-3).
- **Teaching itself** (accounts, classes, games) proposes a public-task basis, not consent
  ([roles_and_legal_bases.md](roles_and_legal_bases.md)), so that no pupil is excluded.
- **Publishing** advises nicknames, and a teacher checks every submission at the Store.
- **Profiling and advertising:** none.

**Member State law to name (D-2):** the national education law that gives the school its
public task, the Article 8 age, and any rules on pupils' data, from national data protection
law or the education ministry.

## DPIA screening (Article 35)

| Criterion (EDPB WP248) | Applies? | Why |
|---|---|---|
| Vulnerable data subjects (children) | **yes** | pupils, mostly minors |
| Systematic monitoring | partly | the audit log records actions; teachers see class work |
| Large scale | depends | one school: no; a regional service: likely |
| New technology | no | ordinary web application |
| Matching or combining datasets | partly | school sign-in links to school accounts; shared accounts with the Store |
| Special categories / highly personal | no (not asked for) | free text could contain anything |
| Prevents exercising a right or using a service | no | the kit can be used without the optional services |

**Result of the screening: a DPIA is recommended.** Children are involved, together with at
least one other criterion. Many supervisory authorities' lists include large-scale processing
of minors' data at school. The controller decides (D-1), carries out the DPIA, and records
its outcome and date there. **Status: not done.**

What a DPIA can reuse from this folder:

- the description of processing: [ropa.md](ropa.md);
- the data flows: `docs/architecture.md`, section "Personal data and trust boundaries";
- the measures: [security_article32.md](security_article32.md);
- rights: [rights_requests.md](rights_requests.md);
- retention: [retention.md](retention.md).

## DPO (Article 37)

A **public authority or body**, which includes state schools in most Member States, **must
designate a DPO** (Art. 37(1)(a)). A private operator must do so if its core activities
involve large-scale monitoring or special categories. Otherwise it may choose to.

**Status (D-8): no DPO or counsel has reviewed this material.** The deploying controller
names its DPO in [decisions.md](decisions.md), and records the date the DPO reviewed these
records.
