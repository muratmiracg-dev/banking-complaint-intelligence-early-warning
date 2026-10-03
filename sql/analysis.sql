-- Built by: python -m complaint_intelligence build
-- Database: artifacts/local/complaints.sqlite

-- Reconcile the report's headline complaint count.
SELECT COUNT(*) AS complaints, COUNT(DISTINCT id) AS unique_complaints
FROM complaints;

-- Product/issue mix uses all metadata records, not just available narratives.
SELECT product, issue, COUNT(*) AS complaints,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY product), 2) AS within_product_pct
FROM complaints
GROUP BY product, issue
ORDER BY product, complaints DESC;

-- Review the week preceding an alert; named parameters can be bound in sqlite3.
SELECT id, date, company, product, issue
FROM complaints
WHERE week = :week AND product = :product AND issue = :issue
ORDER BY date, id;

-- Track missing-narrative coverage by week, without treating it as a quality rate.
SELECT week, total, narratives,
       ROUND(100.0 * narratives / NULLIF(total, 0), 2) AS narrative_coverage_pct
FROM weekly_counts
ORDER BY week;
