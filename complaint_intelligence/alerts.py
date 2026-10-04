"""Past-only count monitoring with weekly multiplicity correction.

Negative-binomial predictive tails are approximate under a rolling estimated baseline.
Flags are investigative signals, not verified incidents or causal findings.
"""
import numpy as np
import pandas as pd
from scipy.stats import nbinom, poisson
from .config import START, END, TRAIN_END, SEED

WINDOW = 12
ALPHA = 0.05


def bh_adjust(values):
    p = np.asarray(values, dtype=float)
    if not len(p):
        return p
    if p.ndim != 1 or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("P-values must be a finite one-dimensional vector in [0, 1]")
    order = np.argsort(p)
    adjusted = p[order] * len(p) / np.arange(1, len(p) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    result = np.empty(len(p))
    result[order] = np.minimum(adjusted, 1)
    return result


def score_series(values, window=WINDOW):
    values = np.asarray(values, dtype=float)
    if isinstance(window, bool) or not isinstance(window, int) or window < 2:
        raise ValueError("Window must be an integer of at least two weeks")
    if (
        values.ndim != 1
        or np.any(values < 0)
        or not np.isfinite(values).all()
        or not np.equal(values, np.floor(values)).all()
    ):
        raise ValueError("Counts must be a one-dimensional vector of finite nonnegative integers")
    output = []
    cusum = 0.0
    for i, observed in enumerate(values):
        if i < window:
            output.append({'expected': None, 'upper': None, 'p': 1.0, 'score': 0.0, 'lift': 0.0, 'cusum': 0.0})
            continue
        history = values[i-window:i]
        mean = max(float(history.mean()), 0.5)
        variance = max(float(history.var(ddof=1)), mean) * (1 + 1 / window)
        if variance > mean + 1e-8:
            shape = mean ** 2 / (variance - mean)
            prob = shape / (shape + mean)
            tail = nbinom.sf(observed - 1, shape, prob)
            upper = nbinom.ppf(0.99, shape, prob)
        else:
            tail = poisson.sf(observed - 1, mean)
            upper = poisson.ppf(0.99, mean)
        z = (observed - mean) / np.sqrt(variance)
        cusum = max(0.0, cusum + min(z, 5.0) - 0.5)
        output.append({'expected': round(mean, 3), 'upper': float(upper), 'p': float(tail),
                       'score': round(float(z), 3), 'lift': round(float(observed / mean), 3),
                       'cusum': round(cusum, 3)})
        if cusum >= 8:
            cusum = 0.0
    return output


def monitor(frame):
    df = frame.copy()
    df['week'] = df['date'] - pd.to_timedelta(df['date'].dt.dayofweek, unit='D')
    weeks = pd.date_range(START, pd.Timestamp(END) - pd.Timedelta(days=7), freq='W-MON')
    # Family of monitored series is fixed using training-period data only.
    eligible = df.loc[df['date'] < TRAIN_END].groupby(['product', 'issue']).size()
    pairs = list(eligible[eligible >= 20].index)
    rows = []
    for product, issue in pairs:
        sub = df.loc[(df['product'] == product) & (df['issue'] == issue)]
        counts = sub.groupby('week').size().reindex(weeks, fill_value=0)
        for week, count, stats in zip(weeks, counts, score_series(counts)):
            rows.append({'week': week.strftime('%Y-%m-%d'), 'product': product, 'issue': issue,
                         'observed': int(count), **stats})
    result = pd.DataFrame(rows)
    if result.empty:
        return [], [], {'series': 0, 'evaluated_series_weeks': 0}
    result['q'] = result.groupby('week')['p'].transform(lambda s: bh_adjust(s.to_numpy()))
    result['monitoring_period'] = result['week'] >= TRAIN_END
    result['alert'] = result['monitoring_period'] & (result['q'] <= ALPHA) & (result['observed'] >= 5) & (result['lift'] >= 1.5) & (result['score'] >= 3)
    result['shift_watch'] = result['monitoring_period'] & (result['cusum'] >= 8)
    result['expected'] = result['expected'].astype(object).where(result['expected'].notna(), None)
    result['upper'] = result['upper'].astype(object).where(result['upper'].notna(), None)
    result['q'] = result['q'].round(6)
    records = result.to_dict('records')
    alerts = sorted([r for r in records if r['alert']], key=lambda x: (-x['score'], x['week']))
    for i, alert in enumerate(alerts):
        alert['id'] = f'EW-{i+1:03d}'
        alert['severity'] = 'High' if alert['score'] >= 5 else 'Review'
    return records, alerts, {'series': len(pairs), 'evaluated_series_weeks': len(pairs) * int((weeks >= TRAIN_END).sum()),
                             'monitoring_start': TRAIN_END, 'window_weeks': WINDOW, 'bh_alpha': ALPHA, 'minimum_count': 5,
                             'minimum_lift': 1.5, 'minimum_standardized_score': 3}


def simulation_benchmark(repetitions=200, family_size=12):
    rng = np.random.default_rng(SEED)
    false_flags = eligible = detected = 0
    delays = []
    for run in range(repetitions):
        means = np.linspace(3, 25, family_size)
        null = np.array([rng.negative_binomial(12, 12 / (12 + m), 52) for m in means])
        shifted = null.copy()
        shifted[0, 36:40] += rng.poisson(means[0] * 3, 4)  # Expected total ~4x baseline.
        for mode, matrix in [('null', null), ('injected', shifted)]:
            stats = [score_series(x) for x in matrix]
            hit = []
            for w in range(WINDOW, 52):
                q = bh_adjust([s[w]['p'] for s in stats])
                flags = [q[j] <= ALPHA and matrix[j, w] >= 5 and stats[j][w]['lift'] >= 1.5 and stats[j][w]['score'] >= 3 for j in range(family_size)]
                if mode == 'null':
                    false_flags += sum(flags)
                    eligible += family_size
                elif 36 <= w < 40 and flags[0]:
                    hit.append(w - 36)
            if mode == 'injected' and hit:
                detected += 1
                delays.append(min(hit))
    return {'kind': 'Synthetic negative-binomial null + injected four-week surge; not real incident labels',
            'seed': SEED, 'repetitions': repetitions, 'family_size': family_size,
            'null_false_flags': int(false_flags), 'null_series_weeks': eligible,
            'null_flag_rate': false_flags / eligible,
            'injected_detection_rate': detected / repetitions,
            'median_delay_weeks_when_detected': float(np.median(delays)) if delays else None,
            'injection': 'Series 0, weeks 36–39; added Poisson(3 × baseline mean), expected total 4×.'}
