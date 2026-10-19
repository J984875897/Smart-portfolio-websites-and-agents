from io import BytesIO
from pathlib import Path
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]

def start(tmp_path, monkeypatch):
    monkeypatch.setenv('PORTFOLIO_IMPORTS_ROOT', str(tmp_path / 'imports'))
    at = AppTest.from_file(str(ROOT / 'app/main.py'), default_timeout=15).run()
    assert not at.exception
    assert at.session_state['workspace_route'] == 'overview'
    at.selectbox(key='workspace_route').set_value('returns_window').run()
    return at

def sample(at):
    at.radio(key='hkd_data_mode').set_value('人工测试案例').run()
    assert not at.exception
    return at

def compute(at):
    at.button(key='hkd_compute').click().run()
    assert not at.exception
    return at.session_state['hkd_result'].reconciliation.set_index('asset_id')

def test_demo_isolated_confirmation_and_calculation(tmp_path, monkeypatch):
    at = sample(start(tmp_path, monkeypatch))
    assert len(at.session_state['bundle'].observations) == 0
    rows = compute(at)
    assert pd.isna(rows.loc['SYNTH_ADJ', 'hkd_return']).all()
    assert rows.loc['SYNTH_USD', 'hkd_return'] == pytest.approx(.02294871794871795)
    assert rows.loc['SYNTH_HKD', 'hkd_return'] == pytest.approx(.01)
    at.multiselect(key='hkd_adjusted_assets').set_value(['SYNTH_ADJ']).run()
    assert at.session_state['hkd_result'] is None
    rows = compute(at)
    assert rows.loc['SYNTH_ADJ'].iloc[-1]['hkd_return'] == pytest.approx(.02294871794871795)
    assert rows.loc['SYNTH_LOSS', 'hkd_return'] == -1
    assert len(at.session_state['bundle'].observations) == 0
    at.selectbox(key='workspace_route').set_value('prepare_data').run()
    assert not at.exception
    assert len(at.session_state['bundle'].observations) == 0

def test_fx_and_demo_changes_invalidate(tmp_path, monkeypatch):
    at = sample(start(tmp_path, monkeypatch))
    compute(at)
    at.selectbox(key='hkd_fx_mode').set_value('缺少期末汇率案例').run()
    assert at.session_state['hkd_result'] is None
    rows = compute(at)
    assert pd.isna(rows.loc['SYNTH_USD', 'hkd_return'])
    assert rows.loc['SYNTH_HKD', 'hkd_return'] == pytest.approx(.01)
    at.selectbox(key='hkd_fx_mode').set_value('不提供汇率').run()
    assert at.session_state['hkd_result'] is None
    rows = compute(at)
    assert pd.isna(rows.loc['SYNTH_USD', 'hkd_return'])
    assert rows.loc['SYNTH_HKD', 'hkd_return'] == pytest.approx(.01)
    at.radio(key='hkd_data_mode').set_value('当前已保存数据').run()
    assert at.session_state['hkd_result'] is None

def test_current_content_change_invalidates_without_version_change(tmp_path, monkeypatch):
    from app.views.hkd_returns import sample_bundle
    at = start(tmp_path, monkeypatch)
    at.session_state['bundle'] = sample_bundle()
    at.run()
    at.selectbox(key='hkd_fx_mode').set_value('完整人工汇率案例').run()
    compute(at)
    bundle = at.session_state['bundle']
    bundle.observations.loc[bundle.observations.asset_id == 'SYNTH_USD', 'value'] = .02
    at.run()
    assert at.session_state['hkd_result'] is None
    rows = compute(at)
    assert rows.loc['SYNTH_USD', 'local_return'] == .02

def test_malformed_upload_clears_result_and_is_scoped(tmp_path, monkeypatch):
    import streamlit
    selected = {'file': None}
    monkeypatch.setattr(streamlit, 'file_uploader', lambda *a, **k: selected['file'])
    at = sample(start(tmp_path, monkeypatch))
    compute(at)
    at.selectbox(key='hkd_fx_mode').set_value('上传本地汇率文件').run()
    bad = BytesIO(b'not-a-workbook'); bad.name = 'bad.xlsx'
    selected['file'] = bad
    at.run()
    assert not at.exception
    assert at.session_state['hkd_result'] is None
    assert any('汇率文件无法读取' in x.value for x in at.error)

