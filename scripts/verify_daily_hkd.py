"""Independent January 2025 HKD audit of verified S01 raw files; no downloads."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
import math
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT))
import pandas as pd
from portfolio.data.daily_hkd import connect_daily_hkd
from portfolio.data.providers.yahoo import audit_price, parse_yahoo_chart
from portfolio.data.snapshots import digest
from scripts.probe_sources import load_verified_manifest
from scripts.verify_daily_monthly import verify_legacy


def _raw(manifest_path, manifest, symbol):
    entries = [e for e in manifest['files'] if e.get('role') == 'yahoo_chart' and e.get('dataset') == symbol and e.get('http_status') == 200 and 'period1' in e.get('parameters', {})]
    if len(entries) != 1:
        raise ValueError('ambiguous or missing S01 history response: ' + symbol)
    entry = entries[0]
    body = (manifest_path.parent / entry['path']).read_bytes()
    if digest(body) != entry['sha256'] or len(body) != entry['bytes']:
        raise ValueError('S01 raw hash changed after verification')
    return body, entry


def _reference_endpoints(body):
    record = json.loads(body)['chart']['result'][0]
    meta = record['meta']
    if any(meta.get(k) != v for k, v in dict(symbol='HKD=X', currency='HKD', instrumentType='CURRENCY', exchangeTimezoneName='Europe/London').items()):
        raise ValueError('FX source identity mismatch')
    stamps = record['timestamp']; quotes = record['indicators']['quote'][0]['close']
    if len(stamps) != len(quotes):
        raise ValueError('FX column length mismatch')
    observations = []
    for index, (stamp, quote) in enumerate(zip(stamps, quotes), 1):
        day = datetime.fromtimestamp(stamp, timezone.utc).astimezone(ZoneInfo('Europe/London')).date().isoformat()
        observations.append(dict(date=day, currency='USD', hkd_per_unit=quote, source_name='S01 Yahoo HKD=X unofficial raw response', source_row=index))
    references = []
    for label in ['2024-12-31', '2025-01-31']:
        candidates = [r for r in observations if r['date'][:7] == label[:7] and r['date'] <= label]
        latest = max((r['date'] for r in candidates), default='')
        selected = [r for r in candidates if r['date'] == latest]
        reason = 'missing_month'; value = None; age = None
        if selected:
            age = (date.fromisoformat(label) - date.fromisoformat(latest)).days
            raw = selected[0]['hkd_per_unit']
            try:
                value = float(raw) if raw is not None and not isinstance(raw, bool) else None
            except (TypeError, ValueError):
                value = None
            reason = 'duplicate_date' if len(selected) != 1 else ('invalid_quote' if value is None or not math.isfinite(value) or value <= 0 else ('stale_quote' if age > 7 else 'ok'))
        references.append(dict(date=label, observed_date=latest, age_days=age, hkd_per_unit=value if reason == 'ok' else None, status='valid' if reason == 'ok' else 'blocked', reason=reason))
    return observations, references


def _compare(actual, expected, name):
    if expected is None:
        if pd.notna(actual):
            raise ValueError(name + ' blocked value mismatch')
    elif not math.isfinite(float(actual)) or not math.isclose(float(actual), expected, rel_tol=1e-10, abs_tol=1e-12):
        raise ValueError(name + ' mismatch')


def verify_legacy_hkd(manifest_path):
    """Return independent report and production tables, preserving global partial."""
    manifest_path = Path(manifest_path).resolve()
    manifest = load_verified_manifest(manifest_path)
    price_report, price_tables = verify_legacy(manifest_path)
    body, entry = _raw(manifest_path, manifest, 'HKD=X')
    observations, references = _reference_endpoints(body)
    parsed, meta = parse_yahoo_chart(json.loads(body))
    global_audit = audit_price(parsed, meta, 'HKD', 'CURRENCY', symbol='HKD=X', start=manifest['start'], end=manifest['end_exclusive'])
    provenance = dict(source_mode='legacy_offline_replay', source_scope='imported raw-file January 2025 endpoint diagnostic preview', current_vintage=True, new_download=False, historical_eligible=False, available_at='', source_global_status=global_audit['status'], source_global_reason=global_audit['reason'], source_manifest_sha256=digest(manifest_path.read_bytes()), raw_sha256=digest(body), source_file=entry['path'], retrieved_utc=entry.get('retrieved_utc', ''), run_id=manifest['run_id'])
    frame = pd.DataFrame(observations)
    # Imported raw-file endpoint diagnostics are distinct from a schema1 cache.
    # Never label this old, globally partial source as a success snapshot.
    frame.attrs.update(provenance, source_hash=digest(body), source_rows=[r['source_row'] for r in observations])
    report = dict(provenance, snapshot_integrity_verified=True, endpoint_scope='December 2024 / January 2025; same-month latest row; max age 7 days', independent_fx_endpoints=references, products={})
    tables = {}
    for symbol, prices in price_tables.items():
        computed = connect_daily_hkd(prices, frame, fx_confirmed=True, max_age_days=7)
        computed.metadata.update(provenance)
        if len(computed.reconciliation)!=1 or computed.reconciliation['date'].tolist()!=['2025-01-31']:
            raise ValueError(symbol + ' reconciliation cardinality/date mismatch')
        expected_labels={r['date'] for r in references}
        if len(computed.fx_endpoints)!=len(references) or not computed.fx_endpoints['date'].is_unique or set(computed.fx_endpoints['date'])!=expected_labels:
            raise ValueError('FX endpoint cardinality/date mismatch')
        actual = computed.reconciliation.iloc[0]
        native = symbol == '2800.HK'
        price_reference = price_report['products'][symbol]
        for side in ['start', 'end']:
            if actual['price_' + side + '_observed_date'] != price_reference['expected_' + side + '_date']:
                raise ValueError(symbol + ' price endpoint date mismatch')
        endpoints_by_date={r['date']:r for r in computed.fx_endpoints.to_dict('records')}
        for expected in references:
            endpoint=endpoints_by_date[expected['date']]
            for key in ['date', 'observed_date', 'status', 'reason']:
                if endpoint[key] != expected[key]:
                    raise ValueError('FX endpoint ' + key + ' mismatch')
            _compare(endpoint['age_days'], expected['age_days'], 'FX endpoint age')
            if expected['status'] == 'valid':
                _compare(endpoint['hkd_per_unit'], expected['hkd_per_unit'], 'FX quote')
        for side, expected in zip(['start','end'], references):
            if actual['fx_'+side+'_observed_date']!=expected['observed_date']:
                raise ValueError('FX reconciliation observed date mismatch')
            _compare(actual['fx_'+side+'_age_days'], expected['age_days'], 'FX reconciliation age')
        local = price_report['products'][symbol]['direct_return']
        valid = price_report['products'][symbol]['preview_valid'] and (native or all(r['status'] == 'valid' for r in references))
        fx = 0.0 if native else (references[1]['hkd_per_unit'] / references[0]['hkd_per_unit'] - 1 if valid else None)
        hkd = ((1 + local) * (1 + fx) - 1) if valid else None
        for side, expected in zip(['start','end'], references):
            _compare(actual['fx_'+side], (1.0 if native else expected['hkd_per_unit']) if valid else None, 'FX reconciliation quote')
        if (actual['status'] == 'valid') != valid:
            raise ValueError(symbol + ' HKD status mismatch')
        if not valid and not native:
            for side, endpoint in zip(['start', 'end'], references):
                if endpoint['status'] != 'valid' and 'fx_' + side + ':' + endpoint['reason'] not in actual['reason']:
                    raise ValueError('FX blocked reason mismatch')
        for field, expected in [('local_return', local), ('fx_return', fx if valid else None), ('cross_term', local * fx if valid else None), ('hkd_return', hkd)]:
            _compare(actual[field], expected, symbol + ' ' + field)
        if actual['available_at'] != '' or bool(actual['historical_eligible']):
            raise ValueError('historical eligibility mismatch')
        report['products'][symbol] = dict(price_report['products'][symbol], direct_fx_return=fx, direct_hkd_return=hkd, computed_hkd_return=float(actual['hkd_return']) if valid else None, hkd_preview_valid=bool(valid), reason=actual['reason'], price_raw_sha256=prices.metadata['raw_sha256'], matches=True)
        tables[symbol] = computed
    report['all_comparisons_agree'] = True
    report['all_hkd_previews_valid'] = all(r['hkd_preview_valid'] for r in report['products'].values())
    return report, tables


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--s01-manifest', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    report, tables = verify_legacy_hkd(args.s01_manifest)
    args.output.mkdir(parents=True, exist_ok=True)
    for symbol, result in tables.items():
        result.reconciliation.to_csv(args.output / f'{symbol}_reconciliation.csv', index=False)
        (args.output / f'{symbol}_metadata.json').write_text(json.dumps(result.metadata, indent=2, ensure_ascii=False) + '\n')
    first = next(iter(tables.values()))
    for name in ['fx_endpoints', 'fx_observations']:
        getattr(first, name).to_csv(args.output / (name + '.csv'), index=False)
    pd.DataFrame(report['independent_fx_endpoints']).to_csv(args.output / 'raw_fx_endpoint_reference.csv', index=False)
    rendered = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    (args.output / 'independent_verification.json').write_text(rendered)
    print(rendered, end='')
    return 0 if report['all_hkd_previews_valid'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
