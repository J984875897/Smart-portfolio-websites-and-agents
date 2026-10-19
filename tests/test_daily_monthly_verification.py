"""Independent Jan-2025 acceptance arithmetic from original Yahoo response."""
from datetime import datetime, timedelta
import json
from zoneinfo import ZoneInfo

import pytest

from portfolio.data.providers.base import RawResponse
from portfolio.data.updates import run_update


def chart_bytes(symbol, *, omit=None):
    hk = symbol == '2800.HK'
    closed = {'2024-12-25', '2024-12-26', '2025-01-01', '2025-01-29', '2025-01-30', '2025-01-31'} if hk else {'2024-12-25', '2025-01-01', '2025-01-09', '2025-01-20'}
    dates = []
    day = datetime(2024, 12, 1)
    while day < datetime(2025, 2, 1):
        label = day.strftime('%Y-%m-%d')
        if day.weekday() < 5 and label not in closed and label != omit:
            dates.append(label)
        day += timedelta(days=1)
    zone = ZoneInfo('Asia/Hong_Kong' if hk else 'America/New_York')
    stamps = [int(datetime.fromisoformat(d + 'T09:30:00').replace(tzinfo=zone).timestamp()) for d in dates]
    prices = [100 if d < '2025-01-01' else 110 for d in dates]
    return json.dumps({'chart': {'error': None, 'result': [{
        'meta': {'symbol': symbol, 'currency': 'HKD' if hk else 'USD', 'instrumentType': 'ETF', 'exchangeTimezoneName': str(zone)},
        'timestamp': stamps,
        'indicators': {'quote': [{'open': prices, 'high': prices, 'low': prices, 'close': prices, 'volume': [100] * len(dates)}], 'adjclose': [{'adjclose': prices}]},
    }]}}).encode()


def snapshot(root, *, omit=None):
    return run_update(root, ['SPY', '2800.HK'], '2024-12-01', '2025-02-01',
                      fetch=lambda symbol, *args: RawResponse(chart_bytes(symbol, omit=omit), 200))


def test_independent_original_endpoints(tmp_path):
    from scripts.verify_daily_monthly import verify_snapshot
    rid = snapshot(tmp_path)
    result = verify_snapshot(tmp_path, rid)
    assert result['run_id'] == rid
    assert result['all_comparisons_agree'] is True
    assert result['all_price_previews_valid'] is True
    assert result['historical_eligible'] is False
    for symbol, end in [('SPY', '2025-01-31'), ('2800.HK', '2025-01-28')]:
        row = result['products'][symbol]
        assert row['expected_start_date'] == '2024-12-31'
        assert row['expected_end_date'] == end
        assert row['raw_start_price'] == 100
        assert row['raw_end_price'] == 110
        assert row['direct_return'] == pytest.approx(.1)
        assert row['computed_return'] == pytest.approx(.1)
        assert row['matches'] is True


def test_missing_endpoint_is_diagnostic_not_false_success(tmp_path):
    from scripts.verify_daily_monthly import verify_snapshot
    result = verify_snapshot(tmp_path, snapshot(tmp_path, omit='2025-01-31'))
    assert result['all_price_previews_valid'] is False
    assert result['all_comparisons_agree'] is True
    assert result['products']['SPY']['computed_return'] is None
    assert result['products']['SPY']['raw_end_price'] is None
    assert result['products']['2800.HK']['computed_return'] == pytest.approx(.1)


def test_corrupt_cache_stops_auditor(tmp_path):
    from scripts.verify_daily_monthly import verify_snapshot
    from portfolio.data.snapshots import load_snapshot
    rid = snapshot(tmp_path)
    manifest = load_snapshot(tmp_path, rid)
    (tmp_path / 'runs' / rid / manifest['items'][0]['raw_file']).write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='hash'):
        verify_snapshot(tmp_path, rid)


def test_wrong_computed_return_is_detected(tmp_path, monkeypatch):
    from scripts import verify_daily_monthly as verifier
    original = verifier.cached_monthly_prices

    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        result.returns.loc[:, 'local_return'] = .2
        return result

    monkeypatch.setattr(verifier, 'cached_monthly_prices', changed)
    with pytest.raises(ValueError, match='mismatch'):
        verifier.verify_snapshot(tmp_path, snapshot(tmp_path))


def legacy_manifest(root):
    from portfolio.data.snapshots import digest
    entries = []
    for symbol in ['SPY', '2800.HK']:
        body = chart_bytes(symbol)
        filename = symbol + '.json'
        (root / filename).write_bytes(body)
        entries.append({'path': filename, 'sha256': digest(body), 'bytes': len(body),
                        'role': 'yahoo_chart', 'dataset': symbol, 'http_status': 200,
                        'parameters': {'period1': 1, 'period2': 2}})
    manifest = {'schema_version': 1, 'run_id': 'S01_FIXTURE', 'start': '2024-12-01', 'end_exclusive': '2025-02-01', 'files': entries}
    path = root / 'snapshot_manifest.json'
    path.write_text(json.dumps(manifest))
    return path


def test_legacy_replay_is_explicit_and_verified(tmp_path):
    from scripts.verify_daily_monthly import verify_legacy
    result, tables = verify_legacy(legacy_manifest(tmp_path))
    assert result['source_mode'] == 'S01 verified offline replay'
    assert result['all_comparisons_agree'] is True
    assert result['all_price_previews_valid'] is True
    assert result['historical_eligible'] is False
    assert set(tables) == {'SPY', '2800.HK'}
    assert result['products']['SPY']['computed_return'] == pytest.approx(.1)
    (tmp_path / 'SPY.json').write_bytes(b'changed')
    with pytest.raises(ValueError):
        verify_legacy(tmp_path / 'snapshot_manifest.json')
