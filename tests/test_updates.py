"""S04 immutable download snapshots, entirely offline."""
import copy
import json
from pathlib import Path
import pandas as pd
import pytest
from portfolio.data.providers.base import RawResponse
from portfolio.data.providers.yahoo import CATALOG, parse_yahoo_chart
from portfolio.data.updates import run_update, validate_plan
from portfolio.data.snapshots import list_runs, load_snapshot, read_artifact, update_log

@pytest.fixture
def chart():
    payload=json.loads((Path(__file__).parent/'fixtures/source_responses/yahoo_chart.json').read_bytes())
    payload['chart']['result'][0]['meta']['symbol']='SPY'
    return payload

def run(root,payload,**kwargs):
    return run_update(root,['SPY'],'2025-01-01','2025-02-01',fetch=lambda *a:RawResponse(json.dumps(payload).encode(),200),**kwargs)

def test_capture_completion_and_legacy(tmp_path, chart):
    from datetime import datetime, timezone
    received=[]
    def fetch(*args):
        received.append(datetime.now(timezone.utc))
        return RawResponse(json.dumps(chart).encode(),200)
    rid=run_update(tmp_path,['SPY'],'2025-01-01','2025-02-01',fetch=fetch)
    m=load_snapshot(tmp_path,rid)
    assert datetime.fromisoformat(m['completed_utc']) >= received[0] >= datetime.fromisoformat(m['created_utc'])
    path=tmp_path/'runs'/rid/'snapshot_manifest.json'
    for invalid in ['bad','2025-01-01T00:00:00','2000-01-01T00:00:00+00:00']:
        broken={**m,'completed_utc':invalid}
        path.write_text(json.dumps(broken))
        with pytest.raises(ValueError): load_snapshot(tmp_path,rid)
    m.pop('completed_utc'); path.write_text(json.dumps(m))
    assert 'completed_utc' not in load_snapshot(tmp_path,rid)

def test_raw_and_revision(tmp_path,chart):
    body=json.dumps(chart).encode()
    calls=[]
    first=run_update(tmp_path,['SPY'],'2025-01-01','2025-02-01',fetch=lambda *a:(calls.append(a) or RawResponse(body,200)))
    manifest=load_snapshot(tmp_path,first); item=manifest['items'][0]
    assert len(calls)==1 and item['status']=='success'
    assert read_artifact(tmp_path,first,item['raw_file'])==body
    imported=pd.read_csv(__import__('io').BytesIO(read_artifact(tmp_path,first,item['import_file'])))
    assert imported.value.tolist()==[99,99,100]
    assert imported.tool_type.unique().tolist()==['ETF']
    chart['chart']['result'][0]['indicators']['adjclose'][0]['adjclose'][0]=98
    second=run(tmp_path,chart)
    assert second!=first and list_runs(tmp_path)==[second,first]
    assert read_artifact(tmp_path,first,item['raw_file'])==body
    assert len(update_log(tmp_path))==2

def test_extracted_parser(chart):
    table,meta=parse_yahoo_chart(chart)
    assert table.date.tolist()==['2025-01-02','2025-01-03','2025-01-06']
    assert table.adj_close.tolist()==[99,99,100]
    assert table.stock_splits.tolist()==[0,0,4]
    assert len(CATALOG)==7

@pytest.mark.parametrize('mode,status,reason',[('format','unavailable','parse_error'),('identity','unavailable','currency_or_instrument_mismatch'),('http','unavailable','rate_limited'),('timeout','unavailable','timeout'),('missing','partial','missing_invalid_prices_or_months')])
def test_failures(tmp_path,chart,mode,status,reason):
    if mode=='identity': chart['chart']['result'][0]['meta']['symbol']='OTHER'
    if mode=='missing': chart['chart']['result'][0]['indicators']['quote'][0]['close'][0]=None
    def fetch(*args):
        if mode=='timeout': raise TimeoutError('SECRET')
        return RawResponse(b'bad SECRET' if mode=='format' else json.dumps(chart).encode(),429 if mode=='http' else 200)
    rid=run_update(tmp_path,['SPY'],'2025-01-01','2025-02-01',fetch=fetch)
    m=load_snapshot(tmp_path,rid); item=m['items'][0]
    assert item['status']==status and item['reason']==reason and item['import_file'] is None
    assert (item['raw_file'] is None)==(mode=='timeout')
    assert 'SECRET' not in json.dumps(m)

