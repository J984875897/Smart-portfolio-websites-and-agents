"""Independent raw-response HKD auditor acceptance checks."""
from datetime import datetime
import json
from zoneinfo import ZoneInfo

import pytest
from test_daily_monthly_verification import legacy_manifest
from portfolio.data.snapshots import digest


def fixture_manifest(root, *, missing=False, bad_latest=False):
    path = legacy_manifest(root)
    days = ['2024-12-31', '2025-01-30'] + ([] if missing else ['2025-01-31'])
    quotes = [7.8, 7.85] + ([] if missing else [None if bad_latest else 7.9])
    body = json.dumps({'chart': {'result': [{'meta': {'symbol': 'HKD=X', 'currency': 'HKD', 'instrumentType': 'CURRENCY', 'exchangeTimezoneName': 'Europe/London'}, 'timestamp': [int(datetime.fromisoformat(d).replace(tzinfo=ZoneInfo('Europe/London')).timestamp()) for d in days], 'indicators': {'quote': [{'close': quotes}]}}], 'error': None}}).encode()
    (root / 'fx.json').write_bytes(body)
    manifest = json.loads(path.read_text())
    manifest['files'].append(dict(path='fx.json', sha256=digest(body), bytes=len(body), role='yahoo_chart', dataset='HKD=X', http_status=200, parameters={'period1': 1}))
    path.write_text(json.dumps(manifest))
    return path


def test_hand_calculation_and_provenance(tmp_path):
    from scripts.verify_daily_hkd import verify_legacy_hkd
    report, tables = verify_legacy_hkd(fixture_manifest(tmp_path))
    spy = report['products']['SPY']
    assert spy['direct_hkd_return'] == pytest.approx(1.1 * 7.9 / 7.8 - 1)
    assert spy['direct_fx_return'] == pytest.approx(7.9 / 7.8 - 1)
    assert report['all_hkd_previews_valid'] is True
    assert report['source_mode'] == 'legacy_offline_replay'
    assert report['new_download'] is False
    assert report['historical_eligible'] is False
    assert tables['2800.HK'].reconciliation.iloc[0].hkd_return == pytest.approx(.1)


def test_bad_latest_is_blocked_without_fallback(tmp_path):
    from scripts.verify_daily_hkd import verify_legacy_hkd
    report, tables = verify_legacy_hkd(fixture_manifest(tmp_path, bad_latest=True))
    assert report['all_comparisons_agree'] is True
    assert report['all_hkd_previews_valid'] is False
    assert report['source_global_status'] == 'partial'
    assert report['products']['SPY']['computed_hkd_return'] is None
    assert 'invalid_quote' in report['products']['SPY']['reason']
    assert len(tables['SPY'].fx_observations) == 3


def test_missing_month_is_matching_diagnostic(tmp_path):
    from scripts.verify_daily_hkd import verify_legacy_hkd
    path = fixture_manifest(tmp_path)
    payload = json.loads((tmp_path / 'fx.json').read_bytes())
    record = payload['chart']['result'][0]
    record['timestamp'] = record['timestamp'][:1]
    record['indicators']['quote'][0]['close'] = [7.8]
    body = json.dumps(payload).encode()
    (tmp_path / 'fx.json').write_bytes(body)
    manifest = json.loads(path.read_text()); manifest['files'][-1].update(sha256=digest(body), bytes=len(body)); path.write_text(json.dumps(manifest))
    report, _ = verify_legacy_hkd(path)
    assert report['all_comparisons_agree'] is True
    assert 'missing_month' in report['products']['SPY']['reason']


def test_corrupt_raw_rejected(tmp_path):
    from scripts.verify_daily_hkd import verify_legacy_hkd
    path = fixture_manifest(tmp_path)
    (tmp_path / 'fx.json').write_bytes(b'changed')
    with pytest.raises(ValueError):
        verify_legacy_hkd(path)


def test_wrong_production_hkd_detected(tmp_path, monkeypatch):
    from scripts import verify_daily_hkd as audit
    original = audit.connect_daily_hkd
    def wrong(*args, **kwargs):
        result = original(*args, **kwargs)
        result.reconciliation.loc[:, 'hkd_return'] = .5
        return result
    monkeypatch.setattr(audit, 'connect_daily_hkd', wrong)
    with pytest.raises(ValueError, match='mismatch'):
        audit.verify_legacy_hkd(fixture_manifest(tmp_path))


@pytest.mark.parametrize('tamper', [
    'empty_endpoints', 'short_endpoints', 'duplicate_endpoint', 'extra_endpoint', 'wrong_label',
    'empty_reconciliation', 'extra_reconciliation', 'wrong_reconciliation_label',
    'fx_start_observed_date', 'fx_end_observed_date', 'fx_start_age_days', 'fx_end_age_days',
    'fx_start', 'fx_end', 'endpoint_age_missing', 'endpoint_quote',
])
def test_evidence_tampering_detected(tmp_path, monkeypatch, tamper):
    import pandas as pd
    from scripts import verify_daily_hkd as audit
    original = audit.connect_daily_hkd
    def wrong(*args, **kwargs):
        result = original(*args, **kwargs)
        if tamper == 'empty_endpoints': result.fx_endpoints = result.fx_endpoints.iloc[:0]
        elif tamper == 'short_endpoints': result.fx_endpoints = result.fx_endpoints.iloc[:1]
        elif tamper == 'duplicate_endpoint': result.fx_endpoints = pd.concat([result.fx_endpoints.iloc[:1]] * 2, ignore_index=True)
        elif tamper == 'extra_endpoint': result.fx_endpoints = pd.concat([result.fx_endpoints, result.fx_endpoints.iloc[:1]], ignore_index=True)
        elif tamper == 'wrong_label': result.fx_endpoints.loc[0, 'date'] = '1900-01-31'
        elif tamper == 'empty_reconciliation': result.reconciliation = result.reconciliation.iloc[:0]
        elif tamper == 'extra_reconciliation': result.reconciliation = pd.concat([result.reconciliation] * 2, ignore_index=True)
        elif tamper == 'wrong_reconciliation_label': result.reconciliation.loc[0, 'date'] = '1900-01-31'
        elif tamper == 'endpoint_age_missing': result.fx_endpoints.loc[0, 'age_days'] = None
        elif tamper == 'endpoint_quote': result.fx_endpoints.loc[0, 'hkd_per_unit'] = 9.0
        else: result.reconciliation.loc[0, tamper] = '1900-01-01' if tamper.endswith('observed_date') else 99.0
        return result
    monkeypatch.setattr(audit, 'connect_daily_hkd', wrong)
    with pytest.raises(ValueError):
        audit.verify_legacy_hkd(fixture_manifest(tmp_path))
