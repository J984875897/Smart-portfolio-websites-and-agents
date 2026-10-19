from io import BytesIO
from pathlib import Path
import json
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def start(tmp_path, monkeypatch):
    import socket
    monkeypatch.setattr(socket,'create_connection',lambda *a,**k:pytest.fail('unexpected network'))
    monkeypatch.setenv('PORTFOLIO_IMPORTS_ROOT',str(tmp_path/'imports'))
    at = AppTest.from_file(str(ROOT/'app/main.py'),default_timeout=30).run()
    assert any('03 筛选候选' in option for option in at.selectbox(key='workspace_route').options)
    at.selectbox(key='workspace_route').set_value('screen_candidates').run()
    assert not at.exception
    return at


def compute(at):
    at.button(key='cs_compute').click().run()
    assert not at.exception
    assert at.session_state['cs_result'] is not None
    return at


def downloads(at):
    return [x for x in at.get('download_button') if x.proto.label.startswith('下载筛选')]


def test_boundary_exclusion_and_isolation(tmp_path, monkeypatch):
    at = start(tmp_path,monkeypatch)
    assert at.session_state['cs_result'] is None and not downloads(at)
    original = at.session_state['bundle'].observations.copy(deep=True)
    compute(at)
    r = at.session_state['cs_result']
    assert r.cardinality.n == 100 and r.cardinality.status == 'passed'
    assert len(downloads(at)) == 3
    assert not any('生成组合' == x.label for x in at.button)
    at.multiselect(key='cs_excluded').set_value(['SYNTH_SCREEN_099']).run()
    assert at.session_state['cs_result'] is None and not downloads(at)
    compute(at)
    assert at.session_state['cs_result'].cardinality.n == 99
    assert at.session_state['cs_result'].cardinality.status == 'pool_too_small'
    assert at.session_state['bundle'].observations.equals(original)


def test_display_only_controls_and_export_content(tmp_path,monkeypatch):
    import streamlit
    captured = {}
    original = streamlit.download_button
    def capture(label,data,*args,**kwargs):
        captured[kwargs.get('key')] = data
        return original(label,data,*args,**kwargs)
    monkeypatch.setattr(streamlit,'download_button',capture)
    at = compute(start(tmp_path,monkeypatch))
    token = at.session_state['cs_result'].fingerprint
    at.text_input(key='cs_search').set_value('SYNTH_SCREEN_099').run()
    assert at.session_state['cs_result'].cardinality.n == 100
    assert at.session_state['cs_result'].fingerprint == token
    assert len(next(x.value for x in at.dataframe if '资产标识' in x.value)) == 1
    at.text_input(key='cs_search').set_value('').run()
    at.number_input(key='cs_page').set_value(2).run()
    assert at.session_state['cs_result'].fingerprint == token
    audit = pd.read_csv(BytesIO(captured['cs_export_audit']))
    matrix = pd.read_csv(BytesIO(captured['cs_export_matrix']))
    evidence = json.loads(captured['cs_export_evidence'])
    assert len(audit) == 100 and matrix.shape == (60,101)
    assert audit.status.eq('eligible').all()
    assert evidence['historical_universe_certified'] is False
    assert evidence['cardinality']['n'] == 100


@pytest.mark.parametrize('key,value', [('cs_markets',[]),('cs_tools',[]),('cs_classes',[])])
def test_scope_change_clears_and_empty_pool(tmp_path,monkeypatch,key,value):
    at = compute(start(tmp_path,monkeypatch))
    at.multiselect(key=key).set_value(value).run()
    assert at.session_state['cs_result'] is None and not downloads(at)
    compute(at)
    assert at.session_state['cs_result'].cardinality.n == 0
    assert at.session_state['cs_result'].cardinality.ratio is None


def test_time_error_clears_and_missing_time_sample(tmp_path,monkeypatch):
    at = compute(start(tmp_path,monkeypatch))
    at.text_input(key='cs_decision').set_value('2025-02-01T06:00:00').run()
    assert at.session_state['cs_result'] is None and not downloads(at)
    at.button(key='cs_compute').click().run()
    assert not at.exception and at.error and not downloads(at)
    at.text_input(key='cs_decision').set_value('2025-02-01T06:00:00+08:00').run()
    at.radio(key='cs_source').set_value('SYNTH 缺月与时间案例').run()
    compute(at)
    assert at.session_state['cs_result'].cardinality.n == 2
    at.text_input(key='cs_decision').set_value('2025-01-31T17:00:00+08:00').run()
    assert at.session_state['cs_result'] is None
    compute(at)
    assert at.session_state['cs_result'].cardinality.n == 1


