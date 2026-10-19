"""Explicit, immutable downloads of reference factors and official FX."""
from datetime import date, datetime, timedelta, timezone
from importlib.metadata import version
from pathlib import Path
import json
import csv
import zlib
import math
import platform
import re
import tempfile
import uuid
import zipfile
import numpy as np
import pandas as pd
from .providers.base import RawResponse
from .providers.french import FACTOR_URLS, extract_csv, parse_french
from .providers.hkma import HKMA_URL, parse_page
from .snapshots import MANIFEST, digest
from .updates import _expected_transport

REFERENCE_CATALOG={d:dict(name=d,kind='factor',provider='French',currency='USD',frequency='monthly',region='US' if d.startswith('US') else 'Asia Pacific ex Japan',model=d.rsplit('_',1)[1],unit='decimal') for d in FACTOR_URLS}
REFERENCE_CATALOG['HKMA_USDHKD']=dict(name='Official USD/HKD',kind='fx',provider='HKMA',currency='HKD',frequency='daily',region='Hong Kong',model=None,unit='HKD per USD')


def validate_reference_plan(datasets,start,end,timeout=15,page_size=1000,max_pages=20):
    if isinstance(datasets,str): raise ValueError('invalid selection')
    try: selected=tuple(datasets)
    except TypeError as error: raise ValueError('invalid selection') from error
    if not selected or any(not isinstance(d,str) or d not in REFERENCE_CATALOG for d in selected) or len(set(selected))!=len(selected): raise ValueError('invalid selection')
    for day in (start,end):
        if not isinstance(day,str) or not re.fullmatch(r'\d{4}-\d{2}-01',day): raise ValueError('month start required')
        date.fromisoformat(day)
    if start>=end: raise ValueError('invalid interval')
    if isinstance(timeout,bool) or not isinstance(timeout,(int,float)) or not math.isfinite(timeout) or not 1<=timeout<=30: raise ValueError('invalid timeout')
    for value,limit in ((page_size,1000),(max_pages,100)):
        if isinstance(value,bool) or not isinstance(value,int) or not 1<=value<=limit: raise ValueError('invalid pagination')
    return selected


def fetch_reference(dataset,start,end,timeout,offset=0,page_size=1000):
    validate_reference_plan([dataset],start,end,timeout,page_size)
    import yfinance
    from curl_cffi import requests
    params=dict(choose='end_of_day',**{'from':start,'to':(date.fromisoformat(end)-timedelta(days=1)).isoformat()},fields='end_of_day,usd',sortby='end_of_day',sortorder='asc',pagesize=page_size,offset=offset) if dataset=='HKMA_USDHKD' else {}
    response=requests.get(HKMA_URL if dataset=='HKMA_USDHKD' else FACTOR_URLS[dataset],params=params,timeout=timeout,verify=True,allow_redirects=False)
    return RawResponse(response.content,response.status_code)


def _reference_transport_reason(error):
    """Classify public transport failures without persisting their messages."""
    import yfinance  # Initialize local curl dependencies before importing curl.
    from curl_cffi.requests.exceptions import SSLError
    if isinstance(error, TimeoutError) or getattr(error, 'code', None) == 28:
        return 'timeout'
    if 'timeout' in type(error).__name__.lower():
        return 'timeout'
    # CURLE SSL connect, engine, certificate, cipher, CA and pinning failures.
    tls_codes = {35, 53, 54, 58, 59, 60, 64, 66, 77, 80, 82, 83, 90, 91, 98}
    if isinstance(error, SSLError) or getattr(error, 'code', None) in tls_codes:
        return 'tls_error'
    return 'transport_error'


