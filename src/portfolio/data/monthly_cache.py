"""Read and reparse immutable Yahoo evidence, without a network or write path."""
import json
from .snapshots import load_snapshot, read_artifact, digest
from .providers.yahoo import CATALOG, parse_yahoo_chart, validated_timestamp_rows
from .daily_monthly import aggregate_daily_prices
from .trading_calendar import TIMEZONES


def cached_monthly_prices(root, run_id, symbol, *, start_month, end_month, confirmed=False, as_of=None):
    manifest = load_snapshot(root, run_id)
    if manifest['schema_version'] != 1 or symbol not in CATALOG or symbol == 'HKD=X': raise ValueError('not a Yahoo price snapshot')
    items = [i for i in manifest['items'] if i['symbol']==symbol]
    if len(items)!=1: raise ValueError('symbol not in snapshot')
    item = items[0]
    if item['status'] not in {'success','partial'} or not item['raw_file']: raise ValueError('source unavailable or lacks raw evidence')
    raw = read_artifact(root, run_id, item['raw_file'])
    payload = json.loads(raw)
    for source in payload.get('chart', {}).get('result') or []:
        for adjusted in source.get('indicators', {}).get('adjclose', []):
            if any(isinstance(value, bool) for value in adjusted.get('adjclose', [])):
                raise ValueError('Yahoo boolean adjusted price')
    validated_timestamp_rows(payload)
    table, meta = parse_yahoo_chart(payload)
    identity = CATALOG[symbol]; market='XHKG' if identity['currency']=='HKD' else 'XNYS'
    if any(meta.get(k)!=v for k,v in dict(symbol=symbol,currency=identity['currency'],instrumentType=identity['provider_type'],exchangeTimezoneName=TIMEZONES[market]).items()):
        raise ValueError('source identity mismatch')
    table = table.loc[(table.date >= manifest['start']) & (table.date < manifest['end_exclusive'])].copy()
    table.attrs.update(source_name='Yahoo chart',source_hash=digest(raw))
    result = aggregate_daily_prices(table, symbol=symbol, start_month=start_month, end_month=end_month, confirmed=confirmed, as_of=as_of)
    result.metadata.update(manifest=manifest,raw_sha256=digest(raw),run_id=run_id,download_started_at=manifest['created_utc'],source_status=item['status'])
    if item['status']!='success':
        result.returns['local_return']=float('nan'); result.returns['status']='blocked'; result.returns['reason']='source_not_success'
    return result
