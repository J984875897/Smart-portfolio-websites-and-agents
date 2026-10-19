"""Validated Yahoo plans and independent item updates with atomic publication."""
from __future__ import annotations
from datetime import date, datetime, timezone
import json
import math
import platform
from importlib.metadata import version
from pathlib import Path
import re
import tempfile
import uuid
import pandas as pd
from .providers.yahoo import CATALOG, fetch_yahoo, parse_yahoo_chart, audit_price
from .snapshots import digest, MANIFEST


def validate_plan(symbols, start: str, end: str, timeout: float=15) -> tuple[str,...]:
    if isinstance(symbols,str): raise ValueError('symbols must be a selection')
    try: selected=tuple(symbols)
    except TypeError as error: raise ValueError('invalid symbols') from error
    if not selected or any(not isinstance(s,str) or s not in CATALOG for s in selected) or len(set(selected))!=len(selected):
        raise ValueError('select unique catalog symbols')
    for day in (start,end):
        if not isinstance(day,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',day): raise ValueError('date must be YYYY-MM-DD')
        date.fromisoformat(day)
    if start>=end: raise ValueError('start must precede end')
    if isinstance(timeout,bool) or not isinstance(timeout,(int,float)) or not math.isfinite(timeout) or not 1<=timeout<=30:
        raise ValueError('timeout must be 1–30 seconds')
    return selected


def _transport_reason(error):
    if isinstance(error,TimeoutError) or 'timeout' in type(error).__name__.lower(): return 'timeout'
    # curl_cffi uses a generic RequestsError carrying CURLE_OPERATION_TIMEDOUT.
    if getattr(error,'code',None)==28: return 'timeout'
    return 'transport_error'


def _expected_transport():
    from curl_cffi.requests.exceptions import RequestException
    return (TimeoutError,ConnectionError,RequestException)


def _item(symbol, start, end, timeout, fetch, cancelled, save):
    item=dict(symbol=symbol,status='unavailable',reason='not_requested',rows=0,raw_file=None,daily_file=None,import_file=None,raw_sha256=None)
    if cancelled(): return {**item,'status':'cancelled','reason':'cancelled'}
    try: response=fetch(symbol,start,end,timeout)
    except _expected_transport() as error:
        return {**item,'reason':_transport_reason(error)}
    safe=symbol.replace('=','_')
    item['raw_file']=save(response.body,f'raw_{safe}.json')
    item['raw_sha256']=digest(response.body)
    if cancelled(): return {**item,'status':'cancelled','reason':'cancelled'}
    if response.status_code!=200:
        return {**item,'reason':'rate_limited' if response.status_code==429 else 'http_error'}
    try:
        table,meta=parse_yahoo_chart(json.loads(response.body))
        table=table.loc[(table.date>=start)&(table.date<end)].reset_index(drop=True)
        identity=CATALOG[symbol]
        audit=audit_price(table,meta,identity['currency'],identity['provider_type'],symbol=symbol,start=start,end=end)
    except (ValueError,TypeError,KeyError,IndexError,OverflowError,AttributeError,ZeroDivisionError):
        return {**item,'reason':'parse_error'}
    item.update(audit)
    item['rows']=len(table)
    item['daily_file']=save(table.to_csv(index=False,float_format='%.12f').encode(),f'daily_{safe}.csv')
    if item['status']=='success' and symbol!='HKD=X':
        imported=pd.DataFrame({k:identity[k] for k in ('ticker','name','tool_type','asset_class','exchange','currency')},index=table.index)
        imported['share_class']=''; imported['frequency']='daily'
        imported['date']=table.date; imported['value']=table.adj_close
        item['import_file']=save(imported.to_csv(index=False,float_format='%.12f').encode(),f'import_{safe}.csv')
    return item


def run_update(root: Path, symbols, start: str, end: str, *, timeout: float=15, fetch=fetch_yahoo, cancelled=lambda:False) -> str:
    selected=validate_plan(symbols,start,end,timeout)
    root=Path(root)
    if (root/'runs').is_symlink(): raise ValueError('invalid runs directory')
    root.mkdir(parents=True,exist_ok=True)
    now=datetime.now(timezone.utc)
    run_id=now.strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid.uuid4().hex
    manifest=dict(schema_version=1,run_id=run_id,provider='Yahoo chart',provider_endpoint_version='v8',adapter_version='yahoo-chart-v1',client_versions={'python':platform.python_version(),**{name:version(name) for name in ('yfinance','curl_cffi','pandas')}},created_utc=now.isoformat(),start=start,end_exclusive=end,timeout=timeout,items=[],files=[])
    with tempfile.TemporaryDirectory(prefix='.update-',dir=root) as temporary:
        stage=Path(temporary)
        def save(body,name):
            (stage/name).write_bytes(body)
            manifest['files'].append(dict(path=name,sha256=digest(body),bytes=len(body)))
            return name
        for symbol in selected:
            manifest['items'].append(_item(symbol,start,end,timeout,fetch,cancelled,save))
        manifest['completed_utc']=datetime.now(timezone.utc).isoformat()
        (stage/MANIFEST).write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        runs=root/'runs'; runs.mkdir(exist_ok=True)
        stage.rename(runs/run_id)
    return run_id
