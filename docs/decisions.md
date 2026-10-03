# Development notes

2026-10-01

**The live export had no narrative column.** The initial assumption that the current API supplied text was wrong. The official September release notes explain the removal. The importer now joins current metadata with the official narrative archive by ID, and the report explicitly describes the differing snapshot sources.

**The date upper bound was inclusive in practice.** The first download contained 10,798 rows, including 48 on December 30. The intended period ends before that date. Filtering locally produces 10,750 rows and avoids an extra partial week. One missing issue is preserved in an explicit bucket.

**A readable baseline is useful here.** TF-IDF/logistic regression is fast enough to reproduce on a normal laptop and exposes token contributions. The small training sample does not justify calling a transformer necessary. The issue classifier's Q4 macro-F1 is only 0.324, despite product classification reaching 0.693. That difference stays visible.

**A time split alone is insufficient.** Normalized duplicate narratives can cross date boundaries. Deduplication retains the earliest observation before splitting. A test guards this behavior. Near duplicates are a remaining risk.

**The monitoring family must exist before monitoring starts.** Selecting pairs using Jan–Jun records and showing April alerts would use future information in family selection. The implementation was corrected before publication: the register starts in July. A regression test guards the boundary.

**Sparse matrices needed explicit NumPy masks.** The first training run hit a pandas-Series/scipy indexing mismatch. Converting temporal masks to NumPy arrays fixed the path; the full training and inference run was then executed successfully.

**The source is historical, not a live incident feed.** Neither receipt-date backtesting nor synthetic injections establish operational detection performance. Live deployment would require first-seen timestamps, incident review labels and exposure denominators.

**The browser stays small.** One HTML/CSS/JavaScript application, a local Python API and SQLite/CSV outputs cover the use case. There is no dashboard file claiming to be Power BI, no placeholder presentation deck and no cloud infrastructure needed to open the report.
