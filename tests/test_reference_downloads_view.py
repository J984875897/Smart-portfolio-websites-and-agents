from datetime import date
from pathlib import Path
import io
import zipfile
import pytest
from streamlit.testing.v1 import AppTest
from portfolio.data.reference_updates import run_reference_update
from portfolio.data.providers.base import RawResponse
from portfolio.data.snapshots import load_snapshot, read_artifact

ROOT = Path(__file__).resolve().parents[1]


def start(monkeypatch, root):
    monkeypatch.setenv('PORTFOLIO_REFERENCE_DOWNLOADS_ROOT', str(root))
    at = AppTest.from_file(str(ROOT/'app/main.py'), default_timeout=15).run()
    at.selectbox(key='workspace_route').set_value('reference_downloads').run()
    assert not at.exception
    return at


def click(at, key):
    at.button(key=key).click().run()
    assert not at.exception


def cache(root, partial=False, failed=False):
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w') as z:
        z.writestr('F-F_Research_Data_Factors.csv', ',Mkt-RF,SMB,HML,RF\n202501,2,3,'+('-99.99' if partial else '4')+',0.4\n202502,1,2,3,0.3')
    rid = run_reference_update(root, ['US_FF3'], '2025-01-01', '2025-03-01', fetch=lambda *a: RawResponse(b'limited',429) if failed else RawResponse(data.getvalue(),200))
    return rid, load_snapshot(root,rid)


def keys(at):
    return {b.key for b in at.get('download_button')}


def test_prepare_cancel_changes_and_navigation_are_offline(monkeypatch,tmp_path):
    import app.views.reference_downloads as view
    monkeypatch.setattr(view,'run_reference_update',lambda *a,**k:pytest.fail('unexpected network'))
    at=start(monkeypatch,tmp_path)
    assert at.date_input(key='ref_end').value == date(2026,1,1)
    click(at,'ref_prepare')
    assert len(at.session_state['ref_plan']['datasets'])==5
    assert any('24' in x.value for x in at.markdown)
    click(at,'ref_cancel')
    assert at.session_state['ref_plan'] is None
    click(at,'ref_prepare')
    at.number_input(key='ref_max_pages').set_value(3).run()
    assert at.session_state['ref_plan'] is None
    at.date_input(key='ref_start_date').set_value(date(2025,1,2)).run()
    click(at,'ref_prepare')
    assert at.error
    at.selectbox(key='workspace_route').set_value('prepare_data').run()
    assert not at.exception


def test_explicit_start_and_open_preserve_active(monkeypatch,tmp_path):
    import app.views.reference_downloads as view
    rid,m=cache(tmp_path)
    calls=[]
    monkeypatch.setattr(view,'run_reference_update',lambda *a,**k:(calls.append(k) or rid))
    at=start(monkeypatch,tmp_path)
    click(at,'ref_open')
    active=at.session_state['ref_active']
    click(at,'ref_prepare'); click(at,'ref_start')
    assert len(calls)==1
    assert at.session_state['ref_active']==active
    assert at.session_state['ref_result']['manifest']==m
    failed,_=cache(tmp_path,failed=True)
    at.run(); at.selectbox(key='ref_run').set_value(failed).run(); click(at,'ref_open')
    assert at.session_state['ref_active']==active
    assert at.session_state['ref_result']['run_id']==failed
    assert {'ref_manifest','ref_table','ref_raw','ref_log','ref_result_manifest'} <= keys(at)
    assert not any('导入' in b.label for b in at.button)


def test_partial_diagnostics_and_corruption(monkeypatch,tmp_path):
    rid,m=cache(tmp_path,partial=True)
    at=start(monkeypatch,tmp_path); click(at,'ref_open')
    assert at.session_state['ref_active'] is None
    assert 'ref_result_diag_table_US_FF3' in keys(at)
    assert any(df.value.isna().any().any() for df in at.dataframe)
    assert read_artifact(tmp_path,rid,m['items'][0]['table_file'])
    (tmp_path/'runs'/rid/m['items'][0]['table_file']).write_bytes(b'corrupt')
    at.run()
    assert not keys(at)
    assert at.error


def test_root_binding_and_manifest_change(monkeypatch,tmp_path):
    rid,m=cache(tmp_path/'a')
    at=start(monkeypatch,tmp_path/'a'); click(at,'ref_open'); click(at,'ref_prepare')
    monkeypatch.setenv('PORTFOLIO_REFERENCE_DOWNLOADS_ROOT',str(tmp_path/'b'))
    at.run()
    assert at.session_state['ref_plan'] is None
    assert 'ref_table' not in keys(at)
    monkeypatch.setenv('PORTFOLIO_REFERENCE_DOWNLOADS_ROOT',str(tmp_path/'a'))
    import json
    p=tmp_path/'a'/'runs'/rid/'snapshot_manifest.json'
    changed=dict(m,created_utc='2026-10-16T00:00:00+00:00')
    p.write_text(json.dumps(changed))
    at.run()
    assert 'ref_manifest' not in keys(at)
    assert at.error


def test_exact_exports_mixed_scope_and_failed_start(monkeypatch,tmp_path):
    import app.views.reference_downloads as view
    from portfolio.data.providers.base import RawResponse
    import json
    good,gm=cache(tmp_path/'seed')
    body=read_artifact(tmp_path/'seed',good,gm['items'][0]['raw_files'][0])
    def fetch(dataset,*a,**k):
        if dataset=='US_FF3': return RawResponse(body,200)
        return RawResponse(json.dumps({'header':{'success':True},'result':{'records':[{'end_of_day':'2025-01-02','usd':7.8}]}}).encode(),200)
    rid=run_reference_update(tmp_path,['US_FF3','HKMA_USDHKD'],'2025-01-01','2025-03-01',fetch=fetch)
    m=load_snapshot(tmp_path,rid)
    recorded={}
    original=view.st.download_button
    def capture(label,data,*args,**kwargs):
        recorded[kwargs['key']]=data
        return original(label,data,*args,**kwargs)
    monkeypatch.setattr(view.st,'download_button',capture)
    at=start(monkeypatch,tmp_path); click(at,'ref_open')
    assert recorded['ref_table']==read_artifact(tmp_path,rid,m['items'][0]['table_file'])
    assert recorded['ref_diag_table_HKMA_USDHKD']==read_artifact(tmp_path,rid,m['items'][1]['table_file'])
    name=at.selectbox(key='ref_raw_file').value
    assert recorded['ref_raw']==read_artifact(tmp_path,rid,name)
    assert any('USD RF' in x.value and '港币' in x.value for x in at.info)
    assert {'数据集','名称','来源','地区','模型','币种','频率','单位'} <= set(at.dataframe[1].value.columns)
    active=at.session_state['ref_active']
    def fail(*a,**k): raise OSError('SECRET exception')
    monkeypatch.setattr(view,'run_reference_update',fail)
    click(at,'ref_prepare'); click(at,'ref_start')
    assert at.session_state['ref_active']==active
    assert 'SECRET' not in str([x.value for x in at.error])
    table=tmp_path/'runs'/rid/m['items'][0]['table_file']
    table.write_bytes(b'corrupt')
    at.run()
    assert not keys(at)


def test_schema_one_friendly_rejection(monkeypatch,tmp_path):
    from portfolio.data.updates import run_update
    run_update(tmp_path,['SPY'],'2025-01-01','2025-02-01',fetch=lambda *a:RawResponse(b'limited',429))
    at=start(monkeypatch,tmp_path); click(at,'ref_open')
    assert at.error
    assert at.session_state['ref_active'] is None
    assert not keys(at)
