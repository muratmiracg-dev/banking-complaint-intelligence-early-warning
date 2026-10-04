# How the analysis works

## Cohort and source change

The study uses three CFPB categories: checking/savings accounts, credit cards and money transfers/virtual currency/money services. It is limited to New York records received from **2024-01-01 inclusive to 2024-12-30 exclusive**, exactly 52 complete Monday–Sunday weeks. The transfer group also contains non-bank providers; the sample is not a census of banks.

The original live CSV returned records on December 30 even though the API specification described the upper bound as exclusive. The importer therefore enforces the boundary locally. One missing issue is retained as `Unspecified issue`. Duplicate IDs, missing required fields and records outside the declared cohort fail validation.

In September 2026 the CFPB removed narratives from its live API. The fetch command joins current metadata with the CFPB's four official FOIA archive files covering 2024. It matches by complaint ID, checks for overlapping archive IDs and records SHA-256 hashes. There is no third-party data mirror or synthetic replacement for missing text.

The resulting snapshot is retrospective. A complaint's received date does not establish when the public narrative became available. Publication lags and subsequent changes prevent interpreting this run as an exact replay of a live 2024 system.

## Two populations

Volume monitoring uses **all 10,750 metadata records**. Text analysis uses records with a narrative of at least 40 normalized characters. URLs, email strings, digits and CFPB `XXXX` placeholders are removed. A stronger, punctuation-insensitive hash identifies exact normalized duplicates; the earliest date/ID is retained.

There are 5,415 published narratives. Seven are too short after normalization and 133 repeated normalized narratives are excluded, leaving 5,275 modeling records. Similar templates may survive this check. Narrative availability is self-selected and cannot be assumed representative of all complaints.

## Text classification

Two separate models predict the consumer-selected product and issue labels using narrative text only. Product, company, response and issue metadata are never input features.

| Partition | Dates | Unique narratives | Purpose |
|---|---|---:|---|
| Train | Jan 1–Jun 30 | 2,527 | Vocabulary, IDF, coefficients and issue taxonomy |
| Validation | Jul 1–Sep 29 | 1,374 | Regularization and score threshold |
| Test | Sep 30–Dec 29 | 1,374 | Final reported metrics |

- TF-IDF: unigram/bigram features, minimum document frequency 3, maximum frequency 98%, at most 18,000 features, sublinear TF and L2 normalization.
- Logistic regression: `C ∈ {0.5, 2.0}`, selected by validation macro-F1. Both tasks select C=2.0. No model refit on test data.
- Issue target: the ten most frequent training-period issues plus `Other issue`. New or rare labels are included in Other rather than silently discarded.
- Baseline: the most frequent training-period class, reported with the same label universe.
- Report: macro/weighted F1, accuracy, per-class precision/recall, confusion matrix, multiclass Brier score, log loss and ten-bin ECE.
- Uncertainty: 200 ordinary bootstrap resamples of test rows, fixed seed 42. The interval does not account for company clusters, near-duplicate templates or future domain shift.

Routing thresholds are the lowest tested score between 0.35 and 0.90 with validation accuracy at least 75% and at least 30 accepted examples. If no threshold qualifies, the fallback is 0.95. Scores are **not calibrated correctness probabilities**. For the issue model, the selected score is 0.60: only about 9.9% of Q4 rows pass it. Their 88.2% accuracy does not describe the other 90.1% of rows. All outputs remain suggestions for human review.

The portable browser model stores vocabulary, IDF and logistic coefficients as JSON. It implements the same TF-IDF normalization and softmax. Python/sklearn and JavaScript consistency are checked; inference does not require a remote model API. Individual term contributions explain the selected class logit, not causality.

## Topic discovery

An eight-component NMF model is fitted only to training-period TF-IDF with English stop words, min_df=4, max_df=0.7 and at most 7,000 unigram/bigram features. Later text is transformed against these fixed components. Each narrative is assigned to its strongest topic; an all-zero representation gets no topic.

Eight topics are an exploratory design choice, not an empirically established optimum. Leading terms form the displayed descriptions. Examples are the highest topic-weight records, not random samples. December share changes compare 2–29 December with 4 November–1 December, each four full weeks. This tracks growth in known themes; it does not detect arbitrary new topics. Topic naming and novelty assessment require review.

## Early warnings

The monitored family contains product/issue pairs with at least 20 records during January–June. This family is frozen before evaluation. **Flags start July 1**, after family selection; earlier values appear only as development context on the charts.

Each monitored pair has a complete weekly series, including explicit zero-count weeks. At week t:

1. Estimate mean and sample variance from t−12 through t−1. The current week cannot alter its baseline.
2. Set predictive variance to `max(sample_variance, mean) × (1 + 1/12)` and floor the mean at 0.5 for sparse series.
3. Moment-match a negative-binomial count distribution; use a Poisson fallback when variance equals the mean. Compute the upper-tail score `P(X ≥ observed)`.
4. Apply Benjamini–Hochberg adjustment across the fixed family in the same week.
5. Flag only if adjusted score ≤ 0.05, count ≥ 5, observed/expected ≥ 1.5 and standardized deviation ≥ 3.

These plug-in predictive tails are approximate. Rolling, overlapping windows, estimated parameters, autocorrelation and dependencies among issues mean a nominal BH threshold is not a demonstrated operational false-discovery guarantee. New pairs outside the training family are not monitored until a deliberate revision of the family.

A one-sided CUSUM accumulates standardized residuals (positive residual capped at 5, drift 0.5, reset at 8). Shift watches are exploratory and separate from the alert register. They indicate accumulated deviations, not exact causal change points. No seasonal or holiday adjustment is currently fitted.

### What the false-alarm experiment measures

There are no verified incident labels in this cohort. A separate seeded simulation creates 200 independent families of 12 stationary negative-binomial series over 52 weeks. Each family has different mean counts (3–25), dispersion shape 12 and a 12-week warm-up. The same gates measure flagged **series-weeks**, not percentage of false real incidents.

A separate copy adds Poisson counts with mean three times baseline to one series for four weeks (expected total about 4×). Detection means at least one flag during that injection window. The recorded null flag rate is 0.99%, injection detection is 80%, and median first-detection delay among detected simulations is zero weeks. These results depend on this particular simulation and are not real-world sensitivity estimates.

## Boundaries

Complaint counts have no customer/transaction exposure denominator. Do not rank banks or call a rising count a rising failure rate. A narrative is an unverified allegation. Neither model nor alert establishes fraud, misconduct or legal liability. Turkish-language transfer, publication-time monitoring, calibrated scores and production deployment are future research, not implemented claims.

## Sources

- [CFPB complaint database](https://www.consumerfinance.gov/data-research/consumer-complaints/)
- [CFPB API release notes, Release 24](https://cfpb.github.io/api/ccdb/release-notes.html)
- [Official narrative archive](https://www.consumerfinance.gov/foia-requests/foia-electronic-reading-room/cfpb-consumer-complaint-database-narratives-archive/)
- [CFPB API specification](https://github.com/cfpb/ccdb5-api/blob/main/swagger-config.yaml)
# Monitoring input contract

Weekly observations must be a one-dimensional sequence of finite, non-negative
integer counts and the rolling baseline must contain at least two weeks.
Benjamini-Hochberg correction accepts only finite p-values in the closed
interval from zero to one, preventing invalid statistical inputs from silently
entering the early-warning ranking.
