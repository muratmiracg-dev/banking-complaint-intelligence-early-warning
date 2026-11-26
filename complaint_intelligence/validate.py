"""Checks that published artifacts agree without downloading source narratives.

The checks raise ArtifactValidationError explicitly instead of using ``assert``, so they
still run under ``python -O`` / ``PYTHONOPTIMIZE``, which strip assert statements.
"""
import json
from collections import defaultdict
from pathlib import Path

from .alerts import bh_adjust, score_series
from .config import ROOT

STAT_FIELDS = ('expected', 'upper', 'p', 'score', 'lift', 'cusum')


class ArtifactValidationError(Exception):
    """A committed artifact is inconsistent with the others."""


def _require(condition, message):
    if not condition:
        raise ArtifactValidationError(message)


def validate_artifacts(root: Path = ROOT):
    root = Path(root)
    report = json.loads((root/'artifacts/report.json').read_text())
    evidence = json.loads((root/'artifacts/validation.json').read_text())
    model = json.loads((root/'artifacts/model.json').read_text())
    summary = report['summary']
    _require(len(report['weekly']) == 52, 'Expected exactly 52 complete weeks')
    _require(sum(w['total'] for w in report['weekly']) == summary['complaints'], 'Weekly count mismatch')
    _require(sum(w['narratives'] for w in report['weekly']) == summary['narratives'], 'Narrative count mismatch')
    _require(sum(m['count'] for m in report['matrix']) == summary['complaints'], 'Matrix mismatch')
    _require(len(report['alerts']) == summary['alerts'], 'Alert count mismatch')
    _require(len(report['records']) == summary['preview_records'], 'Preview count mismatch')
    _require(all(evidence['checks'].values()), 'Analytical quality gate failed')
    _require(all('narrative' not in row for row in report['records']),
             'Raw narrative leaked into public report')
    for target in ['product', 'issue']:
        m = report['models'][target]
        _require(sum(sum(row) for row in m['test']['confusion_matrix']) == m['test']['rows'],
                 f'{target} confusion matrix does not match test rows')
        _require(len(model['models'][target]['coef'][0]) == len(model['idf']) == len(model['vocabulary']),
                 f'{target} model coefficients do not match the vocabulary')
        _require(len(model['models'][target]['classes']) == len(m['classes']),
                 f'{target} model classes do not match the report')
    for alert in report['alerts']:
        _require(alert['observed'] >= 5 and alert['lift'] >= 1.5 and alert['score'] >= 3 and alert['q'] <= .05,
                 f"Alert {alert.get('id', '?')} does not meet the published alert thresholds")
    _validate_monitoring(report)
    for name, key in [('data.js', 'REPORT'), ('model.js', 'MODEL')]:
        js = (root/'web'/name).read_text()
        value = json.loads(js[len('window.'+key+' = '):].strip().removesuffix(';'))
        _require(value == (report if key == 'REPORT' else model), f'{name} stale')
    print('Artifact validation passed: counts, matrices, gates, recomputed monitoring, model shape, '
          'public data and browser copies')
    return True


def _same(published, recomputed):
    if published is None or recomputed is None:
        return published is None and recomputed is None
    return abs(float(published) - float(recomputed)) <= 1e-6


def _validate_monitoring(report):
    """Recompute every published series statistic and alert from the published counts.

    The threshold check above only proves that listed alerts clear the thresholds. It
    could not see a stale or hand-edited monitoring table: a count that no longer matches
    its p-value, a q-value from a different family, or a qualifying week missing from the
    alert list. The weekly counts are public, so the whole monitoring result is
    reproducible here without the local source narratives.
    """
    policy = report['alert_policy']
    start = policy['monitoring_start']
    by_pair = defaultdict(list)
    for row in report['series']:
        by_pair[(row['product'], row['issue'])].append(row)
    weeks = [w['week'] for w in report['weekly']]
    _require(len(by_pair) == policy['series'], 'Monitored series count does not match the policy')
    _require(policy['evaluated_series_weeks'] == len(by_pair) * sum(w >= start for w in weeks),
             'Evaluated series-weeks do not match the monitored series and weeks')
    matrix = {(m['product'], m['issue']): m['count'] for m in report['matrix']}
    recomputed_p = defaultdict(list)
    for pair, rows in by_pair.items():
        _require([r['week'] for r in rows] == weeks,
                 f'Series {pair} does not cover the 52 report weeks in order')
        observed = [r['observed'] for r in rows]
        _require(sum(observed) == matrix.get(pair), f'Series {pair} counts do not reconcile with the matrix')
        for row, stats in zip(rows, score_series(observed)):
            _require(all(_same(row[f], stats[f]) for f in STAT_FIELDS),
                     f"Series {pair} week {row['week']} statistics do not match its published counts")
            recomputed_p[row['week']].append((row, stats['p']))
    expected_alerts = []
    for week, members in recomputed_p.items():
        q_values = bh_adjust([p for _, p in members])
        for (row, _), q in zip(members, q_values):
            _require(_same(row['q'], round(float(q), 6)),
                     f"Series {row['product']} / {row['issue']} week {week} q-value is not reproducible")
            monitored = week >= start
            alert = (monitored and q <= policy['bh_alpha'] and row['observed'] >= policy['minimum_count']
                     and row['lift'] >= policy['minimum_lift']
                     and row['score'] >= policy['minimum_standardized_score'])
            _require(bool(row['alert']) == alert,
                     f"Series {row['product']} / {row['issue']} week {week} alert flag is not reproducible")
            _require(bool(row['shift_watch']) == (monitored and row['cusum'] >= 8),
                     f"Series {row['product']} / {row['issue']} week {week} shift flag is not reproducible")
            if alert:
                expected_alerts.append((-row['score'], week, row['product'], row['issue']))
    published = [(-a['score'], a['week'], a['product'], a['issue']) for a in report['alerts']]
    _require(published == sorted(expected_alerts, key=lambda item: (item[0], item[1])),
             'Published alerts do not match the alerts recomputed from the series')
    for index, alert in enumerate(report['alerts'], start=1):
        _require(alert.get('id') == f'EW-{index:03d}'
                 and alert.get('severity') == ('High' if alert['score'] >= 5 else 'Review'),
                 f"Alert {alert.get('id', '?')} identifier or severity is not reproducible")
