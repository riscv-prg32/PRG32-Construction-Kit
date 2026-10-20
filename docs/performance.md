# How fast the kit must be on classroom computers

Classrooms often have low-end laptops or Chromebooks. `tests/test_performance_browser.py`
stands in for one with Chromium and its CPU slowed down 4 times (DevTools CPU
throttling), the kit served locally as on a school server. It runs in CI with the
other browser suites and cannot be skipped there.

| What | Budget | Measured (2026-10-20, Apple M-series, 4× slower) |
| --- | --- | --- |
| Dashboard ready (projects listed) | 4 s | 0.16 s |
| IDE ready (editors and blocks loaded) | 8 s | 0.83 s |
| Player: a real PRG32 cartridge running (3 frames drawn) | 6 s | 0.43 s |
| JavaScript downloaded by the dashboard | 0.6 MB | 0.20 MB |
| JavaScript downloaded by the IDE (Monaco and Blockly) | 12 MB | 5.4 MB |

The budgets are generous on purpose: CI machines are slower than a developer's laptop,
and the test should catch a page that becomes much heavier or slower, not small
changes. If a budget is reached, first look at what got bigger
(`performance.getEntriesByType('resource')` in the browser), then decide whether the
budget or the page should change.

Not measured yet: a real classroom device (a Chromebook or an old Windows laptop)
over the school's Wi-Fi. To record one, open the dashboard, the IDE and the Player
with the browser's DevTools *Performance* panel and add the numbers here.
