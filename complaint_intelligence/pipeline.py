"""Build traceable analytical artifacts and the browser report."""
import csv
import json
import platform
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import sklearn

from .config import ROOT, START, END, TRAIN_END, VALID_END, PRODUCT_NAMES
from .data import load_cohort, sha256
from .model import split_narratives, train_models, discover_topics
from .alerts import monitor, simulation_benchmark
from .text import public_excerpt


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')), encoding='utf-8')


def safe_csv(frame, path):
    df = frame.copy()
    for col in df.select_dtypes(include=['object', 'string']):
        df[col] = df[col].map(lambda v: "'"+v if isinstance(v,str) and v.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else v)
    df.to_csv(path, index=False, quoting=csv.QUOTE_MINIMAL)


def build(path=None):
    path = Path(path or ROOT / 'data/processed/cohort.csv')
    df = load_cohort(path)
    print(f'Validated {len(df):,} source records', flush=True)
    nlp, split = split_narratives(df)
    print(f'Training on {len(nlp):,} unique narratives: {split["split_counts"]}', flush=True)
    model, metrics, predictions = train_models(nlp)
    print('Classifiers evaluated; discovering topics', flush=True)
    topics, assignments = discover_topics(nlp)
    nlp['topic'] = assignments
    for target in predictions:
        nlp['predicted_'+target] = predictions[target]['prediction']
        nlp[target+'_confidence'] = predictions[target]['confidence']
    print('Monitoring weekly product/issue counts', flush=True)
    series, alerts, policy = monitor(df)
    simulation = simulation_benchmark()
    df['week'] = (df['date'] - pd.to_timedelta(df['date'].dt.dayofweek, unit='D')).dt.strftime('%Y-%m-%d')
    weeks = pd.date_range(START, pd.Timestamp(END)-pd.Timedelta(days=7),freq='W-MON').strftime('%Y-%m-%d')
    weekly = []
    for week in weeks:
        rows = df[df['week'] == week]
        weekly.append({'week': week, 'total': len(rows), 'narratives': int(rows['narrative'].str.strip().ne('').sum()),
                       **{short: int(rows['product'].eq(product).sum()) for product,short in PRODUCT_NAMES.items()}})
    matrix = [{'product': p, 'issue': i, 'count': int(n)} for (p,i),n in df.groupby(['product','issue']).size().items()]
    lookup = nlp.set_index('id').to_dict('index')
    records = []
    for row in df.to_dict('records'):
        analysis = lookup.get(row['id'], {})
        records.append({'id': row['id'], 'date': row['date'].strftime('%Y-%m-%d'), 'week': row['week'],
                        'product': row['product'], 'issue': row['issue'], 'company': row['company'],
                        'narrative': row['narrative'], 'excerpt': public_excerpt(row['narrative']),
                        'topic': int(analysis.get('topic', -1)), 'split': analysis.get('split', 'not modeled'),
                        'prediction': analysis.get('predicted_issue', ''),
                        'confidence': round(float(analysis.get('issue_confidence', 0)),4)})
    # A bounded, deterministic public preview. Raw narratives remain local.
    example_ids = {x for topic in topics for x in topic['examples']}
    preview_candidates = [r for r in records if r['excerpt']]
    chosen = set(r['id'] for r in preview_candidates[-160:]) | example_ids
    preview = [{k:v for k,v in r.items() if k != 'narrative'} for r in records if r['id'] in chosen]
    source_manifest = ROOT/'artifacts/source_manifest.json'
    source = json.loads(source_manifest.read_text()) if source_manifest.exists() else {'source':'User-supplied CFPB-format CSV'}
    # A manifest from a different input must not be silently attributed to this build.
    if source.get('cohort_sha256') != sha256(path):
        source = {'source': 'User-supplied cohort CSV', 'cohort_sha256': sha256(path)}
    report = {'schema_version':1, 'title':'Banking Complaint Intelligence',
              'built_at': datetime.now(timezone.utc).isoformat(),
              'scope': {'state':'New York, USA', 'start':START, 'end_exclusive':END, 'weeks':52,
                        'products': PRODUCT_NAMES, 'training_end_exclusive':TRAIN_END, 'validation_end_exclusive':VALID_END},
              'summary': {'complaints':len(df), 'narratives': int(df['narrative'].str.strip().ne('').sum()),
                          'modeled_narratives':len(nlp), 'companies':int(df['company'].nunique()),
                          'alerts':len(alerts), 'topics':len(topics), 'preview_records':len(preview)},
              'source':source, 'splits':split, 'models':metrics, 'weekly':weekly, 'matrix':matrix,
              'alerts':alerts, 'series':series, 'alert_policy':policy, 'simulation':simulation,
              'topics':topics, 'records':preview,
              'runtime': {'python':platform.python_version(), 'pandas':pd.__version__, 'sklearn':sklearn.__version__},
              'cautions': [
                  'Historical New York cohort. Complaint counts are not incidence rates or bank quality rankings.',
                  'Received dates are not publication dates: this is a retrospective backtest, not a live detection claim.',
                  'Narratives are self-selected, unverified consumer allegations. Topic labels are statistical terms.',
                  'Alerts need human investigation. No verified real incident labels are available.',
                  'Confidence scores are uncalibrated; low-confidence classifications require review.',
              ]}
    output = ROOT/'artifacts'
    output.mkdir(exist_ok=True)
    write_json(output/'report.json', report)
    write_json(output/'model.json', model)
    write_json(output/'local/records.json', records)
    write_json(output/'validation.json', {'splits':split, 'models':metrics, 'simulation':simulation,
                                          'input_sha256':sha256(path), 'checks':{
                                              'unique_ids':not df['id'].duplicated().any(),
                                              'weekly_reconciles':sum(x['total'] for x in weekly)==len(df),
                                              'matrix_reconciles':sum(x['count'] for x in matrix)==len(df),
                                              'portable_inference_parity':metrics['portable_max_probability_error']<1e-7}})
    (ROOT/'web/data.js').write_text('window.REPORT = '+json.dumps(report, ensure_ascii=True, allow_nan=False)+';\n',encoding='utf-8')
    (ROOT/'web/model.js').write_text('window.MODEL = '+json.dumps(model, ensure_ascii=True, allow_nan=False)+';\n',encoding='utf-8')
    safe_csv(pd.DataFrame(weekly), output/'weekly_counts.csv')
    safe_csv(pd.DataFrame(alerts), output/'alerts.csv')
    safe_csv(pd.DataFrame(matrix), output/'product_issue_matrix.csv')
    safe_csv(nlp[['id','date','split','product','issue','predicted_product','predicted_issue','product_confidence','issue_confidence','topic']], output/'predictions.csv')
    database = ROOT/'artifacts/local/complaints.sqlite'
    with sqlite3.connect(database) as connection:
        df.drop(columns='narrative').assign(date=df['date'].dt.strftime('%Y-%m-%d')).to_sql('complaints',connection,if_exists='replace',index=False)
        pd.DataFrame(weekly).to_sql('weekly_counts',connection,if_exists='replace',index=False)
        connection.executescript('DROP VIEW IF EXISTS product_issue_counts; CREATE VIEW product_issue_counts AS SELECT product, issue, COUNT(*) AS complaints FROM complaints GROUP BY product, issue;')
    print(json.dumps(report['summary'],indent=2),flush=True)
    print('Issue test macro-F1:', round(metrics['issue']['test']['macro_f1'],4),flush=True)
    return report
