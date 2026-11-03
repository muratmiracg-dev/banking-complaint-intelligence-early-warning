"""Checks that published artifacts agree without downloading source narratives.

The checks raise ArtifactValidationError explicitly instead of using ``assert``, so they
still run under ``python -O`` / ``PYTHONOPTIMIZE``, which strip assert statements.
"""
import json
from pathlib import Path

from .config import ROOT


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
    for name, key in [('data.js', 'REPORT'), ('model.js', 'MODEL')]:
        js = (root/'web'/name).read_text()
        value = json.loads(js[len('window.'+key+' = '):].strip().removesuffix(';'))
        _require(value == (report if key == 'REPORT' else model), f'{name} stale')
    print('Artifact validation passed: counts, matrices, gates, model shape, public data and browser copies')
    return True
