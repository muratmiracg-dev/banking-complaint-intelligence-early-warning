# Validation record

Local verification completed on 3 October 2026, using the analytical snapshot built on 1 October 2026.

| Check | Outcome |
|---|---|
| Python unit and local API tests | 28 passed |
| Python / browser prediction comparisons | 18 passed; score differences below 1e-7 |
| Committed artifact reconciliation | Passed: weekly counts, matrix totals, model dimensions, browser copies |
| Offline Chromium smoke | Passed: six views, search/filtering, detail dialogs and classification |
| Mobile layout | Checked at 390 × 844; no page-level horizontal overflow |
| Source files and private local records | Excluded from Git |

The Python tests verify that future observations cannot alter earlier count scores, that a current observation cannot alter its own baseline, and that monitoring cannot produce flags before the series family is frozen. Other checks exercise source schema errors, duplicate IDs, the exclusive end date, formula-safe exports, local origin/host checks and traversal attempts.

The browser smoke test opens the actual files, uses the controls, exercises invalid text input and records screenshots. Screenshots are in `docs/assets/`; they are application captures, not design mockups.

## Model results

| Test metric | Product | Issue |
|---|---:|---:|
| Accuracy | 0.803 | 0.510 |
| Macro-F1 | 0.693 | 0.324 |
| Macro-F1 bootstrap 95% interval | 0.666–0.726 | 0.299–0.345 |
| Majority baseline macro-F1 | 0.200 | 0.036 |
| Multiclass Brier score | 0.294 | 0.652 |
| ECE, ten bins | 0.068 | 0.117 |

The issue model has material weaknesses: some classes have little or zero recall. `Closing an account` and `Closing your account` are distinct source labels from different products. They remain distinct here, which illustrates why taxonomy review matters. Full per-class results and confusion matrices are in `artifacts/validation.json`.

## Monitoring results

The frozen family has 24 product–issue pairs, evaluated over 26 weeks (624 series-weeks). Four flags pass the policy. Their underlying records have not been adjudicated as incidents.

The separate synthetic benchmark uses 12-series families and 200 replications: 950 flags over 96,000 null series-weeks, 80% injected-surge detection, and median zero-week delay among detected injections. The simulation family size and data-generating assumptions differ from the empirical cohort, so these rates are diagnostic rather than operational guarantees.

GitHub workflow outcomes are available on the repository's Actions page. The local results above do not pre-empt those independent runs.
