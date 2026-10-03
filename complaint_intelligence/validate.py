"""Checks that published artifacts agree without downloading source narratives."""
import json
from .config import ROOT


def validate_artifacts():
    report = json.loads((ROOT/'artifacts/report.json').read_text())
    evidence = json.loads((ROOT/'artifacts/validation.json').read_text())
    model = json.loads((ROOT/'artifacts/model.json').read_text())
    summary = report['summary']
    assert len(report['weekly']) == 52, 'Expected exactly 52 complete weeks'
    assert sum(w['total'] for w in report['weekly']) == summary['complaints'], 'Weekly count mismatch'
    assert sum(w['narratives'] for w in report['weekly']) == summary['narratives'], 'Narrative count mismatch'
    assert sum(m['count'] for m in report['matrix']) == summary['complaints'], 'Matrix mismatch'
    assert len(report['alerts']) == summary['alerts'], 'Alert count mismatch'
    assert len(report['records']) == summary['preview_records'], 'Preview count mismatch'
    assert all(evidence['checks'].values()), 'Analytical quality gate failed'
    assert all('narrative' not in row for row in report['records']), 'Raw narrative leaked into public report'
    for target in ['product','issue']:
        m = report['models'][target]
        assert sum(sum(row) for row in m['test']['confusion_matrix']) == m['test']['rows']
        assert len(model['models'][target]['coef'][0]) == len(model['idf']) == len(model['vocabulary'])
        assert len(model['models'][target]['classes']) == len(m['classes'])
    for alert in report['alerts']:
        assert alert['observed'] >= 5 and alert['lift'] >= 1.5 and alert['score'] >= 3 and alert['q'] <= .05
    for name,key in [('data.js','REPORT'),('model.js','MODEL')]:
        js = (ROOT/'web'/name).read_text()
        value = json.loads(js[len('window.'+key+' = '):].strip().removesuffix(';'))
        assert value == (report if key == 'REPORT' else model), f'{name} stale'
    print('Artifact validation passed: counts, matrices, gates, model shape, public data and browser copies')
    return True