def test_uploaded_fx_bytes_invalidate_and_preserve_source(tmp_path, monkeypatch):
    import streamlit
    uploaded = BytesIO((ROOT / 'tests/fixtures/hkd/fx.csv').read_bytes())
    uploaded.name = 'user_fx.csv'
    selection = {'file': uploaded}
    def uploader(*a, **k):
        # Native removal runs on_change; a plain None from this transport mock
        # also represents an unmounted widget after navigation.
        if selection.pop('removed', False):
            k['on_change'](*k['args'])
        return selection['file']
    monkeypatch.setattr(streamlit, 'file_uploader', uploader)
    at = sample(start(tmp_path, monkeypatch))
    at.selectbox(key='hkd_fx_mode').set_value('上传本地汇率文件').run()
    rows = compute(at)
    assert rows.loc['SYNTH_USD', 'hkd_return'] == pytest.approx(.02294871794871795)
    assert rows.loc['SYNTH_USD', 'fx_end_source_file'] == 'user_fx.csv'
    old_hash = rows.loc['SYNTH_USD', 'fx_end_source_hash']
    uploaded = BytesIO((ROOT / 'tests/fixtures/hkd/fx.csv').read_bytes().replace(b'7.9', b'8.0'))
    uploaded.name = 'user_fx.csv'; selection['file'] = uploaded
    at.run()
    assert at.session_state['hkd_result'] is None
    rows = compute(at)
    assert rows.loc['SYNTH_USD', 'hkd_return'] == pytest.approx(.03589743589743599)
    assert rows.loc['SYNTH_USD', 'fx_end_source_hash'] != old_hash
    selection['file'] = None
    selection['removed'] = True
    at.run()
    assert at.session_state['hkd_result'] is None

def test_uploaded_xlsx_sheet_invalidation(tmp_path, monkeypatch):
    import streamlit
    payload = BytesIO()
    with pd.ExcelWriter(payload, engine='openpyxl') as writer:
        pd.read_csv(ROOT / 'tests/fixtures/hkd/fx.csv').to_excel(writer, sheet_name='完整', index=False)
        pd.read_csv(ROOT / 'tests/fixtures/hkd/fx_missing_end.csv').to_excel(writer, sheet_name='缺末值', index=False)
    payload.name = 'fx.xlsx'
    monkeypatch.setattr(streamlit, 'file_uploader', lambda *a, **k: payload)
    at = sample(start(tmp_path, monkeypatch))
    at.selectbox(key='hkd_fx_mode').set_value('上传本地汇率文件').run()
    rows = compute(at)
    assert rows.loc['SYNTH_USD', 'fx_end_source_sheet'] == '完整'
    at.selectbox(key='hkd_fx_sheet').set_value('缺末值').run()
    assert at.session_state['hkd_result'] is None
    rows = compute(at)
    assert pd.isna(rows.loc['SYNTH_USD', 'hkd_return'])

def test_compact_result_shows_chinese_percentage_answers(tmp_path, monkeypatch):
    at = sample(start(tmp_path, monkeypatch))
    compute(at)
    summaries = [x.value for x in at.dataframe if '港币收益（%）' in x.value.columns]
    assert summaries, 'HKD answer must be prominently visible in Chinese compact columns'
    summary = summaries[0].set_index('资产标识')
    assert list(summaries[0].columns[:6]) == ['产品名称', '资产标识', '原币', '期末日期', '原币收益（%）', '港币收益（%）']
    assert summary.loc['SYNTH_USD', '港币收益（%）'] == pytest.approx(2.294871794871795)
    assert summary.loc['SYNTH_HKD', '港币收益（%）'] == pytest.approx(1.)
    assert summary.loc['SYNTH_USD', '原币收益（%）'] == pytest.approx(1.)
    assert summary.loc['SYNTH_USD', '处理状态'] == '可查验'
    assert pd.isna(summary.loc['SYNTH_ADJ', '港币收益（%）']).all()
    at.selectbox(key='hkd_fx_mode').set_value('缺少期末汇率案例').run()
    compute(at)
    summary = next(x.value for x in at.dataframe if '港币收益（%）' in x.value.columns).set_index('资产标识')
    assert pd.isna(summary.loc['SYNTH_USD', '港币收益（%）'])
    assert summary.loc['SYNTH_USD', '处理状态'] == '阻止：缺失或不可用'
    assert summary.loc['SYNTH_USD', '处理说明'] == '缺少精确期末汇率'
