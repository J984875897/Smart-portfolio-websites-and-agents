"""Read-only reparsing of hash-verified daily USD/HKD raw evidence."""
import json
import hashlib
import pandas as pd
from .snapshots import load_snapshot, read_artifact, digest
from .providers.yahoo import parse_yahoo_chart, validated_timestamp_rows
from .providers.hkma import parse_page


def cached_daily_fx(root, run_id):
    manifest=load_snapshot(root,run_id)
    schema=manifest['schema_version']
    name='HKD=X' if schema==1 else 'HKMA_USDHKD'
    items=[i for i in manifest['items'] if i.get('symbol')==name]
    if len(items)!=1: raise ValueError('FX dataset not uniquely present')
    item=items[0]
    if item['status'] not in {'success','partial'}: raise ValueError('FX source unavailable')
    page_hashes=[]
    if schema==1:
        if not item.get('raw_file'): raise ValueError('missing raw evidence')
        raw=read_artifact(root,run_id,item['raw_file']); payload=json.loads(raw)
        for result in payload.get('chart',{}).get('result') or []:
            for quote in result.get('indicators',{}).get('quote',[]):
                if any(isinstance(v,bool) for v in quote.get('close',[])): raise ValueError('Yahoo boolean close')
        source_rows=validated_timestamp_rows(payload)
        parsed,meta=parse_yahoo_chart(payload)
        expected=dict(symbol='HKD=X',currency='HKD',instrumentType='CURRENCY',exchangeTimezoneName='Europe/London')
        if any(meta.get(k)!=v for k,v in expected.items()): raise ValueError('FX source identity mismatch')
        parsed=parsed.loc[(parsed.date>=manifest['start'])&(parsed.date<manifest['end_exclusive'])]
        table=parsed[['date','close']].rename(columns={'close':'hkd_per_unit'}).copy()
        source_name='Yahoo chart HKD=X (unofficial)'; source_hash=digest(raw)
        table['source_file']=item['raw_file']; table['source_row']=parsed.timestamp_utc.map(source_rows).tolist()
    elif schema==2:
        if item.get('dataset')!='HKMA_USDHKD' or item.get('provider')!='HKMA' or item.get('unit')!='HKD per USD': raise ValueError('HKMA identity mismatch')
        pages=item.get('pages',[])
        if not pages or [p['path'] for p in pages]!=item.get('raw_files'): raise ValueError('missing or reordered raw pages')
        tables=[]; offset=0; previous=''; complete=False
        for number,page in enumerate(pages):
            if complete or page['offset']!=offset or page['status_code']!=200: raise ValueError('invalid HKMA page metadata/status')
            raw=read_artifact(root,run_id,page['path'])
            if digest(raw)!=page['sha256']: raise ValueError('HKMA page hash mismatch')
            payload=json.loads(raw)
            if any(isinstance(r.get('usd'),bool) for r in payload.get('result',{}).get('records',[])): raise ValueError('HKMA boolean USD')
            parsed=parse_page(payload)
            if len(parsed)>manifest['page_size']: raise ValueError('oversized HKMA page')
            if len(parsed) and (parsed.date.min()<manifest['start'] or parsed.date.max()>=manifest['end_exclusive'] or (previous and parsed.date.min()<=previous)): raise ValueError('invalid HKMA page interval')
            if len(parsed): previous=parsed.date.max()
            parsed=parsed.rename(columns={'hkd_per_usd':'hkd_per_unit'})
            parsed['source_file']=page['path']; parsed['source_row']=list(range(1,len(parsed)+1)); parsed['source_hash']=digest(raw)
            tables.append(parsed); page_hashes.append(dict(path=page['path'],sha256=digest(raw),offset=offset))
            offset+=len(parsed); complete=len(parsed)<manifest['page_size']
        if complete!=item.get('pagination_complete') or (item['status']=='success' and not complete): raise ValueError('HKMA pagination completeness mismatch')
        table=pd.concat(tables,ignore_index=True)
        source_hash=hashlib.sha256(json.dumps(page_hashes,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        source_name='HKMA official USD/HKD daily'
    else: raise ValueError('unsupported FX snapshot schema')
    if table.empty: raise ValueError('empty FX raw evidence')
    table['currency']='USD'; table['source_name']=source_name; table['source_sheet']=''
    if 'source_hash' not in table: table['source_hash']=source_hash
    table=table[['date','currency','hkd_per_unit','source_name','source_file','source_sheet','source_row','source_hash']].reset_index(drop=True)
    table.attrs.update(source_name=source_name,source_hash=source_hash,source_status=item['status'],manifest=manifest,run_id=run_id,unit='HKD per USD',available_at='',historical_eligible=False,page_hashes=page_hashes,download_started_at=manifest['created_utc'])
    return table
