"""Immutable run publication and fully verified, network-free reads."""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
import pandas as pd

RUN_PATTERN = re.compile(r'\d{8}T\d{12}Z-[0-9a-f]{32}')
MANIFEST = 'snapshot_manifest.json'


def digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _folder(root: Path, run_id: str) -> Path:
    if not isinstance(run_id,str) or not RUN_PATTERN.fullmatch(run_id):
        raise ValueError('invalid run_id')
    runs_path=Path(root)/'runs'
    if runs_path.is_symlink(): raise ValueError('invalid runs directory')
    runs=runs_path.resolve()
    target=runs/run_id
    if target.is_symlink() or not target.resolve().is_relative_to(runs):
        raise ValueError('invalid run directory')
    return target


def list_runs(root: Path) -> list[str]:
    runs=Path(root)/'runs'
    if runs.is_symlink(): raise ValueError('invalid runs directory')
    if not runs.exists(): return []
    return sorted((p.name for p in runs.iterdir() if RUN_PATTERN.fullmatch(p.name) and p.is_dir() and not p.is_symlink() and (p/MANIFEST).is_file()),reverse=True)


def _artifact(folder: Path, name: str) -> Path:
    if not isinstance(name,str) or not name or Path(name).name!=name or name in {'.','..',MANIFEST}:
        raise ValueError('invalid artifact path')
    target=folder/name
    if target.is_symlink() or not target.resolve().is_relative_to(folder.resolve()):
        raise ValueError('artifact path escapes snapshot')
    return target


def load_snapshot(root: Path, run_id: str) -> dict:
    folder=_folder(root,run_id)
    if (folder/MANIFEST).is_symlink(): raise ValueError('invalid manifest path')
    try:
        manifest=json.loads((folder/MANIFEST).read_bytes())
        _validate_completion(manifest)
        if manifest.get('schema_version')==2: return _load_reference(folder,manifest,run_id)
        if manifest['schema_version']!=1 or manifest['run_id']!=run_id or manifest['provider']!='Yahoo chart':
            raise ValueError('unsupported snapshot')
        from .updates import validate_plan
        items=manifest['items']
        validate_plan([i['symbol'] for i in items],manifest['start'],manifest['end_exclusive'],manifest['timeout'])
        if not isinstance(manifest['created_utc'],str): raise ValueError('invalid created time')
        entries=_verified_entries(folder,manifest['files'])
        referenced=set()
        for item in items:
            if item['status'] not in {'success','partial','unavailable','cancelled'} or not isinstance(item['reason'],str) or not isinstance(item['rows'],int) or item['rows']<0:
                raise ValueError('invalid item')
            for key in ('raw_file','daily_file','import_file'):
                name=item[key]
                if name is not None:
                    if name not in entries: raise ValueError('unlisted artifact')
                    referenced.add(name)
            if item['raw_file'] is not None:
                if item['raw_sha256']!=entries[item['raw_file']]['sha256']: raise ValueError('raw hash mismatch')
            elif item['raw_sha256'] is not None: raise ValueError('raw hash without raw')
            if item['status']=='success' and (not item['raw_file'] or not item['daily_file']): raise ValueError('success missing evidence')
            if item['status']=='success' and item['symbol']!='HKD=X' and not item['import_file']: raise ValueError('success missing import evidence')
            if item['import_file'] and (item['status']!='success' or item['symbol']=='HKD=X'): raise ValueError('invalid import')
        if referenced!=set(entries): raise ValueError('unreferenced artifact')
        return manifest
    except (KeyError,TypeError,UnicodeError,json.JSONDecodeError) as error:
        raise ValueError('invalid snapshot manifest') from error


def read_artifact(root: Path, run_id: str, filename: str) -> bytes:
    manifest=load_snapshot(root,run_id)
    if filename not in {f['path'] for f in manifest['files']}: raise ValueError('unlisted artifact')
    return _artifact(_folder(root,run_id),filename).read_bytes()


def _validate_completion(manifest):
    """Legacy manifests remain readable; new capture evidence must be coherent."""
    if 'completed_utc' not in manifest: return
    from datetime import datetime
    _validate_utc_timestamp(manifest['created_utc'])
    _validate_utc_timestamp(manifest['completed_utc'])
    if datetime.fromisoformat(manifest['completed_utc']) < datetime.fromisoformat(manifest['created_utc']):
        raise ValueError('capture completed before download started')


def update_log(root: Path) -> pd.DataFrame:
    columns=['run_id','created_utc','symbol','start','end_exclusive','status','reason','rows','cache_status']
    rows=[]
    for run_id in list_runs(root):
        manifest=load_snapshot(root,run_id)
        for item in manifest['items']:
            rows.append({**{k:manifest[k] for k in ('run_id','created_utc','start','end_exclusive')},**{k:item[k] for k in ('symbol','status','reason','rows')},'cache_status':'available' if item['status']=='success' else 'unavailable'})
    return pd.DataFrame(rows,columns=columns)


