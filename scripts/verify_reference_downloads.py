"""Independent raw-to-table checks; networking requires an explicit --online."""
from __future__ import annotations

import argparse
import csv
from datetime import date
import io
import json
import math
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from portfolio.data.reference_updates import REFERENCE_CATALOG, run_reference_update
from portfolio.data.snapshots import load_snapshot, read_artifact, update_log


def _hkma_observations(body: bytes, manifest: dict, previous: dict) -> dict:
    """Read one complete observation page without using the production parser."""
    payload = json.loads(body)
    if payload['header']['success'] is not True:
        raise ValueError('HKMA header rejected')
    records = payload['result']['records']
    if not isinstance(records, list) or len(records) > manifest['page_size']:
        raise ValueError('HKMA records invalid')
    observations = {}
    last_day = max(previous) if previous else None
    for record in records:
        day = record['end_of_day']
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError('HKMA date invalid')
        value = float(record['usd'])
        if not math.isfinite(value) or value <= 0:
            raise ValueError('HKMA value invalid')
        if not manifest['start'] <= day < manifest['end_exclusive']:
            raise ValueError('HKMA date outside requested interval')
        if last_day is not None and day <= last_day:
            raise ValueError('HKMA dates overlap or are unordered')
        observations[day] = value
        last_day = day
    return observations


def verify(root: Path, run_id: str) -> dict:
    manifest = load_snapshot(root, run_id)
    if manifest['schema_version'] != 2:
        raise ValueError('reference snapshot required')
    checks = []
    for item in manifest['items']:
        result = {key: item[key] for key in ('dataset', 'status', 'reason', 'rows', 'first_date', 'last_date')}
        result['raw_files'] = item['raw_files']
        result['table_checked'] = False
        if item['table_file']:
            payload = read_artifact(root, run_id, item['table_file'])
            rows = list(csv.DictReader(io.StringIO(payload.decode())))
            assert len(rows) == item['rows'], 'table row count'
            assert rows, 'table unexpectedly empty'
            if item['kind'] == 'factor':
                source = read_artifact(root, run_id, item['source_file'])
                archive = read_artifact(root, run_id, item['raw_files'][0])
                with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
                    members = [name for name in zipped.namelist() if name.lower().endswith('.csv')]
                    assert len(members) == 1 and zipped.read(members[0]) == source, 'raw CSV differs from ZIP'
                # Do not call the production parser: identify monthly raw rows directly.
                raw_rows = [[v.strip() for v in row] for row in csv.reader(io.StringIO(source.decode('utf-8-sig')))]
                header = next(row for row in raw_rows if row and row[0] == '' and 'Mkt-RF' in row)
                original = {row[0]: dict(zip(header[1:], row[1:])) for row in raw_rows
                            if row and len(row[0]) == 6 and row[0].isdigit()}
                comparisons = 0
                for row in rows:
                    assert manifest['start'][:7] <= row['month'] < manifest['end_exclusive'][:7]
                    raw = original[row['month'].replace('-', '')]
                    for field, value in row.items():
                        if field == 'month':
                            continue
                        expected = float(raw[field])
                        if expected in (-99.99, -999):
                            assert value == '' or math.isnan(float(value)), 'missing sentinel was filled'
                        else:
                            assert math.isclose(float(value), expected / 100, rel_tol=0, abs_tol=5.1e-13), 'percent conversion'
                        comparisons += 1
                if item['status'] == 'success':
                    # Generate the expected month sequence without the production coverage code.
                    year, month = map(int, manifest['start'][:7].split('-'))
                    expected_months = []
                    while f'{year:04d}-{month:02d}-01' < manifest['end_exclusive']:
                        expected_months.append(f'{year:04d}-{month:02d}')
                        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
                    assert [row['month'] for row in rows] == expected_months, 'requested monthly coverage'
                result['numeric_cells_verified'] = comparisons
                result['first_month_raw_percent'] = original[rows[0]['month'].replace('-', '')]
                result['first_month_decimal'] = rows[0]
                first, last = rows[0]['month'] + '-01', rows[-1]['month'] + '-01'
            else:
                original = {}
                for page in item['pages']:
                    if page['status_code'] != 200:
                        assert item['status'] != 'success', 'HKMA unsuccessful response'
                        break
                    body = read_artifact(root, run_id, page['path'])
                    try:
                        observations = _hkma_observations(body, manifest, original)
                    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
                        # Failed/cancelled runs retain the rejected response after valid pages.
                        assert item['status'] != 'success', 'HKMA invalid raw evidence'
                        break
                    original.update(observations)
                for row in rows:
                    assert manifest['start'] <= row['date'] < manifest['end_exclusive']
                    assert row['date'] in original, 'HKMA date lacks valid raw evidence'
                    assert math.isclose(float(row['hkd_per_usd']), original[row['date']], rel_tol=0, abs_tol=5.1e-13), 'HKMA value differs from raw evidence'
                result['numeric_cells_verified'] = len(rows)
                result['unit'] = 'HKD per USD'
                first, last = rows[0]['date'], rows[-1]['date']
            assert first == item['first_date'] and last == item['last_date'], 'actual dates mismatch'
            result['table_checked'] = True
        checks.append(result)
    return dict(run_id=run_id, snapshot_integrity_verified=True,
                start=manifest['start'], end_exclusive=manifest['end_exclusive'],
                all_requested_sources_success=all(i['status'] == 'success' for i in manifest['items']),
                checks=checks, scope='Download evidence only; no daily-calendar or historical-availability certification.')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--online', action='store_true')
    mode.add_argument('--replay', metavar='RUN_ID')
    parser.add_argument('--root', type=Path, default=ROOT / 'data/reference_downloads')
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/acceptance/S04B')
    args = parser.parse_args()
    run_id = run_reference_update(args.root, list(REFERENCE_CATALOG), '2025-01-01', '2026-01-01') if args.online else args.replay
    report = verify(args.root, run_id)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / ('online_run.json' if args.online else 'offline_replay.json')).write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    (args.output / 'snapshot_manifest.json').write_text(json.dumps(load_snapshot(args.root, run_id), indent=2, ensure_ascii=False) + '\n')
    update_log(args.root).to_csv(args.output / 'update_log.csv', index=False)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    # Exit 1 preserves a visible incomplete-source result even when cache integrity passes.
    return 0 if report['all_requested_sources_success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
