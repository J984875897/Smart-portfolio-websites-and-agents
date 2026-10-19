from io import BytesIO
import json
import pandas as pd
import pytest
from tests.test_candidate_screening_view import start, compute as screen_compute


def compute(at):
    screen_compute(at)
    at.selectbox(key='workspace_route').set_value('risk_preview').run()
    assert not at.exception
    return at


def risk_compute(at):
    at.button(key='ra_compute').click().run(timeout=60)
    assert not at.exception
    assert at.session_state['ra_preview'] is not None
    return at


def risk_downloads(at):
    return [x for x in at.get('download_button') if x.proto.label.startswith('下载风险')]


def test_equal_weight_constant_state_and_strict_exports(tmp_path,monkeypatch):
    import streamlit
    captured={}; original=streamlit.download_button
    def capture(label,data,*args,**kw):
        captured[kw.get('key')]=data
        return original(label,data,*args,**kw)
    monkeypatch.setattr(streamlit,'download_button',capture)
    at=compute(start(tmp_path,monkeypatch))
    assert at.button(key='ra_compute') and not risk_downloads(at)
    risk_compute(at)
    p=at.session_state['ra_preview']
    assert p.sample_risk.metrics['volatility_ann'] == 0
    assert p.evidence['positive_weight_count'] == 100 and p.evidence['target_k'] == 30
    assert len(risk_downloads(at)) == 9
    data=json.loads(captured['ra_export_risk_evidence.json'])
    assert data['sample_metrics']['diversification_ratio'] is None
    assert any('不可用' in x.value for x in at.info)
    at.multiselect(key='cs_excluded').set_value(['SYNTH_SCREEN_099']).run()
    assert at.session_state['ra_preview'] is None and not risk_downloads(at)
    compute(at)
    assert not any(x.key == 'ra_compute' for x in at.button)


def test_variable_sample_display_changes_preserve_results(tmp_path,monkeypatch):
    at=start(tmp_path,monkeypatch)
    at.radio(key='cs_source').set_value('SYNTH 相关性与风险演示').run()
    compute(at);risk_compute(at)
    p=at.session_state['ra_preview'];fp=p.fingerprint
    assert p.sample_risk.metrics['volatility_ann'] > 0
    assert p.model_risk.contributions.loc['SYNTH_SCREEN_000','asset_volatility_ann'] > 0
    assert p.sample_risk.contributions.loc['SYNTH_SCREEN_000','asset_volatility_ann'] == 0
    at.multiselect(key='ra_corr_ids').set_value(['SYNTH_SCREEN_001','SYNTH_SCREEN_003']).run()
    at.selectbox(key='ra_risk_method').set_value('收缩模型（Ledoit–Wolf）').run()
    at.selectbox(key='ra_pair_sort').set_value('绝对值从高到低').run()
    at.text_input(key='cs_search').set_value('099').run()
    assert at.session_state['ra_preview'].fingerprint == fp and len(risk_downloads(at)) == 9
    at.number_input(key='cs_k').set_value(20).run()
    assert at.session_state['ra_preview'] is None and not risk_downloads(at)


def test_weights_mode_invalid_file_and_valid_sparse_preview(tmp_path,monkeypatch):
    import streamlit
    payloads={}
    original=streamlit.file_uploader
    def uploader(*args,**kw):
        if kw.get('key','').startswith('ra_weights_'): return payloads.get('file')
        return original(*args,**kw)
    monkeypatch.setattr(streamlit,'file_uploader',uploader)
    at=risk_compute(compute(start(tmp_path,monkeypatch)))
    at.radio(key='ra_weight_mode').set_value('上传自定义多头权重 CSV').run()
    assert at.session_state['ra_preview'] is None and at.button(key='ra_compute').disabled
    bad=BytesIO(b'asset_id,weight\nwrong,1');bad.name='weights.csv';payloads['file']=bad
    at.run()
    assert at.error and not risk_downloads(at) and at.button(key='ra_compute').disabled
    ids=at.session_state['cs_result'].eligible_asset_ids
    weights=pd.DataFrame({'asset_id':ids,'weight':[1.]+[0.]*(len(ids)-1)})
    good=BytesIO(weights.to_csv(index=False).encode());good.name='weights.csv';payloads['file']=good
    at.run();risk_compute(at)
    assert at.session_state['ra_preview'].evidence['positive_weight_count'] == 1
    assert at.session_state['ra_preview'].evidence['portfolio_constructed'] is False
    payloads['file']=bad;at.run()
    assert at.session_state['ra_preview'] is None and not risk_downloads(at)


