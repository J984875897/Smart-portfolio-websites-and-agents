"""Offline S05-A acceptance: synthetic success and existing daily-input blocking."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import pandas as pd
from portfolio.data.contracts import DataBundle
from portfolio.data.alignment import TIMING_FIELDS
from portfolio.universe.inputs import prepare_candidate_input, candidate_input_is_current
from portfolio.universe.samples import sample_candidate_inputs

PARAMS = dict(end_month='2025-01', decision_at='2025-02-01T06:00:00+08:00')


def export(result, output):
    output.mkdir(parents=True, exist_ok=True)
    for field, filename in [('assets', 'assets.csv'), ('data_eligibility', 'data_eligibility.csv'),
                            ('coverage', 'coverage.csv'), ('structures', 'structures.csv'),
                            ('reconciliation', 'reconciliation.csv')]:
        getattr(result, field).to_csv(output / filename, index=False)
    result.matrix.to_csv(output / 'hkd_matrix.csv')
    evidence = dict(result.evidence, input_fingerprint=result.input_fingerprint)
    (output / 'input_evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def file_hashes(path):
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob('*') if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/acceptance/S05A')
    parser.add_argument('--real-bundle', type=Path)
    args = parser.parse_args()
    if args.real_bundle is None:
        source = json.loads((ROOT / 'outputs/acceptance/S02/import_summary.json').read_text())
        args.real_bundle = Path(source['real_bundle_path'])
    real_path = args.real_bundle.resolve()
    # Never allow an acceptance export to overwrite the evidence it checks.
    out = args.output.resolve()
    if out == real_path or real_path in out.parents or out in real_path.parents:
        raise ValueError('output and source bundle must be separate directories')
    before = file_hashes(real_path)
    bundle, fx, timing, structures = sample_candidate_inputs()
    result = prepare_candidate_input(bundle, fx, timing, structures, **PARAMS)
    assert result.matrix.shape == (60, 2)
    assert list(result.matrix) == ['HKD_COMPLETE', 'USD_COMPLETE']
    assert ((result.matrix - .01).abs() < 1e-12).all().all()
    assert result.matrix.index[0] == '2020-02-29' and result.matrix.index[-1] == '2025-01-31'
    valid = result.data_eligibility.set_index('asset_id').valid_months.to_dict()
    assert valid == dict(HKD_COMPLETE=60, USD_COMPLETE=60, MISSING_MIDDLE=59, SHORT_HISTORY=59, MISSING_END_FX=59)
    assert candidate_input_is_current(result, bundle, fx, timing, structures, **PARAMS)
    timing.loc[0, 'source_name'] = 'changed declaration'
    assert not candidate_input_is_current(result, bundle, fx, timing, structures, **PARAMS)
    export(result, out / 'synthetic')
    real = DataBundle.load(real_path)
    assert not real.assets.empty and real.observations.frequency.eq('daily').all()
    blocked = prepare_candidate_input(real, pd.DataFrame(columns=['date', 'currency', 'hkd_per_unit', 'source_name']),
                                      pd.DataFrame(columns=TIMING_FIELDS),
                                      adjusted_price_assets=real.assets.asset_id.tolist(), **PARAMS)
    assert blocked.matrix.shape == (60, 0)
    assert blocked.data_eligibility.status.eq('excluded').all()
    assert blocked.data_eligibility.reason.str.contains('monthly_preparation_required').all()
    assert before == file_hashes(real_path)
    export(blocked, out / 'real_daily_input')
    report = dict(
        stage='S05-A', status='expected_checks_passed', no_network=True,
        synthetic=dict(matrix_shape=list(result.matrix.shape), data_eligible_asset_ids=list(result.matrix),
                       expected_monthly_hkd_return=.01, valid_months=valid, stale_input_invalidated=True),
        real_daily_input=dict(bundle_path=str(real_path), product_count=len(real.assets),
                              observation_count=len(real.observations), matrix_shape=list(blocked.matrix.shape),
                              outcome='blocked: daily frequency needs separate monthly preparation and timing evidence'),
        source_files_unchanged=True, historical_universe_certified=False,
        formal_candidate_N_computed=False, portfolio_created=False)
    (out / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
