from io import BytesIO
import pytest
import streamlit as st
from tests.test_workspace_shell_view import start, ROOT


@pytest.mark.parametrize('route,key,result_key', [
    ('returns_window','hkd_fx_upload','hkd_result'),
    ('alignment','alignment_upload','alignment_result'),
    ('rates_factors','rf_upload','rf_result'),
    ('daily_hkd','dh_fx_upload','dh_result'),
])
def test_uploaded_tool_input_survives_navigation_and_explicit_clear(tmp_path, monkeypatch, route, key, result_key):
    if route == 'returns_window':
        data = (ROOT/'tests/fixtures/hkd/fx.csv').read_bytes()
    elif route == 'alignment':
        from portfolio.data.alignment_samples import sample_alignment_inputs
        data = sample_alignment_inputs()[1].to_csv(index=False).encode()
    elif route == 'rates_factors':
        from portfolio.data.risk_free_samples import sample_risk_free_quotes
        data = sample_risk_free_quotes().to_csv(index=False).encode()
    else:
        data = b'date,currency,hkd_per_unit,source_name\n2024-12-31,USD,7.8,manual\n2025-01-31,USD,7.9,manual\n'
    file = BytesIO(data); file.name = 'tool_evidence.csv'
    files = {key: file}
    original = st.file_uploader
    def uploader(*a, **kw):
        return files.get(key) if kw.get('key') == key else original(*a, **kw)
    monkeypatch.setattr(st, 'file_uploader', uploader)
    at = start(tmp_path, monkeypatch)
    at.selectbox(key='workspace_route').set_value(route).run()
    if route == 'returns_window':
        at.radio(key='hkd_data_mode').set_value('人工测试案例').run()
        at.selectbox(key='hkd_fx_mode').set_value('上传本地汇率文件').run()
        compute_key = 'hkd_compute'
    elif route == 'alignment':
        at.radio(key='alignment_mode').set_value('人工测试案例').run()
        at.selectbox(key='alignment_timing_mode').set_value('上传时间证据').run()
        compute_key = 'alignment_compute'
    elif route == 'rates_factors':
        at.radio(key='rf_mode').set_value('上传报价文件').run()
        compute_key = 'rf_compute'
    else:
        at.radio(key='dh_fx_mode').set_value('CSV / XLSX 文件').run()
        at.checkbox(key='dh_price_confirm').check().run()
        at.checkbox(key='dh_fx_confirm').check().run()
        compute_key = 'dh_compute'
    at.button(key=compute_key).click().run()
    assert not at.exception
    assert at.session_state[result_key] is not None
    assert any('已有诊断记录' in x.value for x in at.warning)
    at.button(key='nav_overview').click().run()
    files.clear()
    at.selectbox(key='workspace_route').set_value(route).run()
    assert not at.exception
    assert at.session_state[result_key] is not None
    at.button(key='clear_retained_'+key).click().run()
    assert not at.exception
    assert at.session_state[result_key] is None
    assert any('选择输入并执行本页操作' in x.value for x in at.info)