@pytest.mark.parametrize('after',[False,True])
def test_cancel(tmp_path,chart,after):
    state={'cancel':not after,'calls':0}
    def fetch(*args):
        state['calls']+=1; state['cancel']=True
        return RawResponse(json.dumps(chart).encode(),200)
    rid=run_update(tmp_path,['SPY','AAPL'],'2025-01-01','2025-02-01',fetch=fetch,cancelled=lambda:state['cancel'])
    items=load_snapshot(tmp_path,rid)['items']
    assert state['calls']==int(after)
    assert all(i['status']=='cancelled' and i['import_file'] is None for i in items)
    assert bool(items[0]['raw_file'])==after

@pytest.mark.parametrize('symbols,start,end,timeout',[([], '2025-01-01','2025-02-01',15),(['NO'],'2025-01-01','2025-02-01',15),(['SPY'],'20250101','2025-02-01',15),(['SPY'],'2025-02-01','2025-01-01',15),(['SPY'],'2025-01-01','2025-02-01',31),(['SPY'],'2025-01-01','2025-02-01',float('nan')),(['SPY','SPY'],'2025-01-01','2025-02-01',15)])
def test_invalid_zero_requests(tmp_path,symbols,start,end,timeout):
    with pytest.raises(ValueError): run_update(tmp_path,symbols,start,end,timeout=timeout,fetch=lambda *a:pytest.fail('network'))

def test_corrupt_and_paths(tmp_path,chart):
    rid=run(tmp_path,chart); m=load_snapshot(tmp_path,rid)
    with pytest.raises(ValueError): read_artifact(tmp_path,rid,'../elsewhere')
    with pytest.raises(ValueError): load_snapshot(tmp_path,'../escape')
    (tmp_path/'runs'/rid/m['items'][0]['raw_file']).write_bytes(b'changed')
    with pytest.raises(ValueError): load_snapshot(tmp_path,rid)
    with pytest.raises(ValueError): update_log(tmp_path)

def test_local_failure_old_unchanged(tmp_path,chart,monkeypatch):
    old=run(tmp_path,chart); original=load_snapshot(tmp_path,old)
    original_write=Path.write_bytes
    def fail(path,data):
        if path.name.startswith('daily_'): raise OSError('disk full')
        return original_write(path,data)
    monkeypatch.setattr(Path,'write_bytes',fail)
    with pytest.raises(OSError): run(tmp_path,chart)
    assert list_runs(tmp_path)==[old] and load_snapshot(tmp_path,old)==original

def test_mixed_outcomes_and_fx(tmp_path,chart):
    calls=[]
    def fetch(symbol,*args):
        calls.append(symbol)
        if symbol=='AAPL': return RawResponse(b'limited',429)
        payload=copy.deepcopy(chart)
        if symbol=='HKD=X': payload['chart']['result'][0]['meta'].update(symbol=symbol,currency='HKD',instrumentType='CURRENCY')
        return RawResponse(json.dumps(payload).encode(),200)
    rid=run_update(tmp_path,['SPY','AAPL','HKD=X'],'2025-01-01','2025-02-01',fetch=fetch)
    items=load_snapshot(tmp_path,rid)['items']
    assert calls==['SPY','AAPL','HKD=X']
    assert [i['status'] for i in items]==['success','unavailable','success']
    assert items[2]['import_file'] is None

