"""Chronological TF-IDF/logistic models, evaluation, and non-pickle inference."""
import re
from collections import Counter

import numpy as np
from scipy.special import softmax
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, log_loss
from sklearn.decomposition import NMF

from .config import TRAIN_END, VALID_END, SEED
from .text import clean_text, text_hash


def split_narratives(frame):
    df = frame.loc[frame['narrative'].map(clean_text).str.len() >= 40].copy()
    df['text'] = df['narrative'].map(clean_text)
    df['hash'] = df['text'].map(text_hash)
    before = len(df)
    df = df.sort_values(['date', 'id']).drop_duplicates('hash', keep='first')
    df['split'] = np.where(df['date'] < TRAIN_END, 'train', np.where(df['date'] < VALID_END, 'validation', 'test'))
    counts = df['split'].value_counts().to_dict()
    if any(counts.get(s, 0) < 30 for s in ['train', 'validation', 'test']):
        raise ValueError('At least 30 unique narrative records required in each temporal split')
    return df, {'duplicates_removed': before - len(df), 'split_counts': counts,
                'short_or_missing_excluded': len(frame) - before,
                'deduplication': 'Normalized exact text hashes; earliest record retained. Near duplicates remain possible.'}


def evaluate(y, pred, probabilities, classes):
    labels = list(classes)
    correct = np.asarray(y) == np.asarray(pred)
    confidence = probabilities.max(axis=1)
    ece = 0.0
    for lo in np.arange(0, 1, .1):
        mask = (confidence >= lo) & (confidence < lo + .1 + (1e-10 if lo > .85 else 0))
        if mask.any():
            ece += mask.mean() * abs(correct[mask].mean() - confidence[mask].mean())
    truth = np.array([[int(v == c) for c in classes] for v in y])
    rng = np.random.default_rng(SEED)
    scores = []
    y = np.asarray(y)
    pred = np.asarray(pred)
    for _ in range(200):
        index = rng.integers(0, len(y), len(y))
        scores.append(f1_score(y[index], pred[index], labels=labels, average='macro', zero_division=0))
    return {'rows': len(y), 'accuracy': float(accuracy_score(y, pred)),
            'macro_f1': float(f1_score(y, pred, labels=labels, average='macro', zero_division=0)),
            'macro_f1_bootstrap_95': np.quantile(scores, [.025, .975]).tolist(),
            'weighted_f1': float(f1_score(y, pred, average='weighted', zero_division=0)),
            'log_loss': float(log_loss(y, probabilities, labels=classes)),
            'multiclass_brier': float(((probabilities - truth) ** 2).sum(axis=1).mean()),
            'ece_10_bins': float(ece),
            'per_class': classification_report(y, pred, labels=labels, output_dict=True, zero_division=0),
            'confusion_matrix': confusion_matrix(y, pred, labels=labels).tolist()}


def train_models(df):
    train = df['split'].eq('train').to_numpy()
    val = df['split'].eq('validation').to_numpy()
    test = df['split'].eq('test').to_numpy()
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_df=.98, max_features=18000,
                               sublinear_tf=True, strip_accents=None)
    x_train = vectorizer.fit_transform(df.loc[train, 'text'])
    x_all = vectorizer.transform(df['text'])
    exports = {}
    metrics = {}
    predictions = {}
    for target in ['product', 'issue']:
        if target == 'issue':
            top = df.loc[train, target].value_counts().head(10).index.tolist()
            labels = df[target].where(df[target].isin(top), 'Other issue')
        else:
            top = sorted(df[target].unique())
            labels = df[target]
        candidates = []
        for c in [.5, 2.0]:
            estimator = LogisticRegression(C=c, max_iter=1000, solver='lbfgs', random_state=SEED)
            estimator.fit(x_train, labels[train])
            score = f1_score(labels[val], estimator.predict(x_all[val]), average='macro', zero_division=0)
            candidates.append((score, c, estimator))
        _, best_c, estimator = max(candidates, key=lambda item: item[0])
        probs = estimator.predict_proba(x_all)
        pred = estimator.classes_[probs.argmax(axis=1)]
        # Routing threshold chosen on validation only. Scores are not calibrated probabilities.
        accepted = []
        for threshold in np.arange(.35, .91, .05):
            mask = probs[val].max(axis=1) >= threshold
            if mask.sum() >= 30 and (pred[val][mask] == labels[val].to_numpy()[mask]).mean() >= .75:
                accepted.append(float(threshold))
        threshold = min(accepted) if accepted else .95
        stats = evaluate(labels[test], pred[test], probs[test], estimator.classes_)
        val_stats = {'macro_f1': float(f1_score(labels[val], pred[val], average='macro', zero_division=0))}
        baseline = labels[train].value_counts().index[0]
        stats['majority_baseline_macro_f1'] = float(f1_score(labels[test], [baseline]*test.sum(), labels=estimator.classes_, average='macro', zero_division=0))
        selected = probs[test].max(axis=1) >= threshold
        stats['routing_coverage'] = float(selected.mean())
        stats['routing_accuracy'] = float((pred[test][selected] == labels[test].to_numpy()[selected]).mean()) if selected.any() else None
        metrics[target] = {'classes': estimator.classes_.tolist(), 'C': best_c,
                           'validation_candidates': [{'C': c, 'macro_f1': float(s)} for s, c, _ in candidates],
                           'validation': val_stats, 'test': stats, 'review_threshold': threshold,
                           'class_mapping': top, 'confidence_note': 'Uncalibrated model scores, not guaranteed correctness probabilities.'}
        exports[target] = {'classes': estimator.classes_.tolist(), 'coef': estimator.coef_.round(10).tolist(),
                           'intercept': estimator.intercept_.round(10).tolist(), 'threshold': threshold}
        predictions[target] = {'prediction': pred.tolist(), 'confidence': probs.max(axis=1).tolist()}
    export = {'vocabulary': vectorizer.vocabulary_, 'idf': vectorizer.idf_.round(10).tolist(),
              'models': exports, 'format': 'tfidf-logistic-json-v1', 'preprocessing': 'clean_text + sklearn default word tokens; unigram/bigram, sublinear TF, L2 norm'}
    export['vocabulary'] = {k: int(v) for k, v in export['vocabulary'].items()}
    # Verify the portable inference path against sklearn on unseen test documents.
    parity = []
    for i in np.flatnonzero(test)[:40]:
        result = infer(export, df.iloc[i]['narrative'])
        for target in ['product', 'issue']:
            parity.append(abs(result[target]['confidence'] - predictions[target]['confidence'][i]))
    metrics['portable_max_probability_error'] = max(parity, default=0)
    if metrics['portable_max_probability_error'] > 1e-7:
        raise ValueError('Portable inference diverged from sklearn')
    return export, metrics, predictions


