"""Explicit CSV/XLSX mapping, identity resolution and immutable preview workflow."""
from pathlib import Path
from io import BytesIO, StringIO
import csv
from datetime import datetime, timezone
from dataclasses import asdict
import copy
import hashlib
import pandas as pd
from .contracts import DataBundle, ImportConfig, ImportPreview, TABLE_COLUMNS
from .quality import validate_row

IDENTITY=['exchange','ticker','share_class','currency']
KEY=['asset_id','date','value_kind','frequency','currency']


def read_file(data: bytes | str | Path, *, filename: str | None=None, sheet_name: str | int=0) -> pd.DataFrame:
    if isinstance(data,(str,Path)):
        path=Path(data); filename=filename or path.name; data=path.read_bytes()
    if not filename: raise ValueError('filename is required for bytes')
    suffix=Path(filename).suffix.lower()
    if suffix=='.csv':
        reader=csv.reader(StringIO(data.decode('utf-8-sig'),newline=''))
        header=next(reader,[])
        if not pd.Index(header).is_unique: raise ValueError('Duplicate column names: headers must be unique before mapping')
        records=[]; source_rows=[]
        while True:
            start_line=reader.line_num+1
            try: record=next(reader)
            except StopIteration: break
            if not record: continue
            if len(record)!=len(header): raise ValueError('CSV records must match the header column count')
            records.append(record); source_rows.append(start_line)
        frame=pd.DataFrame(records,columns=header)
        frame.attrs['source_rows']=source_rows
    elif suffix=='.xlsx':
        workbook=pd.ExcelFile(BytesIO(data),engine='openpyxl')
        sheet_name=workbook.sheet_names[sheet_name] if isinstance(sheet_name,int) else sheet_name
        header_frame=pd.read_excel(workbook,header=None,nrows=1,sheet_name=sheet_name)
        header=header_frame.iloc[0].tolist() if not header_frame.empty else []
        if not pd.Index(header).is_unique: raise ValueError('Duplicate column names: headers must be unique before mapping')
        from datetime import date, time
        native=pd.read_excel(workbook,dtype=object,keep_default_na=False,sheet_name=sheet_name)
        def excel_text(value):
            if isinstance(value,datetime) and value.time()==time(): return value.strftime('%Y-%m-%d')
            if isinstance(value,date) and not isinstance(value,datetime): return value.strftime('%Y-%m-%d')
            return str(value)
        frame=native.map(excel_text)
        frame.attrs['source_sheet']=sheet_name
    else: raise ValueError('Only CSV and XLSX local imports are supported')
    frame.attrs.update(source_file=filename,raw_bytes=data)
    return frame