@pytest.mark.parametrize('escape',['relative','symlink','unlisted','item_reference'])
def test_manifest_tampering(tmp_path,chart,escape):
    rid=run(tmp_path,chart); folder=tmp_path/'runs'/rid
    manifest=load_snapshot(tmp_path,rid)
    if escape=='relative': manifest['files'][0]['path']='../outside'
    if escape=='symlink':
        file=folder/manifest['files'][0]['path']; body=file.read_bytes(); file.unlink()
        outside=tmp_path/'outside'; outside.write_bytes(body); file.symlink_to(outside)
    if escape=='unlisted': manifest['files'].pop()
    if escape=='item_reference': manifest['items'][0]['raw_file']='not_listed.json'
    (folder/'snapshot_manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError): load_snapshot(tmp_path,rid)

def test_network_free_reads(tmp_path,chart,monkeypatch):
    rid=run(tmp_path,chart)
    import portfolio.data.providers.yahoo as yahoo
    monkeypatch.setattr(yahoo,'fetch_yahoo',lambda *a:pytest.fail('network'))
    manifest=load_snapshot(tmp_path,rid)
    assert list_runs(tmp_path)==[rid]
    assert len(update_log(tmp_path))==1
    assert read_artifact(tmp_path,rid,manifest['items'][0]['daily_file'])

def test_non_transport_errors_propagate(tmp_path):
    def broken(*args): raise OSError('local error')
    with pytest.raises(OSError): run_update(tmp_path,['SPY'],'2025-01-01','2025-02-01',fetch=broken)
    assert list_runs(tmp_path)==[]

def test_reject_runs_directory_symlink(tmp_path,chart):
    outside=tmp_path/'outside'; outside.mkdir()
    (tmp_path/'runs').symlink_to(outside,target_is_directory=True)
    with pytest.raises(ValueError): run(tmp_path,chart)
    assert not list(outside.iterdir())

def test_transport_public_one_request(monkeypatch):
    import sys
    import types
    from curl_cffi import requests
    from portfolio.data.providers.yahoo import fetch_yahoo
    calls=[]
    def get(url,**kwargs):
        calls.append((url,kwargs)); return types.SimpleNamespace(content=b'exact',status_code=429)
    monkeypatch.setitem(sys.modules,'yfinance',types.ModuleType('yfinance'))
    monkeypatch.setattr(requests,'get',get)
    response=fetch_yahoo('HKD=X','2025-01-01','2025-02-01',15)
    assert response==RawResponse(b'exact',429) and len(calls)==1
    url,kwargs=calls[0]
    assert url.endswith('/HKD%3DX') and kwargs['timeout']==15 and kwargs['allow_redirects'] is False
    assert kwargs['params']['period1']==1735689600 and kwargs['params']['period2']==1738368000
    assert kwargs['params']['interval']=='1d' and kwargs['params']['events']=='div,splits,capitalGains'


def test_success_requires_product_import_evidence(tmp_path, chart):
    rid = run(tmp_path, chart)
    manifest = load_snapshot(tmp_path, rid)
    item = manifest['items'][0]
    assert item['status'] == 'success' and item['import_file']
    removed = item['import_file']
    item['import_file'] = None
    manifest['files'] = [f for f in manifest['files'] if f['path'] != removed]
    (tmp_path/'runs'/rid/'snapshot_manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        load_snapshot(tmp_path, rid)


def test_runtime_provenance_and_legacy_schema(tmp_path, chart):
    import platform
    from importlib.metadata import version
    rid = run(tmp_path, chart)
    manifest = load_snapshot(tmp_path, rid)
    assert manifest['provider_endpoint_version'] == 'v8'
    assert manifest['adapter_version'] == 'yahoo-chart-v1'
    assert manifest['client_versions'] == {'python': platform.python_version(), **{name: version(name) for name in ('yfinance', 'curl_cffi', 'pandas')}}
    for key in ('provider_endpoint_version', 'adapter_version', 'client_versions'):
        manifest.pop(key)
    (tmp_path/'runs'/rid/'snapshot_manifest.json').write_text(json.dumps(manifest))
    assert load_snapshot(tmp_path, rid) == manifest