def test_current_empty_and_missing_evidence(tmp_path,monkeypatch):
    from portfolio.universe.samples import sample_candidate_inputs
    at = compute(start(tmp_path,monkeypatch))
    at.radio(key='cs_source').set_value('当前已打开导入版本').run()
    assert at.session_state['cs_result'] is None and not downloads(at)
    assert at.button(key='cs_compute').disabled
    at.session_state['bundle'] = sample_candidate_inputs()[0]
    at.run(); compute(at)
    r = at.session_state['cs_result']
    assert r.cardinality.n == 0
    assert r.audit.reason.str.contains('structure_missing').all()
    assert r.audit.reason.str.contains('missing_timing').all()
    shown = next(x.value for x in at.dataframe if '资产标识' in x.value)
    assert '说明' in list(shown.columns)[:4]
    at.session_state['bundle'].assets.loc[0,'name'] = 'changed'
    at.run()
    assert at.session_state['cs_result'] is None and not downloads(at)


def upload(frame,name):
    file = BytesIO(frame.to_csv(index=False).encode('utf-8-sig')); file.name = name
    return file


def test_uploaded_real_path_stock_toggle_and_content_change(tmp_path,monkeypatch):
    import streamlit
    from portfolio.universe.samples import sample_candidate_inputs
    bundle,fx,timing,structures = sample_candidate_inputs()
    bundle.assets.loc[bundle.assets.asset_id == 'HKD_COMPLETE','tool_type'] = 'stock'
    structures.loc[structures.asset_id == 'HKD_COMPLETE','canonical_tool_type'] = 'stock'
    files = {'cs_fx':upload(fx,'fx.csv'),'cs_timing':upload(timing,'time.csv'),'cs_structures':upload(structures,'structures.csv')}
    monkeypatch.setattr(streamlit,'file_uploader',lambda *a,**kw:next((file for key,file in files.items() if kw['key'].startswith(key+'_upload')),None))
    at = start(tmp_path,monkeypatch)
    at.session_state['bundle'] = bundle
    at.radio(key='cs_source').set_value('当前已打开导入版本').run()
    compute(at)
    assert at.session_state['cs_result'].cardinality.n == 1
    assert 'direct_equity_excluded' in at.session_state['cs_result'].audit.set_index('asset_id').loc['HKD_COMPLETE','reason']
    at.toggle(key='cs_stocks').set_value(True).run()
    assert at.session_state['cs_result'] is None and not downloads(at)
    compute(at)
    assert at.session_state['cs_result'].cardinality.n == 2
    assert at.session_state['cs_result'].evidence['inputs']['timing']['source_file'] == 'time.csv'
    files['cs_timing'] = upload(timing.iloc[:-1],'time.csv')
    at.run()
    assert at.session_state['cs_result'] is None and not downloads(at)
    broken = BytesIO(b'broken'); broken.name = 'broken.xlsx'
    files['cs_timing'] = broken; at.run()
    assert not at.exception and at.error and at.button(key='cs_compute').disabled
    assert at.session_state['cs_result'] is None and not downloads(at)


def test_excel_sheet_and_structure_conflicts(tmp_path,monkeypatch):
    import streamlit
    from portfolio.universe.samples import sample_candidate_inputs
    bundle,fx,timing,structures = sample_candidate_inputs()
    book = BytesIO()
    with pd.ExcelWriter(book,engine='openpyxl') as writer:
        structures.to_excel(writer,sheet_name='完整',index=False)
        structures.iloc[:0].to_excel(writer,sheet_name='空表',index=False)
    book.name = 'structures.xlsx'
    files = {'cs_fx':upload(fx,'fx.csv'),'cs_timing':upload(timing,'time.csv'),'cs_structures':book}
    monkeypatch.setattr(streamlit,'file_uploader',lambda *a,**kw:next((file for key,file in files.items() if kw['key'].startswith(key+'_upload')),None))
    at = start(tmp_path,monkeypatch); at.session_state['bundle'] = bundle
    at.radio(key='cs_source').set_value('当前已打开导入版本').run(); compute(at)
    assert at.session_state['cs_result'].cardinality.n == 2
    at.selectbox(key='cs_structures_sheet').set_value('空表').run()
    assert at.session_state['cs_result'] is None and not downloads(at)
    compute(at)
    assert at.session_state['cs_result'].cardinality.n == 0
    conflict = pd.concat([structures,structures.iloc[[0]]],ignore_index=True)
    conflict.loc[len(conflict)-1,'structure'] = 'inverse'
    files['cs_structures'] = upload(conflict,'conflict.csv'); at.run()
    at.button(key='cs_compute').click().run()
    assert not at.exception and at.error
    assert at.session_state['cs_result'] is None and not downloads(at)


