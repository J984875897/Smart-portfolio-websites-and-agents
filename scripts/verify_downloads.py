"""S04-A small real download or offline snapshot verification; no account/key."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--online', action='store_true', help='Explicitly request SPY, 2800.HK and HKD=X once each')
    mode.add_argument('--replay', help='Read an existing run without network')
    parser.add_argument('--root', type=Path, default=ROOT / 'data/downloads')
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/acceptance/S04A')
    args = parser.parse_args()
    from portfolio.data.updates import run_update
    from portfolio.data.snapshots import load_snapshot, read_artifact, update_log
    run_id = (run_update(args.root, ['SPY', '2800.HK', 'HKD=X'], '2025-01-01', '2025-02-01')
              if args.online else args.replay)
    manifest = load_snapshot(args.root, run_id)
    results = []
    for item in manifest['items']:
        result = {k: item.get(k) for k in ['symbol', 'status', 'reason', 'rows', 'raw_sha256']}
        if item.get('daily_file'):
            raw = read_artifact(args.root, run_id, item['raw_file'])
            chart = json.loads(raw)['chart']['result'][0]
            meta = chart['meta']
            frame = pd.read_csv(BytesIO(read_artifact(args.root, run_id, item['daily_file'])))
            dates = [datetime.fromtimestamp(s, timezone.utc).astimezone(ZoneInfo(meta['exchangeTimezoneName'])).strftime('%Y-%m-%d')
                     for s in chart['timestamp']]
            keep = [i for i, day in enumerate(dates) if manifest['start'] <= day < manifest['end_exclusive']]
            assert frame['date'].tolist() == [dates[i] for i in keep]
            for field in ['close', 'adj_close']:
                values = (chart['indicators']['quote'][0].get('close') if field == 'close'
                          else chart['indicators'].get('adjclose', [{}])[0].get('adjclose'))
                values = values if values is not None else [None] * len(dates)
                expected = np.array([np.nan if values[i] is None else values[i] for i in keep])
                assert np.allclose(frame[field], expected, equal_nan=True)
            assert hashlib.sha256(raw).hexdigest() == item['raw_sha256']
            assert meta['symbol'] == item['symbol']
            assert meta['currency'] == ('USD' if item['symbol'] == 'SPY' else 'HKD')
            if item.get('import_file'):
                imported = pd.read_csv(BytesIO(read_artifact(args.root, run_id, item['import_file'])))
                assert imported['date'].tolist() == frame['date'].tolist()
                assert np.allclose(imported['value'], frame['adj_close'], equal_nan=True)
            result.update(currency=meta['currency'], first_date=frame['date'].min(), last_date=frame['date'].max(),
                          missing_close=int(frame['close'].isna().sum()),
                          raw_to_daily_values_verified=True)
        results.append(result)
    args.output.mkdir(parents=True, exist_ok=True)
    update_log(args.root).to_csv(args.output / 'update_log.csv', index=False)
    summary = dict(mode='online' if args.online else 'offline_replay', run_id=run_id,
                   root=str(args.root.resolve()), created_utc=manifest['created_utc'], items=results,
                   snapshot_integrity_verified=True,
                   all_source_checks_success=all(x['status'] == 'success' for x in results),
                   scope='Source fields and immutable files only; no trading-calendar, historical availability or universe certification')
    (args.output / ('online_run.json' if args.online else 'offline_replay.json')).write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary['all_source_checks_success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
