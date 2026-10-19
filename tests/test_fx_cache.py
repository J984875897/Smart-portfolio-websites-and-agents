import importlib.util
import json
import pandas as pd
import pytest
from portfolio.data.providers.base import RawResponse
from portfolio.data.updates import run_update
from portfolio.data.reference_updates import run_reference_update
from portfolio.data.snapshots import MANIFEST


def cached(root,run):
    assert importlib.util.find_spec('portfolio.data.fx_cache'), 'daily FX cache reader missing'
    from portfolio.data.fx_cache import cached_daily_fx
    return cached_daily_fx(root,run)


def yahoo(value=7.9,currency='HKD'):
    return json.dumps({'chart':{'error':None,'result':[{'meta':{'symbol':'HKD=X','currency':currency,'instrumentType':'CURRENCY','exchangeTimezoneName':'Europe/London'},'timestamp':[int(pd.Timestamp(d,tz='Europe/London').timestamp()) for d in ['2024-12-31','2025-01-31']], 'indicators':{'quote':[{**{k:[7.8,value] for k in ['open','high','low','close']},'volume':[0,0]}],'adjclose':[{'adjclose':[7.8,7.9]}]}}]}}).encode()


@pytest.mark.parametrize('fault',['none','boolean','identity','hash','partial','unavailable'])
def test_yahoo_raw_readonly(tmp_path,fault):
    raw=yahoo(True if fault=='boolean' else 7.9,'USD' if fault=='identity' else 'HKD')
    run=run_update(tmp_path,['HKD=X'],'2024-12-01','2025-02-01',fetch=lambda *a:RawResponse(raw,200))
    folder=tmp_path/'runs'/run; path=folder/MANIFEST; manifest=json.loads(path.read_text())
    if fault=='hash': (folder/manifest['items'][0]['raw_file']).write_bytes(b'bad')
    if fault in {'partial','unavailable'}:
        manifest['items'][0]['status']=fault
        path.write_text(json.dumps(manifest))
    before={p.name:p.read_bytes() for p in folder.iterdir()}
    if fault in {'boolean','identity','hash','unavailable'}:
        with pytest.raises(ValueError): cached(tmp_path,run)
    else:
        frame=cached(tmp_path,run)
        assert frame.hkd_per_unit.tolist()==[7.8,7.9]
        assert frame.attrs['source_status']==('partial' if fault=='partial' else 'success')
        assert frame.attrs['available_at']=='' and not frame.attrs['historical_eligible']
    assert before=={p.name:p.read_bytes() for p in folder.iterdir()}


def page(rows): return json.dumps({'header':{'success':True},'result':{'records':[{'end_of_day':d,'usd':v} for d,v in rows]}}).encode()


@pytest.mark.parametrize('fault',['none','boolean','overlap','offset','complete','http','partial'])
def test_hkma_pages(tmp_path,fault):
    pages=[page([('2024-12-31',7.8)]),page([('2025-01-31',True if fault=='boolean' else 7.9)]),page([])]
    if fault=='overlap': pages[1]=page([('2024-12-31',7.9)])
    def fetch(*args,offset=0,**kwargs): return RawResponse(pages[offset],500 if fault=='http' and offset==1 else 200)
    run=run_reference_update(tmp_path,['HKMA_USDHKD'],'2024-12-01','2025-02-01',page_size=1,max_pages=2 if fault=='partial' else 3,fetch=fetch)
    folder=tmp_path/'runs'/run; path=folder/MANIFEST; manifest=json.loads(path.read_text())
    if fault=='offset': manifest['items'][0]['pages'][1]['offset']=0
    if fault=='complete': manifest['items'][0]['pagination_complete']=False
    path.write_text(json.dumps(manifest)); before={p.name:p.read_bytes() for p in folder.iterdir()}
    if fault not in {'none','partial'}:
        with pytest.raises(ValueError): cached(tmp_path,run)
    else:
        frame=cached(tmp_path,run)
        assert frame.hkd_per_unit.tolist()==[7.8,7.9]
        assert len(frame.attrs['page_hashes'])==(2 if fault=='partial' else 3)
        assert frame.attrs['source_status']==('partial' if fault=='partial' else 'success')
    assert before=={p.name:p.read_bytes() for p in folder.iterdir()}


@pytest.mark.parametrize('stamp', [None, True, float('nan'), float('inf'), 'NaT', 'bad', 10**400])
def test_yahoo_unknown_timestamp_rejected_before_filter(tmp_path, monkeypatch, stamp):
    from portfolio.data import fx_cache
    payload = json.loads(yahoo())
    record = payload['chart']['result'][0]
    record['timestamp'].append(stamp)
    for values in record['indicators']['quote'][0].values(): values.append(8.0)
    record['indicators']['adjclose'][0]['adjclose'].append(8.0)
    raw = json.dumps(payload).encode()
    # A verified upstream snapshot may report success despite an unlocatable row.
    manifest = dict(schema_version=1, start='2024-12-01', end_exclusive='2025-02-01', created_utc='', items=[dict(symbol='HKD=X', status='success', raw_file='fx.json')])
    monkeypatch.setattr(fx_cache, 'load_snapshot', lambda *a: manifest)
    monkeypatch.setattr(fx_cache, 'read_artifact', lambda *a: raw)
    with pytest.raises(ValueError): cached(tmp_path, 'run')


def test_yahoo_original_row_ordinals_survive_sort(tmp_path):
    payload = json.loads(yahoo())
    record = payload['chart']['result'][0]
    record['timestamp'].reverse()
    for values in record['indicators']['quote'][0].values(): values.reverse()
    record['indicators']['adjclose'][0]['adjclose'].reverse()
    raw = json.dumps(payload).encode()
    run = run_update(tmp_path, ['HKD=X'], '2024-12-01', '2025-02-01', fetch=lambda *a: RawResponse(raw, 200))
    folder = tmp_path / 'runs' / run
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    frame = cached(tmp_path, run)
    assert frame.date.tolist() == ['2024-12-31', '2025-01-31']
    assert frame.hkd_per_unit.tolist() == [7.8, 7.9]
    assert frame.source_row.tolist() == [2, 1]
    from portfolio.data.daily_hkd import _endpoints
    _, endpoints, _ = _endpoints(frame, frame.date.tolist(), 7)
    assert endpoints.source_row.tolist() == [2, 1]
    assert before == {p.name: p.read_bytes() for p in folder.iterdir()}
