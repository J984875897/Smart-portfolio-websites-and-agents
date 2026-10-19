import copy
import importlib
import pandas as pd
import pytest
from test_daily_hkd import connect, fx

CAPTURE='2025-02-02T00:00:00+00:00'

def api():
    assert importlib.util.find_spec('portfolio.data.time_eligibility'), 'time qualification module missing'
    return importlib.import_module('portfolio.data.time_eligibility')

def inputs():
    m=api(); r=connect(fx(),fx_confirmed=True)
    return m,r,m.CaptureEvidence(r.prices.metadata['source_hash'],CAPTURE,'success','price'),m.CaptureEvidence(r.metadata['fx_source_hash'],CAPTURE,'success','fx')

@pytest.mark.parametrize('decision,expected',[(CAPTURE,True),('2025-02-02T08:00:00+08:00',True),('2025-02-01T23:59:59.999999Z',False)])
def test_capture_boundary_and_no_mutation(decision,expected):
    m,r,p,f=inputs(); before=copy.deepcopy(r)
    out=m.qualify_daily_hkd(r,decision_at=decision,price_capture=p,fx_capture=f)
    assert bool(out.rows.iloc[0].historical_observation_eligible)==expected
    assert not out.rows.historical_universe_eligible.any()
    assert not out.rows.historical_eligible.any()
    pd.testing.assert_frame_equal(r.reconciliation,before.reconciliation)
    assert r.metadata==before.metadata

@pytest.mark.parametrize('fault,reason',[
    ('missing_price','price_capture_missing'),('missing_fx','fx_capture_missing'),
    ('hash','price_hash_mismatch'),('fx_hash','fx_hash_mismatch'),
    ('partial','price_source_not_success'),('fx_partial','fx_source_not_success'),
    ('legacy','price_time_evidence_missing'),('bad_time','price_time_evidence_invalid'),
    ('fx_legacy','fx_time_evidence_missing'),('base','base_return_invalid')])
def test_evidence_blockers(fault,reason):
    from dataclasses import replace
    m,r,p,f=inputs()
    if fault=='missing_price': p=None
    if fault=='missing_fx': f=None
    if fault=='hash': p=replace(p,source_hash='0'*64)
    if fault=='fx_hash': f=replace(f,source_hash='0'*64)
    if fault=='partial': p=replace(p,source_status='partial')
    if fault=='fx_partial': f=replace(f,source_status='partial')
    if fault=='legacy': p=replace(p,completed_utc='')
    if fault=='fx_legacy': f=replace(f,completed_utc='')
    if fault=='bad_time': p=replace(p,completed_utc='2025-02-01')
    if fault=='base': r.reconciliation.loc[0,'status']='blocked'
    row=m.qualify_daily_hkd(r,decision_at=CAPTURE,price_capture=p,fx_capture=f).rows.iloc[0]
    assert not row.historical_observation_eligible and reason in row.time_reason

@pytest.mark.parametrize('decision',['bad','2025-02-01','2025-02-01T12:00:00',None,'0001-01-01T00:00:00+14:00','9999-12-31T23:59:59-12:00'])
def test_invalid_decision(decision):
    m,r,p,f=inputs()
    with pytest.raises(ValueError): m.qualify_daily_hkd(r,decision_at=decision,price_capture=p,fx_capture=f)

def test_manual_declaration_never_upgrades():
    m,r,p,f=inputs()
    out=m.qualify_daily_hkd(r,decision_at=CAPTURE,declared_available_at='2025-02-01T00:00:00Z')
    assert out.rows.time_status.tolist()==['declaration_only']
    assert not out.rows.historical_observation_eligible.any()
    with pytest.raises(ValueError): m.qualify_daily_hkd(r,decision_at=CAPTURE,declared_available_at='2025-02-01')

