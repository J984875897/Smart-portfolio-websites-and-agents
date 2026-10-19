"""Offline Jan-2025 acceptance audit, using literal official calendar cases.

No download path. Source prices and ratios are read independently from Yahoo
JSON; production parsers and monthly return formulas are not used for the
reference calculation. The inspected products remain current-vintage previews.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from portfolio.data.monthly_cache import cached_monthly_prices
from portfolio.data.snapshots import digest, load_snapshot, read_artifact

CASES = {
    'SPY': {'zone': 'America/New_York', 'end': '2025-01-31', 'close': '2025-01-31T21:00:00+00:00',
            'closed': {'2024-12-25', '2025-01-01', '2025-01-09', '2025-01-20'}},
    '2800.HK': {'zone': 'Asia/Hong_Kong', 'end': '2025-01-28', 'close': '2025-01-28T04:00:00+00:00',
                'closed': {'2024-12-25', '2024-12-26', '2025-01-01', '2025-01-29', '2025-01-30', '2025-01-31'}},
}


def _reference_prices(body, symbol):
    """Read original observations without calling the production parser."""
    record = json.loads(body)['chart']['result'][0]
    case = CASES[symbol]
    if record['meta']['symbol'] != symbol or record['meta']['exchangeTimezoneName'] != case['zone']:
        raise ValueError('source identity mismatch')
    stamps = record['timestamp']
    values = record['indicators']['adjclose'][0]['adjclose']
    if len(stamps) != len(values):
        raise ValueError('source column length mismatch')
    groups = {}
    for stamp, value in zip(stamps, values):
        day = datetime.fromtimestamp(stamp, tz=timezone.utc).astimezone(ZoneInfo(case['zone'])).date().isoformat()
        if '2024-12-01' <= day < '2025-02-01':
            number = None
            if not isinstance(value, bool) and value is not None:
                parsed = float(value)
                if math.isfinite(parsed) and parsed > 0:
                    number = parsed
            groups.setdefault(day, []).append(number)
    day = datetime(2024, 12, 1)
    expected = set()
    while day < datetime(2025, 2, 1):
        label = day.date().isoformat()
        if day.weekday() < 5 and label not in case['closed']:
            expected.add(label)
        day += timedelta(days=1)
    prices = {day: numbers[0] for day, numbers in groups.items() if len(numbers) == 1 and numbers[0] is not None}
    complete = set(groups) == expected and set(prices) == expected
    return prices, complete, expected


def _new_row(symbol):
    return {'expected_start_date': '2024-12-31', 'expected_end_date': CASES[symbol]['end'],
            'raw_start_price': None, 'raw_end_price': None, 'direct_return': None,
            'computed_return': None, 'preview_valid': False, 'matches': True}


def _check_result(symbol, raw, computed, *, source_success):
    prices, complete, expected = _reference_prices(raw, symbol)
    case = CASES[symbol]
    row = _new_row(symbol)
    row.update(raw_start_price=prices.get('2024-12-31'), raw_end_price=prices.get(case['end']), raw_sha256=digest(raw))
    if row['raw_start_price'] is not None and row['raw_end_price'] is not None:
        row['direct_return'] = row['raw_end_price'] / row['raw_start_price'] - 1
    actual = computed.returns.iloc[0]
    row.update(preview_valid=bool(actual['status'] == 'valid'), reason=str(actual['reason']))
    if math.isfinite(float(actual['local_return'])):
        row['computed_return'] = float(actual['local_return'])
    should_preview = complete and source_success
    if row['preview_valid'] != should_preview:
        raise ValueError(f'{symbol} calendar/status mismatch')
    if should_preview:
        if row['computed_return'] is None or not math.isclose(row['computed_return'], row['direct_return'], rel_tol=1e-10, abs_tol=1e-12):
            raise ValueError(f'{symbol} return mismatch')
    elif row['computed_return'] is not None:
        raise ValueError(f'{symbol} blocked return mismatch')
    for month, end in [('2024-12', '2024-12-31'), ('2025-01', case['end'])]:
        anchor = computed.monthly.loc[computed.monthly['date'].astype(str).str.startswith(month)].iloc[0]
        expected_count = sum(day.startswith(month) for day in expected)
        if anchor['expected_end_date'] != end or anchor['expected_sessions'] != expected_count:
            raise ValueError(f'{symbol} monthly anchor mismatch')
        if month == '2025-01' and datetime.fromisoformat(anchor['calendar_close_at']) != datetime.fromisoformat(case['close']):
            raise ValueError(f'{symbol} close label mismatch')
        if should_preview and float(anchor['end_price']) != prices[end]:
            raise ValueError(f'{symbol} endpoint price mismatch')
    if computed.metadata.get('historical_eligible') is not False:
        raise ValueError('historical eligibility must remain false')
    return row


def _finish(output):
    output['all_comparisons_agree'] = all(row['matches'] for row in output['products'].values())
    output['all_price_previews_valid'] = all(row['preview_valid'] for row in output['products'].values())
    return output


def verify_snapshot(root: Path, run_id: str) -> dict:
    manifest = load_snapshot(root, run_id)
    if manifest['schema_version'] != 1:
        raise ValueError('Yahoo snapshot required')
    if manifest['start'] > '2024-12-01' or manifest['end_exclusive'] < '2025-02-01':
        raise ValueError('audit needs full December 2024 and January 2025 request coverage')
    output = {'run_id': run_id, 'snapshot_integrity_verified': True,
              'historical_eligible': False, 'scope': 'January 2025 original-currency price preview', 'products': {}}
    items = {item['symbol']: item for item in manifest['items']}
    for symbol in CASES:
        item = items.get(symbol)
        row = _new_row(symbol)
        if not item or item['status'] not in {'success', 'partial'} or not item['raw_file']:
            row['reason'] = 'source_unavailable'
            output['products'][symbol] = row
            continue
        raw = read_artifact(root, run_id, item['raw_file'])
        computed = cached_monthly_prices(root, run_id, symbol, start_month='2025-01', end_month='2025-01',
                                         confirmed=True, as_of='2025-02-02T00:00:00+00:00')
        output['products'][symbol] = _check_result(symbol, raw, computed, source_success=item['status'] == 'success')
    return _finish(output)


def verify_legacy(manifest_path):
    """Explicit fallback: existing S01 original files, never a new online success."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts.probe_sources import load_verified_manifest
    from portfolio.data.daily_monthly import aggregate_daily_prices
    from portfolio.data.providers.yahoo import parse_yahoo_chart

    manifest_path = Path(manifest_path)
    manifest = load_verified_manifest(manifest_path)
    output = {'run_id': manifest['run_id'], 'source_mode': 'S01 verified offline replay',
              'snapshot_integrity_verified': True, 'historical_eligible': False,
              'scope': 'January 2025 original-currency diagnostic preview', 'products': {}}
    tables = {}
    for symbol in CASES:
        candidates = [entry for entry in manifest['files'] if entry.get('role') == 'yahoo_chart'
                      and entry.get('dataset') == symbol and entry.get('http_status') == 200
                      and 'period1' in entry.get('parameters', {})]
        if len(candidates) != 1:
            raise ValueError('ambiguous or missing S01 history response')
        entry = candidates[0]
        raw = (manifest_path.resolve().parent / entry['path']).read_bytes()
        if digest(raw) != entry['sha256'] or len(raw) != entry['bytes']:
            raise ValueError('S01 raw changed after verification')
        prices, meta = parse_yahoo_chart(json.loads(raw))
        if meta.get('symbol') != symbol or meta.get('currency') != ('USD' if symbol == 'SPY' else 'HKD') or meta.get('instrumentType') != 'ETF':
            raise ValueError('S01 identity mismatch')
        prices.attrs.update(source_name='S01 verified Yahoo history / ' + manifest['run_id'], source_hash=digest(raw))
        computed = aggregate_daily_prices(prices, symbol=symbol, start_month='2025-01', end_month='2025-01',
                                          confirmed=True, as_of='2025-02-02T00:00:00+00:00')
        computed.metadata.update(source_mode=output['source_mode'], run_id=manifest['run_id'], raw_sha256=digest(raw),
                                 source_manifest_sha256=digest(manifest_path.read_bytes()),
                                 retrieved_utc=entry.get('retrieved_utc', ''), source_file=entry['path'])
        output['products'][symbol] = _check_result(symbol, raw, computed, source_success=True)
        tables[symbol] = computed
    return _finish(output), tables


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--run-id')
    source.add_argument('--s01-manifest', type=Path, help='explicit verified offline fallback, not a new download')
    parser.add_argument('--root', type=Path, default=ROOT / 'data/downloads')
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/acceptance/S04C1')
    args = parser.parse_args()
    if args.s01_manifest:
        result, computed_tables = verify_legacy(args.s01_manifest)
    else:
        result = verify_snapshot(args.root, args.run_id)
        computed_tables = {}
        for symbol, row in result['products'].items():
            if row['reason'] != 'source_unavailable':
                computed_tables[symbol] = cached_monthly_prices(args.root, args.run_id, symbol, start_month='2025-01', end_month='2025-01',
                                                               confirmed=True, as_of='2025-02-02T00:00:00+00:00')
    args.output.mkdir(parents=True, exist_ok=True)
    for symbol, tables in computed_tables.items():
        for name in ['sessions', 'monthly', 'returns']:
            getattr(tables, name).to_csv(args.output / f'{symbol}_{name}.csv', index=False)
        (args.output / f'{symbol}_metadata.json').write_text(json.dumps(tables.metadata, ensure_ascii=False, indent=2) + '\n')
    rendered = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    (args.output / 'independent_verification.json').write_text(rendered)
    print(rendered, end='')
    return 0 if result['all_price_previews_valid'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
