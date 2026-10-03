"""Official-source acquisition, schema checks, and bounded-memory archive joins."""
import hashlib
import json
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from .config import API, ARCHIVE_PAGE, END, PRODUCTS, ROOT, START, STATE

ARCHIVES = [
    'CCDB_Export_5_September_2023_through_March_2024.zip',
    'CCDB_Export_6_April_2024_through_July_2024.zip',
    'CCDB_Export_7_August_2024_through_October_2024.zip',
    'CCDB_Export_8_November_2024_through_December_2024.zip',
]
COLUMN_MAP = {'Complaint ID': 'id', 'Date received': 'date', 'Product': 'product',
              'Issue': 'issue', 'Company': 'company', 'State': 'state',
              'Consumer complaint narrative': 'narrative', 'Timely response?': 'timely'}
REQUIRED = ['id', 'date', 'product', 'issue', 'state']


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def download(url, target):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return
    temp = target.with_suffix(target.suffix + '.part')
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'ComplaintIntelligence/1.0'}), timeout=120) as response, temp.open('wb') as f:
                while block := response.read(1024 * 1024):
                    f.write(block)
            temp.replace(target)
            return
        except (OSError, ValueError):
            temp.unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def validate_frame(frame, require_narrative=False):
    missing = set(REQUIRED) - set(frame.columns)
    if missing:
        raise ValueError(f'Missing required columns: {sorted(missing)}')
    df = frame.copy()
    if df[REQUIRED].isna().any().any() or any(df[c].astype(str).str.strip().eq('').any() for c in REQUIRED):
        raise ValueError('Blank required values are not allowed')
    df['id'] = df['id'].astype(str)
    if not df['id'].str.fullmatch(r'\d+').all():
        raise ValueError('Complaint IDs must be numeric strings')
    if df['id'].duplicated().any():
        raise ValueError('Duplicate complaint IDs: reconcile source files before building')
    df['date'] = pd.to_datetime(df['date'], utc=True, errors='raise').dt.tz_convert(None).dt.normalize()
    if df.empty:
        raise ValueError('No records in the input')
    if not df['date'].between(pd.Timestamp(START), pd.Timestamp(END) - pd.Timedelta(days=1)).all():
        raise ValueError('Dates outside the declared 52-week cohort')
    if not df['product'].isin(PRODUCTS).all() or not df['state'].eq(STATE).all():
        raise ValueError('Records outside the declared product/state cohort')
    for col in ['company', 'timely', 'narrative']:
        if col not in df:
            df[col] = ''
        df[col] = df[col].fillna('').astype(str)
    if require_narrative and not df['narrative'].str.strip().ne('').any():
        raise ValueError('No narratives: current CFPB API does not supply them; use the official archive')
    return df.sort_values(['date', 'id']).reset_index(drop=True)


def acquire():
    raw = ROOT / 'data/raw'
    params = [('format', 'csv'), ('date_received_min', START), ('date_received_max', END), ('state', STATE)]
    params += [('product', product) for product in PRODUCTS]
    url = API + '?' + urlencode(params)
    download(url, raw / 'live_metadata.csv')
    for name in ARCHIVES:
        print(f'Archive: {name}', flush=True)
        download('https://files.consumerfinance.gov/f/documents/' + name, raw / name)
    metadata = pd.read_csv(raw / 'live_metadata.csv', dtype=str).rename(columns=COLUMN_MAP)
    # Enforce the local half-open interval even if upstream changes endpoint inclusivity.
    dates = pd.to_datetime(metadata['date'], utc=True)
    metadata = metadata.loc[(dates >= START) & (dates < END)].copy()
    missing_issue_count = int(metadata['issue'].isna().sum())
    metadata['issue'] = metadata['issue'].fillna('Unspecified issue')
    metadata = validate_frame(metadata)
    ids = set(metadata['id'])
    parts = []
    sources = [{'url': url, 'sha256': sha256(raw / 'live_metadata.csv')}]
    for name in ARCHIVES:
        path = raw / name
        sources.append({'url': 'https://files.consumerfinance.gov/f/documents/' + name, 'sha256': sha256(path)})
        with zipfile.ZipFile(path) as archive:
            csvs = [n for n in archive.namelist() if n.lower().endswith('.csv')]
            if not csvs:
                raise ValueError(f'Archive has no CSV: {name}')
            for member in csvs:
                with archive.open(member) as f:
                    for chunk in pd.read_csv(f, dtype=str, chunksize=40000):
                        chunk = chunk.rename(columns=COLUMN_MAP)
                        if 'narrative' not in chunk or 'id' not in chunk:
                            raise ValueError(f'Archive schema changed: {name}')
                        keep = chunk.loc[chunk['id'].isin(ids), ['id', 'narrative']]
                        parts.append(keep)
    narratives = pd.concat(parts, ignore_index=True)
    if narratives['id'].duplicated().any():
        raise ValueError('Overlapping archive complaint IDs')
    metadata = metadata.drop(columns='narrative').merge(narratives, on='id', how='left', validate='one_to_one')
    metadata = validate_frame(metadata, require_narrative=True)
    processed = ROOT / 'data/processed/cohort.csv'
    processed.parent.mkdir(parents=True, exist_ok=True)
    metadata.to_csv(processed, index=False)
    manifest = {
        'retrieved_at': datetime.now(timezone.utc).isoformat(), 'source': 'CFPB official API + official FOIA narrative archive',
        'archive_page': ARCHIVE_PAGE, 'sources': sources, 'cohort_sha256': sha256(processed),
        'start_inclusive': START, 'end_exclusive': END, 'state': STATE, 'products': PRODUCTS,
        'rows': len(metadata), 'archive_id_matches': len(narratives),
        'missing_issue_imputed': missing_issue_count,
        'narratives': int(metadata['narrative'].str.strip().ne('').sum()),
        'api_change': 'September 2026: public narratives removed from live API; archived narratives joined by complaint ID.',
        'as_of_caution': 'Retrospective snapshot by received date, not a historical publication-time replay.',
    }
    (ROOT / 'artifacts').mkdir(exist_ok=True)
    (ROOT / 'artifacts/source_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({k: manifest[k] for k in ['rows', 'archive_id_matches', 'narratives']}), flush=True)
    return processed


def load_cohort(path):
    frame = pd.read_csv(path, dtype=str).rename(columns=COLUMN_MAP)
    return validate_frame(frame, require_narrative=True)