def _load_reference(folder,manifest,run_id):
    from datetime import date, datetime
    from .reference_updates import REFERENCE_CATALOG, validate_reference_plan
    if manifest['run_id'] != run_id or manifest['provider'] != 'Reference sources':
        raise ValueError('unsupported snapshot')
    items=manifest['items']
    validate_reference_plan([i['dataset'] for i in items],manifest['start'],manifest['end_exclusive'],manifest['timeout'],manifest['page_size'],manifest['max_pages'])
    _validate_utc_timestamp(manifest['created_utc'])
    if not isinstance(manifest['adapter_version'],str) or not manifest['adapter_version'] or not isinstance(manifest['client_versions'],dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in manifest['client_versions'].items()): raise ValueError('invalid versions')
    entries=_verified_entries(folder,manifest['files'])
    referenced=set()
    reasons={'tls_error','not_requested','cancelled','timeout','transport_error','rate_limited','http_error','parse_error','page_limit','empty_data','complete_requested_months','missing_or_invalid_values_or_months'}
    for item in items:
        dataset=item['dataset']
        if item['symbol']!=dataset or any(item[k]!=v for k,v in REFERENCE_CATALOG[dataset].items()): raise ValueError('invalid identity')
        if 'import_file' in item or item['status'] not in {'success','partial','unavailable','cancelled'} or item['reason'] not in reasons or isinstance(item['rows'],bool) or not isinstance(item['rows'],int) or item['rows']<0: raise ValueError('invalid reference item')
        if not isinstance(item['raw_files'],list) or len(set(item['raw_files']))!=len(item['raw_files']): raise ValueError('invalid raw files')
        for name in [*item['raw_files'],item['source_file'],item['table_file']]:
            if name is not None:
                if name not in entries: raise ValueError('unlisted artifact')
                if name in referenced: raise ValueError('duplicate reference')
                referenced.add(name)
        if not isinstance(item['pagination_complete'],bool) or not isinstance(item['missing_months'],list) or len(set(item['missing_months']))!=len(item['missing_months']): raise ValueError('invalid coverage')
        for month in item['missing_months']:
            if not isinstance(month,str) or not re.fullmatch(r'\d{4}-\d{2}',month): raise ValueError('invalid month')
            day=date.fromisoformat(month+'-01').isoformat()
            if not manifest['start']<=day<manifest['end_exclusive']: raise ValueError('month outside plan')
        for key in ('first_date','last_date'):
            day=item[key]
            if day is not None and (date.fromisoformat(day).isoformat()!=day or not manifest['start']<=day<manifest['end_exclusive']): raise ValueError('invalid observation date')
        if item['rows'] and (not item['first_date'] or not item['last_date'] or item['first_date']>item['last_date'] or not item['table_file']): raise ValueError('missing table metadata')
        if not item['rows'] and (item['first_date'] is not None or item['last_date'] is not None or item['table_file'] is not None): raise ValueError('unexpected table metadata')
        if item['status']=='success' and (not item['raw_files'] or not item['table_file'] or not item['pagination_complete'] or item['missing_months'] or (dataset!='HKMA_USDHKD' and not item['source_file'])): raise ValueError('success missing evidence')
        if not isinstance(item['pages'],list) or len(item['pages'])!=len(item['raw_files']): raise ValueError('invalid pages')
        for page,name in zip(item['pages'],item['raw_files']):
            if page['path']!=name or page['sha256']!=entries[name]['sha256'] or isinstance(page['offset'],bool) or not isinstance(page['offset'],int) or page['offset']<0 or isinstance(page['status_code'],bool) or not isinstance(page['status_code'],int) or not 100<=page['status_code']<=599: raise ValueError('invalid page')
            _validate_utc_timestamp(page['retrieved_utc'])
        expected_scope = 'observation_months_only' if dataset == 'HKMA_USDHKD' else 'requested_monthly_factors'
        if item['quality_scope'] != expected_scope:
            raise ValueError('invalid quality scope')
    if referenced!=set(entries): raise ValueError('unreferenced artifact')
    actual={p.name for p in folder.iterdir() if p.name!=MANIFEST}
    if actual!=set(entries): raise ValueError('unlisted artifact on disk')
    return manifest


def _verified_entries(folder,files):
    entries={}
    for entry in files:
        name=entry['path']
        if name in entries or isinstance(entry['bytes'],bool) or not isinstance(entry['bytes'],int) or entry['bytes']<0 or not isinstance(entry['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',entry['sha256']): raise ValueError('invalid artifact')
        body=_artifact(folder,name).read_bytes()
        if digest(body)!=entry['sha256'] or len(body)!=entry['bytes']: raise ValueError('snapshot hash/size mismatch')
        entries[name]=entry
    return entries


def _validate_utc_timestamp(value):
    from datetime import datetime, timedelta
    if not isinstance(value, str):
        raise ValueError('invalid UTC timestamp')
    timestamp = datetime.fromisoformat(value)
    if timestamp.tzinfo is None or timestamp.utcoffset() != timedelta(0):
        raise ValueError('timestamp must have explicit UTC offset')