def test_source_switch_never_carries_previous_uploads(tmp_path,monkeypatch):
    import streamlit
    from portfolio.universe.samples import sample_candidate_inputs
    bundle,fx,timing,structures = sample_candidate_inputs()
    files = {}; seen = {}
    def uploader(*args,**kw):
        seen[args[0]] = kw['key']
        return files.get(kw['key'])
    monkeypatch.setattr(streamlit,'file_uploader',uploader)
    at = start(tmp_path,monkeypatch)
    at.radio(key='cs_source').set_value('SYNTH 缺月与时间案例').run()
    at.selectbox(key='cs_evidence_mode').set_value('上传自己的证据').run()
    old = {name:key for name,key in seen.items()}
    files.update({key:upload(frame,name+'.csv') for name,frame in [('月末汇率',fx),('逐月时间证据',timing),('结构资料',structures)]
                  for title,key in old.items() if title.startswith(name)})
    at.run(); compute(at)
    assert at.session_state['cs_result'].cardinality.n == 2
    at.session_state['bundle'] = bundle
    at.radio(key='cs_source').set_value('当前已打开导入版本').run()
    compute(at)
    assert at.session_state['cs_result'].cardinality.n == 0
    assert seen['结构资料（CSV／XLSX）'] != old['结构资料（CSV／XLSX）']


def test_adjusted_price_confirmation_resets_on_new_version(tmp_path,monkeypatch):
    from portfolio.universe.samples import sample_candidate_inputs
    bundle = sample_candidate_inputs()[0]
    bundle.observations.loc[bundle.observations.asset_id == 'HKD_COMPLETE','value_kind'] = 'adjusted_price'
    at = start(tmp_path,monkeypatch)
    at.session_state['bundle'] = bundle; at.session_state['bundle_version'] = 'version-A'
    at.radio(key='cs_source').set_value('当前已打开导入版本').run()
    at.multiselect(key='cs_adjusted').set_value(['HKD_COMPLETE']).run()
    assert at.multiselect(key='cs_adjusted').value == ['HKD_COMPLETE']
    at.session_state['bundle_version'] = 'version-B'; at.run()
    assert not at.exception
    assert at.multiselect(key='cs_adjusted').value == []


def test_k_and_invalid_month_invalidate_previous_result(tmp_path,monkeypatch):
    at = compute(start(tmp_path,monkeypatch))
    at.number_input(key='cs_k').set_value(20).run()
    assert at.session_state['cs_result'] is None and not downloads(at)
    compute(at)
    assert at.session_state['cs_result'].cardinality.k == 20
    at.text_input(key='cs_end').set_value('bad').run()
    assert at.session_state['cs_result'] is None and not downloads(at)
    at.button(key='cs_compute').click().run()
    assert not at.exception and at.error and not downloads(at)


def test_existing_real_bundle_remains_blocked_and_unmodified(tmp_path,monkeypatch):
    import hashlib
    from portfolio.data.contracts import DataBundle
    path = Path(json.loads((ROOT/'outputs/acceptance/S02/import_summary.json').read_text())['real_bundle_path'])
    before = {p:hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob('*') if p.is_file()}
    at = start(tmp_path,monkeypatch)
    at.session_state['bundle'] = DataBundle.load(path)
    at.session_state['bundle_version'] = path.name
    at.radio(key='cs_source').set_value('当前已打开导入版本').run(); compute(at)
    r = at.session_state['cs_result']
    assert r.cardinality.n == 0 and len(r.audit) == 3
    assert r.audit.reason.str.contains('monthly_preparation_required').all()
    assert before == {p:hashlib.sha256(p.read_bytes()).hexdigest() for p in before}
