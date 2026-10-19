"""Offline S05-B acceptance; synthetic IDs are not real investment products."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import pandas as pd
from portfolio.allocation.cardinality import check_cardinality
from portfolio.data.contracts import DataBundle
from portfolio.data.alignment import TIMING_FIELDS
from portfolio.universe.inputs import prepare_candidate_input
from portfolio.universe.screening_samples import sample_screening_inputs
from portfolio.universe.screening import screen_candidates, universe_result_is_current
from verify_candidate_inputs import file_hashes

PARAMS = dict(end_month='2025-01',decision_at='2025-02-01T06:00:00+08:00')


def synthetic_input():
    return prepare_candidate_input(*sample_screening_inputs(), **PARAMS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'outputs/acceptance/S05B')
    parser.add_argument('--real-bundle',type=Path)
    args = parser.parse_args()
    real_path = args.real_bundle or Path(json.loads((ROOT/'outputs/acceptance/S02/import_summary.json').read_text())['real_bundle_path'])
    real_path = real_path.resolve(); out = args.output.resolve()
    if out == real_path or real_path in out.parents or out in real_path.parents:
        raise ValueError('output and source bundle must be separate directories')
    before = file_hashes(real_path)
    c = synthetic_input()
    before_input = c.input_fingerprint
    r = screen_candidates(c,k=30)
    blocked = screen_candidates(c,k=30,excluded_asset_ids=('SYNTH_SCREEN_099',))
    assert r.cardinality.n == 100 and r.cardinality.status == 'passed'
    assert blocked.cardinality.n == 99 and blocked.cardinality.status == 'pool_too_small'
    assert r.matrix.shape == (60,100) and ((r.matrix-.01).abs() < 1e-12).all().all()
    assert universe_result_is_current(r,c,k=30)
    assert not universe_result_is_current(r,c,k=30,include_stocks=True)
    assert c.input_fingerprint == before_input
    cases = []
    for k,n,expected in [(20,66,False),(20,67,True),(30,99,False),(30,100,True),
                         (50,166,False),(50,167,True),(100,333,False),(100,334,True)]:
        case = check_cardinality(k,n)
        assert (case.status == 'passed') == expected
        cases.append(asdict(case))
    for k in [True,False,30.0,30.5,'30',None,19,101]:
        case = check_cardinality(k,100)
        assert case.status == 'invalid_k'
        cases.append(asdict(case))
    empty = check_cardinality(30,0)
    assert empty.ratio is None and empty.status == 'pool_too_small'
    cases.append(asdict(empty))
    real = DataBundle.load(real_path)
    assert not real.assets.empty and real.observations.frequency.eq('daily').all()
    real_input = prepare_candidate_input(real,pd.DataFrame(columns=['date','currency','hkd_per_unit','source_name']),
                                         pd.DataFrame(columns=TIMING_FIELDS),
                                         adjusted_price_assets=real.assets.asset_id.tolist(),**PARAMS)
    real_result = screen_candidates(real_input,k=30)
    assert real_result.cardinality.n == 0
    assert real_result.audit.reason.str.contains('monthly_preparation_required').all()
    assert before == file_hashes(real_path)
    out.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(cases).to_csv(out/'cardinality_cases.csv',index=False)
    r.audit.to_csv(out/'universe_audit.csv',index=False)
    blocked.audit.to_csv(out/'universe_n99_audit.csv',index=False)
    r.matrix.to_csv(out/'synthetic_hkd_matrix.csv')
    real_result.audit.to_csv(out/'real_universe_audit.csv',index=False)
    (out/'synthetic_evidence.json').write_text(json.dumps(r.evidence|{'screening_fingerprint':r.fingerprint},ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    (out/'real_evidence.json').write_text(json.dumps(real_result.evidence|{'screening_fingerprint':real_result.fingerprint},ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    summary = dict(stage='S05-B',status='expected_checks_passed',no_network=True,
                   synthetic_n100_status=r.cardinality.status,synthetic_n99_status=blocked.cardinality.status,
                   synthetic_funnel=r.counts,synthetic_is_artificial=True,real_n=real_result.cardinality.n,
                   real_funnel=real_result.counts,real_bundle_path=str(real_path),
                   real_status=real_result.cardinality.status,source_files_unchanged=True,
                   historical_universe_certified=False,portfolio_constructed=False)
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
