from io import BytesIO
from pathlib import Path
import pandas as pd
from streamlit.testing.v1 import AppTest
from portfolio.data.alignment_samples import sample_alignment_inputs

ROOT = Path(__file__).resolve().parents[1]

def start(tmp_path, monkeypatch):
    monkeypatch.setenv('PORTFOLIO_IMPORTS_ROOT', str(tmp_path / 'imports'))
    at = AppTest.from_file(str(ROOT / 'app/main.py'), default_timeout=20).run()
    assert at.session_state['workspace_route'] == 'overview'
    assert any('共同窗口查验' in option for option in at.selectbox(key='workspace_route').options)
    at.selectbox(key='workspace_route').set_value('alignment').run()
    assert not at.exception
    return at

def sample(at):
    at.radio(key='alignment_mode').set_value('人工测试案例').run()
    at.button(key='alignment_compute').click().run()
    assert not at.exception
    return at

def downloads(at):
    return [x for x in at.get('download_button') if x.proto.label.startswith('下载共同')]

def test_early_late_and_isolation(tmp_path, monkeypatch):
    at = sample(start(tmp_path, monkeypatch))
    assert at.session_state['alignment_result'].matrix.shape == (60, 1)
    assert len(at.session_state['bundle'].observations) == 0
    assert len(downloads(at)) == 3
    at.text_input(key='alignment_decision').set_value('2025-02-01T06:00:00+08:00').run()
    assert at.session_state['alignment_result'] is None
    assert not downloads(at)
    at.button(key='alignment_compute').click().run()
    assert at.session_state['alignment_result'].matrix.shape == (60, 2)
    at.text_input(key='alignment_end').set_value('2024-12').run()
    assert at.session_state['alignment_result'] is None
    assert not downloads(at)

def test_no_handoff_and_source_content_staleness(tmp_path, monkeypatch):
    from app.views.hkd_returns import sample_bundle
    at = start(tmp_path, monkeypatch)
    assert at.button(key='alignment_compute').disabled
    at.selectbox(key='workspace_route').set_value('returns_window').run()
    at.session_state['bundle'] = sample_bundle()
    at.run()
    at.selectbox(key='hkd_fx_mode').set_value('完整人工汇率案例').run()
    at.button(key='hkd_compute').click().run()
    at.selectbox(key='workspace_route').set_value('alignment').run()
    assert not at.button(key='alignment_compute').disabled
    at.session_state['bundle'].observations.loc[0, 'value'] = .03
    at.run()
    assert at.button(key='alignment_compute').disabled
    assert any('变化' in x.value for x in at.warning)

def test_upload_changes_malformed_and_sheet(tmp_path, monkeypatch):
    import streamlit
    _, timing, _ = sample_alignment_inputs()
    upload = BytesIO(timing.to_csv(index=False).encode()); upload.name = 'timing.csv'
    selection = {'file': upload}
    monkeypatch.setattr(streamlit, 'file_uploader', lambda *a, **k: selection['file'])
    at = start(tmp_path, monkeypatch)
    at.radio(key='alignment_mode').set_value('人工测试案例').run()
    at.selectbox(key='alignment_timing_mode').set_value('上传时间证据').run()
    at.button(key='alignment_compute').click().run()
    assert not at.exception
    assert at.session_state['alignment_result'].matrix.shape == (60, 1)
    coverage = at.session_state['alignment_result'].coverage
    assert set(coverage.timing_source_file.dropna()) == {'timing.csv'}
    changed = BytesIO(timing.to_csv(index=False).encode() + b'\n'); changed.name = 'timing.csv'
    selection['file'] = changed; at.run()
    assert at.session_state['alignment_result'] is None
    assert not downloads(at)
    bad = BytesIO(b'broken'); bad.name = 'bad.xlsx'; selection['file'] = bad; at.run()
    assert not at.exception
    assert at.session_state['alignment_result'] is None
    assert at.error
    workbook = BytesIO()
    with pd.ExcelWriter(workbook, engine='openpyxl') as writer:
        timing.to_excel(writer, sheet_name='完整', index=False)
        timing.iloc[:-1].to_excel(writer, sheet_name='缺行', index=False)
    workbook.name = 'timing.xlsx'; selection['file'] = workbook; at.run()
    at.button(key='alignment_compute').click().run()
    assert not at.exception
    assert at.session_state['alignment_result'] is not None
    at.selectbox(key='alignment_sheet').set_value('缺行').run()
    assert at.session_state['alignment_result'] is None
    assert not downloads(at)

def test_previous_synthetic_handoff_is_labelled(tmp_path, monkeypatch):
    at = start(tmp_path, monkeypatch)
    at.selectbox(key='workspace_route').set_value('returns_window').run()
    at.radio(key='hkd_data_mode').set_value('人工测试案例').run()
    at.button(key='hkd_compute').click().run()
    at.selectbox(key='workspace_route').set_value('alignment').run()
    assert not at.button(key='alignment_compute').disabled
    assert any('上一页人工' in x.value for x in at.info)