def _download(dataset,start,end,timeout,page_size,max_pages,fetch,cancelled,save):
    hkma=dataset=='HKMA_USDHKD'
    item=dict(dataset=dataset,symbol=dataset,**REFERENCE_CATALOG[dataset],status='unavailable',reason='not_requested',rows=0,first_date=None,last_date=None,raw_files=[],source_file=None,table_file=None,missing_months=[],pagination_complete=False,pages=[],quality_scope='observation_months_only' if hkma else 'requested_monthly_factors')
    table=None; offset=0
    expected=pd.period_range(start,pd.Timestamp(end)-pd.Timedelta(days=1),freq='M').astype(str).tolist()
    for number in range(max_pages if hkma else 1):
        if cancelled():
            item.update(status='cancelled', reason='cancelled')
            break
        try:
            response=fetch(dataset,start,end,timeout,offset=offset,page_size=page_size) if hkma else fetch(dataset,start,end,timeout)
        except _expected_transport() as error:
            item.update(
                status='partial' if table is not None and len(table) else 'unavailable',
                reason=_reference_transport_reason(error),
            )
            break
        raw=save(response.body,f'{dataset}_raw_{number:03d}'+('.json' if hkma else '.zip'))
        item['raw_files'].append(raw)
        item['pages'].append(dict(offset=offset,status_code=response.status_code,path=raw,sha256=digest(response.body),retrieved_utc=datetime.now(timezone.utc).isoformat()))
        if cancelled():
            item.update(status='cancelled', reason='cancelled')
            break
        if response.status_code!=200:
            item.update(status='partial' if table is not None and len(table) else 'unavailable',reason='rate_limited' if response.status_code==429 else 'http_error'); break
        try:
            if hkma:
                page=parse_page(json.loads(response.body))
                if len(page) > page_size:
                    raise ValueError('oversized page')
                if len(page) and (page.date.min()<start or page.date.max()>=end or (table is not None and len(table) and page.date.min()<=table.date.max())): raise ValueError('invalid page interval')
                table=page if table is None else pd.concat([table,page],ignore_index=True) if len(page) else table
                offset+=len(page)
                item['pagination_complete']=len(page)<page_size
            else:
                source=extract_csv(response.body,FACTOR_URLS[dataset].rsplit('/',1)[1].replace('_CSV.zip','.csv'))
                item['source_file']=save(source,f'{dataset}_source.csv')
                candidate=parse_french(source.decode('utf-8-sig'),require_contiguous=False)
                columns=['month','Mkt-RF','SMB','HML']+(['RMW','CMA'] if dataset.endswith('FF5') else [])+['RF']
                if candidate.columns.tolist()!=columns: raise ValueError('model schema mismatch')
                table=candidate.loc[(candidate.month>=start[:7])&(candidate.month<end[:7])].reset_index(drop=True)
                item['pagination_complete']=True
        except (ValueError,TypeError,KeyError,IndexError,AttributeError,OverflowError,zipfile.BadZipFile,zipfile.LargeZipFile,RuntimeError,csv.Error,zlib.error,EOFError):
            item.update(status='unavailable', reason='parse_error')
            break
        item.update(status='partial',reason='page_limit')
        if item['pagination_complete']:
            if table.empty: item.update(status='unavailable',reason='empty_data')
            else:
                observed=table.date.str[:7] if hkma else table.month
                missing=sorted(set(expected)-set(observed))
                finite=np.isfinite(table.select_dtypes(include='number')).all().all()
                item.update(missing_months=missing,status='success' if not missing and finite else 'partial',reason='complete_requested_months' if not missing and finite else 'missing_or_invalid_values_or_months')
            break
    if table is not None and len(table):
        dates=table.date if hkma else table.month+'-01'
        item.update(rows=len(table),first_date=dates.min(),last_date=dates.max(),table_file=save(table.to_csv(index=False,float_format='%.12f').encode(),f'{dataset}_table.csv'))
        item['missing_months']=sorted(set(expected)-set(dates.str[:7]))
    return item


def run_reference_update(root,datasets,start,end,*,timeout=15,page_size=1000,max_pages=20,fetch=fetch_reference,cancelled=lambda:False):
    selected=validate_reference_plan(datasets,start,end,timeout,page_size,max_pages)
    root=Path(root)
    if (root/'runs').is_symlink(): raise ValueError('invalid runs directory')
    root.mkdir(parents=True,exist_ok=True)
    now=datetime.now(timezone.utc); run_id=now.strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid.uuid4().hex
    manifest=dict(schema_version=2,run_id=run_id,provider='Reference sources',created_utc=now.isoformat(),start=start,end_exclusive=end,timeout=timeout,page_size=page_size,max_pages=max_pages,adapter_version='reference-v2',client_versions={'python':platform.python_version(),**{n:version(n) for n in ('pandas','curl_cffi','yfinance')}},files=[],items=[])
    with tempfile.TemporaryDirectory(prefix='.reference-',dir=root) as temporary:
        stage=Path(temporary)
        def save(body,name):
            (stage/name).write_bytes(body)
            manifest['files'].append(dict(path=name,sha256=digest(body),bytes=len(body)))
            return name
        for dataset in selected: manifest['items'].append(_download(dataset,start,end,timeout,page_size,max_pages,fetch,cancelled,save))
        manifest['completed_utc']=datetime.now(timezone.utc).isoformat()
        (stage/MANIFEST).write_text(json.dumps(manifest,indent=2)+'\n')
        runs=root/'runs'; runs.mkdir(exist_ok=True); stage.rename(runs/run_id)
    return run_id