def infer(export, text):
    tokens = re.findall(r'(?u)\b\w\w+\b', clean_text(text))
    if len(tokens) < 5:
        raise ValueError('Enter at least five words of an English complaint')
    terms = tokens + [' '.join(tokens[i:i+2]) for i in range(len(tokens)-1)]
    counts = Counter(terms)
    vocab = export['vocabulary']
    weights = {vocab[t]: (1 + np.log(n)) * export['idf'][vocab[t]] for t, n in counts.items() if t in vocab}
    if not weights:
        raise ValueError('No recognized vocabulary; human review required')
    norm = np.sqrt(sum(v*v for v in weights.values()))
    weights = {k: v / norm for k, v in weights.items()}
    inverse = {v: k for k, v in vocab.items()}
    result = {}
    for target, model in export['models'].items():
        logits = np.array(model['intercept']) + np.array([sum(row[k]*v for k,v in weights.items()) for row in model['coef']])
        probability = softmax(logits)
        winner = int(probability.argmax())
        terms = sorted([(inverse[k], model['coef'][winner][k]*v) for k,v in weights.items()], key=lambda x:x[1], reverse=True)[:8]
        confidence = float(probability[winner])
        result[target] = {'label': model['classes'][winner], 'confidence': confidence,
                          'review': confidence < model['threshold'],
                          'top_terms': [{'term': t, 'contribution': round(float(v),4)} for t,v in terms if v>0],
                          'alternatives': sorted([{'label': c, 'score': float(p)} for c,p in zip(model['classes'], probability)], key=lambda x:-x['score'])[:3]}
    return result


def discover_topics(df):
    vector = TfidfVectorizer(stop_words='english', min_df=4, max_df=.7, max_features=7000, ngram_range=(1,2))
    train = df['split'].eq('train').to_numpy()
    x_train = vector.fit_transform(df.loc[train,'text'])
    nmf = NMF(n_components=8, init='nndsvda', max_iter=400, random_state=SEED)
    nmf.fit(x_train)
    weights = nmf.transform(vector.transform(df['text']))
    assignment = weights.argmax(axis=1)
    assignment[weights.sum(axis=1) < 1e-10] = -1
    features = vector.get_feature_names_out()
    topics = []
    recent = df['date'] >= '2024-12-02'
    previous = (df['date'] >= '2024-11-04') & (df['date'] < '2024-12-02')
    for i, component in enumerate(nmf.components_):
        terms = features[component.argsort()[-8:][::-1]].tolist()
        now = int(((assignment == i) & recent).sum())
        prior = int(((assignment == i) & previous).sum())
        share_now = now / max(int(recent.sum()), 1)
        share_prior = prior / max(int(previous.sum()), 1)
        example_indices = np.flatnonzero(assignment == i)
        example_indices = sorted(example_indices, key=lambda j: -weights[j,i])[:3]
        topics.append({'id': i, 'terms': terms, 'count': int((assignment == i).sum()),
                       'recent': now, 'previous': prior, 'share_change_pp': round(100*(share_now-share_prior),2),
                       'examples': df.iloc[example_indices]['id'].tolist()})
    return topics, assignment.tolist()
