# Data and artifact contract

## Input

The importer accepts the CFPB column names or the internal names below. A custom CSV must be in the same configured cohort; changing the study scope requires updating configuration and revalidating the date splits and monitoring window.

| Internal field | CFPB heading | Requirement |
|---|---|---|
| id | Complaint ID | Unique numeric string, no blank values |
| date | Date received | Parseable date, 2024-01-01 inclusive to 2024-12-30 exclusive |
| product | Product | One of the three categories in `config.py` |
| issue | Issue | Nonblank; official importer maps its one missing label to Unspecified issue |
| state | State | NY |
| narrative | Consumer complaint narrative | May be blank per record; at least one nonblank value required to build |
| company | Company | Optional, blank if unavailable |
| timely | Timely response? | Optional, retained as metadata only |

Training requires at least 30 distinct, sufficiently long narratives in each chronological partition. The shipped cohort has far more than this minimum; the minimum is a validity check, not a recommended sample size.

## Outputs

- `source_manifest.json`: official source URLs, hashes, cohort scope and archive match count.
- `report.json`: aggregate results, evaluations, alert series, topics and a bounded preview. No full narrative field is included.
- `model.json`: TF-IDF vocabulary/IDF and logistic coefficients. No pickle execution is needed.
- `predictions.csv`: complaint ID, partition, reported/predicted labels, scores and topic assignment; no narrative text.
- `weekly_counts.csv`: all-record counts and available-narrative counts for every complete week.
- `product_issue_matrix.csv`: all metadata records grouped by product and reported issue.
- `alerts.csv`: flags passing the policy from July onward. Empty results are valid.
- `artifacts/local/records.json`: full records used by local search; ignored by Git.
- `artifacts/local/complaints.sqlite`: metadata and analytical views; ignored by Git.

The browser's `data.js` and `model.js` contain the same objects as the JSON artifacts. Validation checks that these copies agree. Public snippets are at most 260 characters plus an ellipsis, with additional pattern redaction. The redaction is not a guarantee of complete anonymization.
