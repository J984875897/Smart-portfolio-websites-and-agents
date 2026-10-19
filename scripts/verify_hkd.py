"""Offline S03-A evidence; artificial inputs and independent hand calculations."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from portfolio.data import DataBundle, ImportConfig, commit_import, preview_import, read_file
from portfolio.data.fx import reconcile_hkd

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/hkd'
EXPECTED_HKD = 0.02294871794871795


def import_fixture(bundle, filename, kind):
    raw = read_file(FIXTURES / filename)
    config = ImportConfig(
        mapping={column: column for column in raw.columns},
        source_name='SYNTH', value_kind=kind, return_unit='decimal',
    )
    preview = preview_import(raw, config, existing=bundle)
    assert not preview.rows['status'].eq('blocked').any(), preview.issues
    # Acknowledgement applies only to our expressly artificial -100% test row.
    return commit_import(preview, bundle, allow_review=True)


def verify(output):
    output.mkdir(parents=True, exist_ok=True)
    bundle = import_fixture(DataBundle(), 'monthly_total_returns.csv', 'total_return')
    bundle = import_fixture(bundle, 'monthly_adjusted_prices.csv', 'adjusted_price')
    original = bundle.observations.copy(deep=True)
    fx = read_file(FIXTURES / 'fx.csv')
    adjusted = ('SYNTH_ADJ',)
    result = reconcile_hkd(bundle, fx, adjusted_price_assets=adjusted)
    evidence = result.reconciliation
    january = evidence[evidence['date'].eq('2025-01-31')].set_index('asset_id')
    independent = {
        'SYNTH_USD': EXPECTED_HKD,
        'SYNTH_HKD': 0.01,
        'SYNTH_ZERO': 0.01282051282051282,
        'SYNTH_LOSS': -1.0,
        'SYNTH_ADJ': EXPECTED_HKD,
    }
    for asset, expected in independent.items():
        assert january.loc[asset, 'status'] == 'valid'
        assert np.isclose(january.loc[asset, 'hkd_return'], expected, rtol=0, atol=1e-12)
    valid = evidence[evidence['status'].eq('valid')]
    np.testing.assert_allclose(
        valid['hkd_return'].astype(float),
        (valid['local_return'] + valid['fx_return'] + valid['cross_term']).astype(float),
        rtol=0, atol=1e-12,
    )
    pd.testing.assert_frame_equal(original, bundle.observations)
    missing = reconcile_hkd(bundle, read_file(FIXTURES / 'fx_missing_end.csv'), adjusted_price_assets=adjusted)
    unconfirmed = reconcile_hkd(bundle, fx)
    plain_bundle = import_fixture(DataBundle(), 'monthly_adjusted_prices.csv', 'price')
    plain = reconcile_hkd(plain_bundle, fx)
    foreign = missing.reconciliation[missing.reconciliation['currency'].eq('USD')]
    assert foreign['hkd_return'].isna().all()
    assert foreign['status'].eq('blocked').all()
    native = missing.reconciliation[missing.reconciliation['asset_id'].eq('SYNTH_HKD')].iloc[0]
    assert native['status'] == 'valid' and native['hkd_return'] == 0.01
    unverified = unconfirmed.reconciliation[unconfirmed.reconciliation['asset_id'].eq('SYNTH_ADJ')]
    assert unverified['hkd_return'].isna().all()
    assert plain.reconciliation['hkd_return'].isna().all()
    failures = pd.concat([
        checked.reconciliation.assign(case=name)
        for name, checked in [('missing_fx', missing), ('unconfirmed_adjustment', unconfirmed), ('ordinary_price', plain)]
    ], ignore_index=True)
    for filename, table in [
        ('hkd_reconciliation.csv', evidence), ('local_returns.csv', result.local_returns),
        ('fx_issues.csv', result.fx_issues), ('failure_cases.csv', failures),
    ]:
        table.to_csv(output / filename, index=False)
    inputs = ['monthly_total_returns.csv', 'monthly_adjusted_prices.csv', 'fx.csv', 'fx_missing_end.csv']
    summary = {
        'synthetic': True,
        'input_hashes': {name: hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() for name in inputs},
        'base_currency': 'HKD', 'return_unit': 'decimal',
        'date_convention': 'Explicit calendar-month-end valuations; exact FX endpoints only',
        'adjusted_price_assets_confirmed': list(adjusted),
        'assets': len(bundle.assets), 'observations': len(bundle.observations),
        'valid_hkd_rows': len(valid), 'blocked_hkd_rows': len(evidence) - len(valid),
        'independent_expected_hkd': independent,
        'time_alignment_verified': False, 'qualified_candidate_count_computed': False,
        'risk_free_proxy_available': False,
    }
    (output / 'summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n')
    print(f'S03A synthetic checks passed: {len(valid)} valid HKD rows; source observations unchanged.')
    print(f'USD 1% / FX 7.8 -> 7.9: {january.loc["SYNTH_USD", "hkd_return"]:.12%}')
    print('Missing FX is blocked, HKD native remains 1%; S03B/C remain unverified.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/acceptance/S03A')
    verify(parser.parse_args().output)
