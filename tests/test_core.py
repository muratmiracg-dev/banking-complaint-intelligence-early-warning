import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from complaint_intelligence.alerts import bh_adjust, score_series, monitor, simulation_benchmark
from complaint_intelligence.data import validate_frame
from complaint_intelligence.model import infer, split_narratives
from complaint_intelligence.pipeline import safe_csv
from complaint_intelligence.text import clean_text, text_hash, public_excerpt
from complaint_intelligence.config import ROOT, PRODUCTS
from complaint_intelligence.validate import validate_artifacts


def row(**kwargs):
    return dict(id='123',date='2024-01-02',product=PRODUCTS[0],issue='Managing an account',state='NY',**kwargs)


class SourceContractTests(unittest.TestCase):
    def test_simulation_benchmark_rejects_invalid_dimensions(self):
        for kwargs in ({"repetitions": 0}, {"repetitions": True},
                       {"family_size": 0}, {"family_size": 1.5}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                simulation_benchmark(**kwargs)

    def test_duplicate_ids_fail(self):
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            validate_frame(pd.DataFrame([row(),row()]))

    def test_required_column_missing(self):
        with self.assertRaisesRegex(ValueError,'Missing required'):
            validate_frame(pd.DataFrame([row()]).drop(columns='issue'))

    def test_exclusive_end_is_rejected(self):
        data=row();data['date']='2024-12-30'
        with self.assertRaisesRegex(ValueError,'Dates outside'):
            validate_frame(pd.DataFrame([data]))

    def test_wrong_geography_fails(self):
        data=row();data['state']='CA'
        with self.assertRaisesRegex(ValueError,'cohort'):
            validate_frame(pd.DataFrame([data]))

    def test_narratives_are_not_fabricated(self):
        with self.assertRaisesRegex(ValueError,'No narratives'):
            validate_frame(pd.DataFrame([row()]),require_narrative=True)

    def test_normalization_removes_urls_numbers_and_redactions(self):
        text=clean_text('Account XXXX email a@test.com https://example.com balance 5000')
        self.assertEqual(text,'account email balance')

    def test_duplicate_hash_ignores_amounts_and_punctuation(self):
        self.assertEqual(text_hash('My money! Amount 400.'),text_hash('My money amount 500'))

    def test_excerpt_redacts_obvious_identifiers(self):
        excerpt=public_excerpt('Write person@test.com about 12345678901, https://test.com')
        self.assertNotIn('person@test.com',excerpt)
        self.assertNotIn('12345678901',excerpt)
        self.assertNotIn('https://test.com',excerpt)

    def test_formula_injection_is_escaped(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'export.csv'
            safe_csv(pd.DataFrame({'text':['=SUM(A1)', '  @function', 'safe']}),p)
            values=pd.read_csv(p)['text'].tolist()
            self.assertEqual(values,["'=SUM(A1)","'  @function",'safe'])


class MonitoringTests(unittest.TestCase):
    def test_bh_known_values(self):
        np.testing.assert_allclose(bh_adjust([.01,.04,.03,.2]),[.04,.0533333333,.0533333333,.2])

    def test_bh_rejects_invalid_probability_vectors(self):
        for values in ([0.1, float("nan")], [-0.1, 0.5], [0.5, 1.1], [[0.1], [0.2]]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                bh_adjust(values)

    def test_future_counts_cannot_change_past_scores(self):
        x=np.array([5,6,4,8,4,7,6,3,6,5,7,4]*4)
        other=x.copy();other[30:]=999
        self.assertEqual(score_series(x)[:30],score_series(other)[:30])

    def test_current_count_cannot_change_its_baseline(self):
        a=score_series([5]*12+[10])[-1]
        b=score_series([5]*12+[100])[-1]
        self.assertEqual(a['expected'],b['expected'])
        self.assertLess(b['p'],a['p'])

    def test_no_alert_before_family_is_frozen(self):
        rows=[]
        for i in range(100):
            r=row();r['id']=str(i);r['date']='2024-04-15';rows.append(r)
        records,alerts,_=monitor(validate_frame(pd.DataFrame(rows)))
        self.assertTrue(all(a['week']>='2024-07-01' for a in alerts))
        self.assertFalse(any(r['alert'] for r in records if r['week']<'2024-07-01'))

    def test_zero_baseline_is_finite(self):
        last=score_series([0]*12+[8])[-1]
        self.assertTrue(all(np.isfinite(v) for v in last.values()))
        self.assertGreater(last['lift'],1)

    def test_warmup_has_no_estimated_baseline(self):
        self.assertTrue(all(x['expected'] is None and x['p']==1 for x in score_series([5]*12)))

    def test_invalid_counts_fail(self):
        for values in [[1,-1],[1,float('nan')], [1, 1.5], [[1, 2]]]:
            with self.assertRaises(ValueError):score_series(values)

    def test_invalid_monitoring_windows_fail(self):
        for window in (True, 1, 2.5):
            with self.subTest(window=window), self.assertRaises(ValueError):
                score_series([1, 2, 3], window=window)

    def test_missing_weeks_are_zero_not_dropped(self):
        rows=[]
        for i in range(25):
            r=row();r['id']=str(i);rows.append(r)
        records,_,policy=monitor(validate_frame(pd.DataFrame(rows)))
        self.assertEqual(len(records),52)
        self.assertEqual(sum(x['observed'] for x in records),25)
        self.assertEqual(policy['series'],1)


class ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model=json.loads((ROOT/'artifacts/model.json').read_text())

    def test_published_artifacts_agree(self):
        self.assertTrue(validate_artifacts())

    def test_inference_is_numeric_and_explained(self):
        result=infer(self.model,'My credit card was charged twice for the same purchase and the merchant refused to refund the duplicate payment.')
        self.assertEqual(set(result),{'product','issue'})
        for prediction in result.values():
            self.assertTrue(0<=prediction['confidence']<=1)
            self.assertTrue(prediction['top_terms'])

    def test_unknown_text_requires_review(self):
        with self.assertRaises(ValueError):infer(self.model,'zzqvv zzqvv zzqvv zzqvv zzqvv')

    def test_short_text_fails(self):
        with self.assertRaises(ValueError):infer(self.model,'bad bank')

    def test_temporal_split_and_dedup(self):
        rows=[]
        for month in [1,8,11]:
            for i in range(35):
                # Letter tokens preserve distinct hashes after numeric normalization.
                label=chr(97+i//26)+chr(97+i%26)
                r=row(narrative=f'Long original complaint with payment difficulties about subject {label} period month{chr(97+month)}')
                r['id']=str(month*100+i);r['date']=f'2024-{month:02d}-01';rows.append(r)
        duplicate=rows[0].copy();duplicate['id']='9000';duplicate['date']='2024-11-01';rows.append(duplicate)
        frame=validate_frame(pd.DataFrame(rows),True)
        result,stats=split_narratives(frame)
        self.assertEqual(stats['duplicates_removed'],1)
        self.assertEqual(stats['split_counts'],{'train':35,'validation':35,'test':35})
        self.assertNotIn('9000',set(result.id))
