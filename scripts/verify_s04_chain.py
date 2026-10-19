"""Offline S04 cross-stage audit of a complete Dec2024–Jan2025 Yahoo run."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))
from scripts.verify_daily_monthly import verify_snapshot
from portfolio.data.snapshots import load_snapshot, read_artifact
from portfolio.data.monthly_cache import cached_monthly_prices
from portfolio.data.fx_cache import cached_daily_fx
from portfolio.data.daily_hkd import connect_daily_hkd
from portfolio.data.time_eligibility import load_price_capture, load_fx_capture, qualify_daily_hkd


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--root', type=Path, default=ROOT / 'data/downloads')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out, root, rid = args.output, args.root, args.run_id
    manifest = load_snapshot(root, rid)
    price_check = verify_snapshot(root, rid)
    assert price_check['all_comparisons_agree'] and price_check['all_price_previews_valid']
    fx = cached_daily_fx(root, rid)
    fc = load_fx_capture(root, rid)
    item = next(i for i in manifest['items'] if i['symbol'] == 'HKD=X')
    raw = json.loads(read_artifact(root, rid, item['raw_file']))['chart']['result'][0]
    quotes = {
        datetime.fromtimestamp(t, timezone.utc).astimezone(ZoneInfo(raw['meta']['exchangeTimezoneName'])).strftime('%Y-%m-%d'): v
        for t, v in zip(raw['timestamp'], raw['indicators']['quote'][0]['close']) if v is not None
    }
    endpoints = [quotes[max(d for d in quotes if d[:7] == month)] for month in ['2024-12', '2025-01']]
    report = dict(run_id=rid, completed_utc=manifest['completed_utc'],
                  price_independent_check=price_check, fx_source_status=item['status'], products={})
    out.mkdir(parents=True, exist_ok=True)
    for symbol in ['SPY', '2800.HK']:
        prices = cached_monthly_prices(root, rid, symbol, start_month='2025-01', end_month='2025-01', confirmed=True)
        result = connect_daily_hkd(prices, fx, fx_confirmed=True)
        pc = load_price_capture(root, rid, symbol)
        now = qualify_daily_hkd(result, decision_at=manifest['completed_utc'], price_capture=pc, fx_capture=fc)
        past = qualify_daily_hkd(result, decision_at='2025-02-02T00:00:00Z', price_capture=pc, fx_capture=fc)
        row = result.reconciliation.iloc[0]
        local = price_check['products'][symbol]['direct_return']
        independent = (1 + local) * endpoints[1] / endpoints[0] - 1 if symbol == 'SPY' else local
        should_pass = symbol == '2800.HK' or item['status'] == 'success'
        if should_pass:
            assert row.status == 'valid' and math.isclose(row.hkd_return, independent, abs_tol=1e-12)
            assert now.rows.historical_observation_eligible.all()
        else:
            assert row.status == 'blocked' and math.isnan(row.hkd_return)
            assert 'source_not_success' in row.reason
            assert not now.rows.historical_observation_eligible.any()
        assert not past.rows.historical_observation_eligible.any()
        assert not now.rows.historical_universe_eligible.any()
        result.reconciliation.to_csv(out / (symbol + '_hkd.csv'), index=False)
        now.rows.to_csv(out / (symbol + '_time_at_capture.csv'), index=False)
        past.rows.to_csv(out / (symbol + '_time_in_2025.csv'), index=False)
        report['products'][symbol] = dict(
            status=row.status, reason=row.reason,
            hkd_return=float(row.hkd_return) if should_pass else None,
            independent_endpoint_return=independent,
            independent_endpoint_return_is_qualified=should_pass,
            at_capture_eligible=bool(now.rows.historical_observation_eligible.all()),
            at_capture_reason=now.rows.time_reason.iloc[0],
            in_2025_eligible=False, in_2025_reason=past.rows.time_reason.iloc[0])
    report['all_expected_checks_passed'] = True
    rendered = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    (out / 'chain_verification.json').write_text(rendered)
    print(rendered)


if __name__ == '__main__':
    main()