def test_hkd_does_not_require_fx():
    from portfolio.data.daily_monthly import aggregate_daily_prices
    from portfolio.data.daily_hkd_samples import sample_daily_prices
    from portfolio.data.daily_hkd import connect_daily_hkd
    m=api()
    r=connect_daily_hkd(aggregate_daily_prices(sample_daily_prices('2800.HK','2025-01','2025-01'),symbol='2800.HK',start_month='2025-01',end_month='2025-01',confirmed=True))
    p=m.CaptureEvidence(r.prices.metadata['source_hash'],CAPTURE,'success','price')
    assert m.qualify_daily_hkd(r,decision_at=CAPTURE,price_capture=p).rows.historical_observation_eligible.all()

def test_verified_loader_legacy_and_corruption(tmp_path):
    import json
    from test_updates import run
    from pathlib import Path
    m=api()
    payload=json.loads((Path(__file__).parent/'fixtures/source_responses/yahoo_chart.json').read_bytes())
    payload['chart']['result'][0]['meta']['symbol']='SPY'
    rid=run(tmp_path,payload)
    evidence=m.load_price_capture(tmp_path,rid,'SPY')
    assert evidence.completed_utc and evidence.source_status=='success'
    path=tmp_path/'runs'/rid/'snapshot_manifest.json'
    manifest=json.loads(path.read_bytes()); manifest.pop('completed_utc'); path.write_text(json.dumps(manifest))
    assert m.load_price_capture(tmp_path,rid,'SPY').completed_utc==''
    (path.parent/manifest['items'][0]['raw_file']).write_bytes(b'changed')
    with pytest.raises(ValueError): m.load_price_capture(tmp_path,rid,'SPY')

@pytest.mark.parametrize('provider',['yahoo','hkma'])
def test_fresh_snapshots_through_real_pipeline(tmp_path,provider):
    import json
    from portfolio.data.daily_hkd_samples import sample_daily_prices
    from portfolio.data.providers.base import RawResponse
    from portfolio.data.updates import run_update
    from portfolio.data.reference_updates import run_reference_update
    from portfolio.data.monthly_cache import cached_monthly_prices
    from portfolio.data.fx_cache import cached_daily_fx
    from portfolio.data.daily_hkd import connect_daily_hkd
    from test_fx_cache import yahoo, page
    m=api(); table=sample_daily_prices('SPY','2025-01','2025-01')
    values=table.adj_close.tolist()
    body=json.dumps({'chart':{'error':None,'result':[{
        'meta':dict(symbol='SPY',currency='USD',instrumentType='ETF',exchangeTimezoneName='America/New_York'),
        'timestamp':[int(pd.Timestamp(d+'T16:00:00',tz='America/New_York').timestamp()) for d in table.date],
        'indicators':{'quote':[{**{k:values for k in ['open','high','low','close']},'volume':[0]*len(values)}], 'adjclose':[{'adjclose':values}]}
    }]}}).encode()
    price_run=run_update(tmp_path,['SPY'],'2024-12-01','2025-02-01',fetch=lambda *a:RawResponse(body,200))
    if provider=='yahoo':
        fx_run=run_update(tmp_path,['HKD=X'],'2024-12-01','2025-02-01',fetch=lambda *a:RawResponse(yahoo(),200))
    else:
        fx_run=run_reference_update(tmp_path,['HKMA_USDHKD'],'2024-12-01','2025-02-01',fetch=lambda *a,**k:RawResponse(page([('2024-12-31',7.8),('2025-01-31',7.9)]),200))
    prices=cached_monthly_prices(tmp_path,price_run,'SPY',start_month='2025-01',end_month='2025-01',confirmed=True)
    result=connect_daily_hkd(prices,cached_daily_fx(tmp_path,fx_run),fx_confirmed=True)
    p=m.load_price_capture(tmp_path,price_run,'SPY'); f=m.load_fx_capture(tmp_path,fx_run)
    assert p.source_status==f.source_status=='success'
    decision=max(p.completed_utc,f.completed_utc)
    before={file:file.read_bytes() for file in tmp_path.rglob('*') if file.is_file()}
    out=m.qualify_daily_hkd(result,decision_at=decision,price_capture=p,fx_capture=f)
    assert out.rows.historical_observation_eligible.all()
    assert out.rows.iloc[0].time_status=='eligible_from_snapshot'
    assert before=={file:file.read_bytes() for file in before}
