# Breach exercises and the breach register

| Date | Kind | Who took part | Record | Open findings |
|---|---|---|---|---|
| 2026-10-21 | technical rehearsal (scripted, synthetic pupils) | kit maintainers only | [2026-10-21-breach-rehearsal/record.md](2026-10-21-breach-rehearsal/record.md) | F-4 (F-2, F-3 fixed the same day: S-5, S-6) |

**Not done yet:** a staffed tabletop exercise with the controller's incident lead, privacy
lead, DPO and school leadership (decision D-10). Repeat it at least once a year.

## Template: one breach, or one exercise (Article 33(5))

| Field | Content |
|---|---|
| Reference | |
| T0 (became aware) and how it was found | |
| What happened (facts, timeline) | |
| Data and people affected (number, children?) | |
| Likely consequences | |
| Containment and other measures | |
| Evidence kept (files, SHA-256, where) | |
| Risk: none / risk / high | |
| Authority notified? When, reference, or why not | |
| People told? When, how, or why not | |
| Processors / Store operator told? | |
| Lessons and changes | |
| Closed on, by | |

To rehearse the technical steps again on a throwaway kit:

```bash
python3 tools/breach_rehearsal.py --out docs/privacy/exercises/<date>-breach-rehearsal
```