def test_chinese_summary_download_content_and_invalid_decision(tmp_path, monkeypatch):
    import streamlit
    captured = {}
    original = streamlit.download_button
    def capture(label, data, *args, **kwargs):
        captured[kwargs.get('key')] = data
        return original(label, data, *args, **kwargs)
    monkeypatch.setattr(streamlit, 'download_button', capture)
    at = sample(start(tmp_path, monkeypatch))
    compact = next(x.value for x in at.dataframe if '有效月数' in x.value.columns)
    assert compact.set_index('资产标识').loc['SHORT_HISTORY', '产品名称'] == '仅59个月'
    matrix = pd.read_csv(BytesIO(captured['alignment_download_矩阵']))
    assert matrix.shape == (60, 2)
    assert list(matrix.columns) == ['date', 'HKD_COMPLETE']
    assert matrix.iloc[0, 0] == '2020-02-29'
    assert matrix.iloc[-1, 0] == '2025-01-31'
    assert (matrix.HKD_COMPLETE == .01).all()
    at.text_input(key='alignment_decision').set_value('2025-01-31T17:00:00').run()
    assert at.session_state['alignment_result'] is None
    assert not downloads(at)
    at.button(key='alignment_compute').click().run()
    assert not at.exception
    assert at.error
    assert at.session_state['alignment_result'] is None

def test_synthetic_content_change_invalidates(tmp_path, monkeypatch):
    import app.views.alignment as view
    at = sample(start(tmp_path, monkeypatch))
    original = view.sample_alignment_inputs
    def changed():
        reconciliation, timing, assets = original()
        reconciliation.loc[reconciliation.asset_id == 'HKD_COMPLETE', 'hkd_return'] = .02
        return reconciliation, timing, assets
    monkeypatch.setattr(view, 'sample_alignment_inputs', changed)
    at.run()
    assert at.session_state['alignment_result'] is None
    assert not downloads(at)

def test_all_blocked_handoff_is_disabled_and_clears_old_alignment(tmp_path, monkeypatch):
    from app.views.hkd_returns import sample_bundle
    at = sample(start(tmp_path, monkeypatch))
    at.selectbox(key='workspace_route').set_value('returns_window').run()
    bundle = sample_bundle()
    bundle.observations['value_kind'] = 'price_return'
    at.session_state['bundle'] = bundle
    at.run()
    at.button(key='hkd_compute').click().run()
    assert not (at.session_state['hkd_result'].reconciliation.status == 'valid').any()
    at.selectbox(key='workspace_route').set_value('alignment').run()
    at.radio(key='alignment_mode').set_value('上一页当前港币对照').run()
    assert at.button(key='alignment_compute').disabled
    assert at.session_state['alignment_result'] is None
    assert not downloads(at)
    assert any('总收益' in x.value and '汇率' in x.value for x in at.info)

def test_saved_handoff_uses_product_names_and_retains_blocked_assets(tmp_path, monkeypatch):
    from app.views.hkd_returns import sample_bundle
    at = start(tmp_path, monkeypatch)
    at.selectbox(key='workspace_route').set_value('returns_window').run()
    bundle = sample_bundle()
    bundle.assets.loc[bundle.assets.asset_id == 'SYNTH_HKD', 'name'] = '真实导入产品名称'
    at.session_state['bundle'] = bundle
    at.run()
    at.button(key='hkd_compute').click().run()
    at.selectbox(key='workspace_route').set_value('alignment').run()
    assert not at.button(key='alignment_compute').disabled
    at.button(key='alignment_compute').click().run()
    assert not at.exception
    compact = next(x.value for x in at.dataframe if '有效月数' in x.value.columns).set_index('资产标识')
    assert compact.loc['SYNTH_HKD', '产品名称'] == '真实导入产品名称'
    assert 'SYNTH_USD' in compact.index
    assert 'SYNTH_ADJ' in compact.index

def test_mode_switch_overrides_restored_frontend_timing_value(tmp_path, monkeypatch):
    """Model keyed browser restoration after app deletes server-side widget value."""
    import streamlit
    original = streamlit.selectbox
    restore = {'active': False}
    def selectbox(label, options, *args, **kwargs):
        if kwargs.get('key') == 'alignment_timing_mode' and restore['active']:
            # In the real browser the same keyed widget still carries its previous
            # upload selection. Deletion leaves no authoritative value to override it.
            if 'alignment_timing_mode' not in streamlit.session_state:
                streamlit.session_state['alignment_timing_mode'] = '上传时间证据'
        return original(label, options, *args, **kwargs)
    monkeypatch.setattr(streamlit, 'selectbox', selectbox)
    at = start(tmp_path, monkeypatch)
    assert at.selectbox(key='alignment_timing_mode').value == '上传时间证据'
    restore['active'] = True
    at.radio(key='alignment_mode').set_value('人工测试案例').run()
    assert at.selectbox(key='alignment_timing_mode').value == '人工时间证据'
    at.button(key='alignment_compute').click().run()
    assert at.session_state['alignment_result'].matrix.shape == (60, 1)
    at.radio(key='alignment_mode').set_value('上一页当前港币对照').run()
    assert at.selectbox(key='alignment_timing_mode').value == '上传时间证据'