def preview_import(data: pd.DataFrame | bytes | str | Path, config: ImportConfig, existing: DataBundle | None=None, *, filename: str | None=None) -> ImportPreview:
    raw=data.copy(deep=True) if isinstance(data,pd.DataFrame) else read_file(data,filename=filename,sheet_name=config.sheet_name)
    if not raw.columns.is_unique: raise ValueError('Duplicate column names: headers must be unique before mapping')
    filename=filename or raw.attrs.get('source_file','dataframe.csv')
    payload=raw.attrs.get('raw_bytes',raw.to_csv(index=False).encode())
    digest=hashlib.sha256(payload).hexdigest(); existing=existing or DataBundle()
    rows=[]; findings=[]
    aliases={tuple(r[x] for x in ['source_name',*IDENTITY]):r['asset_id'] for r in existing.aliases.to_dict('records')}
    aliases.update(config.alias_mappings)
    assets={r['asset_id']:r for r in existing.assets.to_dict('records')}
    def issue(row,code,message,severity='blocked'):
        findings.append({**{x:row[x] for x in ['source_file','source_sheet','source_row','source_hash','asset_id']},'code':code,'severity':severity,'message':message})
        if severity=='blocked': row['status']='blocked'
        elif row['status'] in {'valid','duplicate'}: row['status']='review'
    def scalar_text(value):
        return '' if value is None or pd.isna(value) else str(value).strip()
    source_rows=raw.attrs.get('source_rows',range(2,len(raw)+2))
    for index,source in zip(source_rows,raw.to_dict('records')):
        row={field:scalar_text(source.get(config.mapping.get(field),'')) for field in set(TABLE_COLUMNS['assets']+['date','value'])}
        for field,value in config.defaults.items():
            if field=='market': field='exchange'
            if field in row and not row[field]: row[field]=str(value).strip()
        if not row['exchange'] and config.mapping.get('market'): row['exchange']=scalar_text(source.get(config.mapping['market'],''))
        row.update(source_file=filename,source_sheet=raw.attrs.get('source_sheet',''),source_row=index,source_hash=digest,source_name=config.source_name,value_kind=config.value_kind,status='valid',is_duplicate=False)
        alias=(config.source_name,*(row[x] for x in IDENTITY))
        complete_listing=all(row[x] for x in ['exchange','ticker','currency'])
        explicit=row['asset_id']; mapped=aliases.get(alias) if complete_listing else None
        matches=[a for a in assets.values() if all(a[x]==row[x] for x in IDENTITY)] if complete_listing else []
        if mapped:
            if mapped not in assets: issue(row,'manual_identity','Alias target does not exist in existing bundle')
            if explicit and explicit!=mapped: issue(row,'identity_conflict','Explicit asset_id conflicts with source alias')
            row['asset_id']=mapped
        elif explicit and matches and all(a['asset_id']!=explicit for a in matches):
            issue(row,'identity_conflict','Exact listing identity already belongs to another asset_id')
        elif not explicit:
            if not row['ticker'] or not row['exchange'] or not row['currency']:
                issue(row,'manual_identity','Stable identity or explicit source alias is required')
            elif len(matches)==1: row['asset_id']=matches[0]['asset_id']
            elif any(a['ticker']==row['ticker'] for a in assets.values()): issue(row,'manual_identity','Ticker identity differs; explicit mapping required')
            else: row['asset_id']='asset_'+hashlib.sha256('|'.join(row[x] for x in IDENTITY).encode()).hexdigest()[:20]
        old=assets.get(row['asset_id'])
        if old and (any(old[x]!=row[x] for x in ['exchange','currency','share_class']) or (old['ticker']!=row['ticker'] and not mapped)): issue(row,'identity_conflict','Exchange/currency/share class/ticker mismatch requires alias mapping')
        overrides=config.classification_overrides.get(row['asset_id'],{})
        row['_original_tool_type']=row['tool_type']; row['_original_asset_class']=row['asset_class']
        for field in ['tool_type','asset_class']:
            if field in overrides: row[field]=overrides[field]
            if old and old[field]!=row[field] and field not in overrides: issue(row,'metadata_conflict',f'{field} differs; explicit classification override required')
        if old and old['frequency']!=row['frequency']: issue(row,'metadata_conflict','frequency differs from existing asset')
        for code,severity,message in validate_row(row,config): issue(row,code,message,severity)
        rows.append(row)
        if row['status']!='blocked' and not old: assets[row['asset_id']]={x:row[x] for x in TABLE_COLUMNS['assets']}
    identity_groups={}
    for row in rows:
        if row['ticker'] and row['exchange'] and row['currency']: identity_groups.setdefault(tuple(row[x] for x in IDENTITY),[]).append(row)
    for group in identity_groups.values():
        if len({r['asset_id'] for r in group})>1:
            for row in group: issue(row,'identity_conflict','Same listing has multiple explicit asset IDs')
    metadata_groups={}
    for row in rows: metadata_groups.setdefault(row['asset_id'],[]).append(row)
    for group in metadata_groups.values():
        listing_keys={(r['exchange'],r['currency'],r['share_class']) for r in group}
        unaliased_tickers={r['ticker'] for r in group if aliases.get((config.source_name,*(r[x] for x in IDENTITY)))!=r['asset_id']}
        if len(listing_keys)>1 or len(unaliased_tickers)>1:
            for row in group: issue(row,'identity_conflict','Within-file listing identity disagreement requires explicit corrections')
        if len({tuple(r[x] for x in ['tool_type','asset_class','frequency']) for r in group})>1:
            for row in group: issue(row,'metadata_conflict','Within-file metadata disagreement requires explicit corrections')
    groups={}
    for row in rows:
        if row['status']!='blocked': groups.setdefault(tuple(row[k] for k in KEY),[]).append(row)
    prior={tuple(r[k] for k in KEY):r['value'] for r in existing.observations.to_dict('records')}
    for key,group in groups.items():
        values={r['value'] for r in group}
        if key in prior: values.add(prior[key])
        if len(values)>1:
            for row in group: issue(row,'conflict','Same observation identity has conflicting values')
        else:
            for n,row in enumerate(group):
                if key in prior or n>0:
                    row['is_duplicate']=True
                    if row['status']=='valid': row['status']='duplicate'
    periods={}
    for row in rows:
        if row['frequency']=='monthly' and len(row['date'])==10:
            key=(row['asset_id'],row['date'][:7],row['value_kind'],row['currency'])
            periods.setdefault(key,[]).append(row)
    for key,group in periods.items():
        prior_dates=set(existing.observations.loc[(existing.observations.asset_id==key[0]) & (existing.observations.frequency=='monthly') & existing.observations.date.astype(str).str.startswith(key[1]),'date'])
        if len({r['date'] for r in group}|prior_dates)>1:
            for row in group: issue(row,'monthly_period_collision','Multiple dates in one monthly period; normalization deferred to S03','review')
    columns=list(dict.fromkeys(TABLE_COLUMNS['assets']+['date','value','source_file','source_sheet','source_row','source_hash','source_name','value_kind','status','is_duplicate','_original_tool_type','_original_asset_class']))
    return ImportPreview(pd.DataFrame(rows,columns=columns),pd.DataFrame(findings,columns=TABLE_COLUMNS['issues']),config,digest,filename,payload)