@pytest.mark.parametrize('key,value',[('cs_decision','bad'),('cs_markets',[]),('cs_source','SYNTH 缺月与时间案例')])
def test_input_changes_clear_risk_even_without_result_section(tmp_path,monkeypatch,key,value):
    at=risk_compute(compute(start(tmp_path,monkeypatch)))
    widget=at.text_input(key=key) if key == 'cs_decision' else (at.multiselect(key=key) if key == 'cs_markets' else at.radio(key=key))
    widget.set_value(value).run()
    assert at.session_state['ra_preview'] is None and not risk_downloads(at)


def test_empty_real_source_has_no_risk_button(tmp_path,monkeypatch):
    at=start(tmp_path,monkeypatch)
    at.radio(key='cs_source').set_value('当前已打开导入版本').run()
    assert not any(x.key == 'ra_compute' for x in at.button)


def test_uploaded_correlated_weights_have_dr_one_and_negative_contributions(tmp_path,monkeypatch):
    import streamlit
    original=streamlit.file_uploader
    files={}
    def uploader(*args,**kw):
        if kw.get('key','').startswith('ra_weights_'):return files.get('weights')
        return original(*args,**kw)
    monkeypatch.setattr(streamlit,'file_uploader',uploader)
    at=start(tmp_path,monkeypatch)
    at.radio(key='cs_source').set_value('SYNTH 相关性与风险演示').run()
    compute(at)
    at.radio(key='ra_weight_mode').set_value('上传自定义多头权重 CSV').run()
    ids=at.session_state['cs_result'].eligible_asset_ids
    def put(weights):
        frame=pd.DataFrame({'asset_id':ids,'weight':[weights.get(a,0) for a in ids]})
        file=BytesIO(frame.to_csv(index=False).encode());file.name='weights.csv';files['weights']=file
        at.run();risk_compute(at)
        return at.session_state['ra_preview']
    p=put({'SYNTH_SCREEN_001':.5,'SYNTH_SCREEN_002':.5})
    assert p.sample_risk.metrics['diversification_ratio'] == pytest.approx(1)
    p=put({'SYNTH_SCREEN_001':.8,'SYNTH_SCREEN_003':.2})
    assert p.sample_risk.contributions.loc['SYNTH_SCREEN_003','volatility_contribution_ann'] < 0
    assert p.sample_risk.contributions.volatility_contribution_ann.sum() == pytest.approx(p.sample_risk.metrics['volatility_ann'])


def test_current_real_daily_version_remains_n0_with_no_risk(tmp_path,monkeypatch):
    from pathlib import Path
    import hashlib
    from portfolio.data.contracts import DataBundle
    root=Path(__file__).resolve().parents[1]
    source=Path(json.loads((root/'outputs/acceptance/S02/import_summary.json').read_text())['real_bundle_path'])
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
    at=start(tmp_path,monkeypatch)
    at.session_state['bundle']=DataBundle.load(source)
    at.session_state['bundle_version']=source.name
    at.radio(key='cs_source').set_value('当前已打开导入版本').run()
    compute(at)
    assert at.session_state['cs_result'].cardinality.n == 0
    assert not any(x.key == 'ra_compute' for x in at.button) and not risk_downloads(at)
    assert before == {p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in before}