def commit_import(preview: ImportPreview, existing: DataBundle | None=None, *, allow_review: bool=False) -> DataBundle:
    bundle=copy.deepcopy(existing) if existing is not None else DataBundle()
    def append(name,records):
        if records:
            current=getattr(bundle,name)
            setattr(bundle,name,pd.DataFrame(current.to_dict('records')+records,columns=TABLE_COLUMNS[name]))
    accepted=[]; history=[]; aliases=[]; assets={r['asset_id']:r for r in bundle.assets.to_dict('records')}
    provenance=[]
    for row in preview.rows.to_dict('records'):
        status=row['status']
        if status=='review' and not allow_review: status='review_pending'
        provenance.append({**row,'status':status})
        if status not in {'valid','review','duplicate'}: continue
        old=assets.get(row['asset_id'])
        if old:
            for field in ['tool_type','asset_class']:
                if old[field]!=row[field]:
                    history.append(dict(asset_id=row['asset_id'],field=field,old_value=old[field],new_value=row[field],source_file=row['source_file'],source_sheet=row['source_sheet'],source_row=row['source_row'],timestamp=datetime.now(timezone.utc).isoformat()))
                    old[field]=row[field]
        else:
            assets[row['asset_id']]={x:row[x] for x in TABLE_COLUMNS['assets']}
            for field in ['tool_type','asset_class']:
                original=row.get('_original_'+field,row[field])
                if original!=row[field]: history.append(dict(asset_id=row['asset_id'],field=field,old_value=original,new_value=row[field],source_file=row['source_file'],source_sheet=row['source_sheet'],source_row=row['source_row'],timestamp=datetime.now(timezone.utc).isoformat()))
        if not row['is_duplicate']: accepted.append({x:row[x] for x in TABLE_COLUMNS['observations']})
        if all(row[x] for x in ['exchange','ticker','currency']):
            aliases.append({x:row[x] for x in TABLE_COLUMNS['aliases']})
    bundle.assets=pd.DataFrame(list(assets.values()),columns=TABLE_COLUMNS['assets'])
    append('observations',accepted); append('provenance',provenance); append('issues',preview.issues.to_dict('records')); append('classification_history',history); append('aliases',aliases)
    bundle.aliases=bundle.aliases.drop_duplicates().reset_index(drop=True)
    bundle.returns=bundle.observations.loc[bundle.observations.value_kind.isin(['total_return','price_return']),TABLE_COLUMNS['returns']].copy()
    cfg=asdict(preview.config); cfg['alias_mappings']=[{'identity':list(k),'asset_id':v} for k,v in preview.config.alias_mappings.items()]
    bundle.configs.append({'source_file':preview.source_file,'source_hash':preview.source_hash,'config':cfg})
    if preview.raw_bytes is not None: bundle.raw_sources[preview.source_hash]=preview.raw_bytes
    return bundle
