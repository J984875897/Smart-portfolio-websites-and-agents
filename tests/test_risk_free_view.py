from io import BytesIO
from pathlib import Path
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from portfolio.data.risk_free_samples import sample_risk_free_quotes, CASES

ROOT = Path(__file__).resolve().parents[1]

def start(tmp_path, monkeypatch):
    monkeypatch.setenv('PORTFOLIO_IMPORTS_ROOT', str(tmp_path / 'imports'))
    at = AppTest.from_file(str(ROOT / 'app/main.py'), default_timeout=20).run()
    assert at.session_state['workspace_route'] == 'overview'
    assert any('利率与因子' in option for option in at.selectbox(key='workspace_route').options)
    at.selectbox(key='workspace_route').set_value('rates_factors').run()
    assert not at.exception
    return at

def compute(at):
    at.button(key='rf_compute').click().run()
    assert not at.exception
    return at.session_state['rf_result']

def downloads(at):
    return [x for x in at.get('download_button') if x.proto.label in ['下载利率查验报告 CSV', '下载港币代理收益 CSV']]

def test_complete_and_isolation(tmp_path, monkeypatch):
    at = start(tmp_path, monkeypatch)
    result = compute(at)
    assert result.available
    assert result.series.tolist() == pytest.approx([.0031,.0029,.0031])
    assert len(at.session_state['bundle'].observations) == 0
    assert len(downloads(at)) == 2
    assert any('可用月份 3 / 3' in x.value for x in at.caption)
    summary = next(x.value for x in at.dataframe if '月度港币代理收益' in x.value.columns)
    assert summary['期间天数'].tolist() == [31, 29, 31]
    assert summary['年化报价（%）'].tolist() == ['3.65%', '3.65%', '3.65%']
    assert summary['月度港币代理收益'].tolist() == ['0.31%', '0.29%', '0.31%']

@pytest.mark.parametrize('case', CASES[1:])
def test_failed_cases(tmp_path, monkeypatch, case):
    at = start(tmp_path, monkeypatch)
    compute(at)
    at.selectbox(key='rf_case').set_value(case).run()
    assert at.session_state['rf_result'] is None
    assert not downloads(at)
    result = compute(at)
    assert not result.available
    if case == '缺中间报价':
        summary = next(x.value for x in at.dataframe if '年化报价（%）' in x.value.columns)
        assert summary['年化报价（%）'].iloc[1] == '未知年化报价'
    assert result.series.isna().sum() == 1
    assert any('可用月份 2 / 3' in x.value for x in at.caption)

@pytest.mark.parametrize('key,value', [('rf_end','2024-04'),('rf_months',4),('rf_decision','2024-03-31T15:59:59+08:00')])
def test_window_or_immature_change(tmp_path, monkeypatch, key, value):
    at = start(tmp_path, monkeypatch); compute(at)
    widget = at.number_input(key=key) if key == 'rf_months' else at.text_input(key=key)
    widget.set_value(value).run()
    assert at.session_state['rf_result'] is None
    assert not downloads(at)
    assert not compute(at).available

@pytest.mark.parametrize('key,value', [('rf_end','2024/03'),('rf_decision','bad+08:00'),('rf_decision','2024-03-31T16:00:00')])
def test_invalid_parameters_clear(tmp_path, monkeypatch, key, value):
    at = start(tmp_path, monkeypatch); compute(at)
    at.text_input(key=key).set_value(value).run()
    assert compute(at) is None
    assert at.error
    assert not downloads(at)

def test_no_upload(tmp_path, monkeypatch):
    at = start(tmp_path, monkeypatch); compute(at)
    at.radio(key='rf_mode').set_value('上传报价文件').run()
    assert at.session_state['rf_result'] is None
    assert not downloads(at)
    assert at.button(key='rf_compute').disabled

def test_uploaded_csv_workbook_and_malformed(tmp_path, monkeypatch):
    import streamlit
    q = sample_risk_free_quotes()
    def upload(data, name):
        f = BytesIO(data); f.name = name; return f
    selection = {'file': upload(q.to_csv(index=False).encode(), 'quotes.csv')}
    monkeypatch.setattr(streamlit, 'file_uploader', lambda *a, **k: selection['file'])
    at = start(tmp_path, monkeypatch)
    at.radio(key='rf_mode').set_value('上传报价文件').run()
    assert compute(at).available
    assert set(at.session_state['rf_result'].report.quote_source_file) == {'quotes.csv'}
    for data, name in [(q.to_csv(index=False).encode()+b'\n','quotes.csv'), (q.to_csv(index=False).encode(),'renamed.csv')]:
        selection['file'] = upload(data, name); at.run()
        assert at.session_state['rf_result'] is None
        assert not downloads(at)
        compute(at)
    workbook = BytesIO()
    with pd.ExcelWriter(workbook, engine='openpyxl') as writer:
        q.iloc[:1].to_excel(writer, sheet_name='短表', index=False)
        q.to_excel(writer, sheet_name='完整', index=False)
    selection['file'] = upload(workbook.getvalue(), 'quotes.xlsx'); at.run()
    assert not compute(at).available
    at.selectbox(key='rf_sheet').set_value('完整').run()
    assert at.session_state['rf_result'] is None
    assert not downloads(at)
    assert compute(at).available
    selection['file'] = upload(b'broken', 'bad.xlsx'); at.run()
    assert not at.exception
    assert at.error
    assert at.session_state['rf_result'] is None
    assert not downloads(at)
    selection['file'] = upload(b'wrong\n1', 'bad.csv'); at.run()
    assert compute(at) is None
    assert at.error

def test_download_decimals(tmp_path, monkeypatch):
    import streamlit
    captured = {}; original = streamlit.download_button
    def capture(label, data, *args, **kwargs):
        captured[label] = data
        return original(label, data, *args, **kwargs)
    monkeypatch.setattr(streamlit, 'download_button', capture)
    at = start(tmp_path, monkeypatch); compute(at)
    frame = pd.read_csv(BytesIO(captured['下载港币代理收益 CSV']))
    assert frame.rf_hkd.tolist() == pytest.approx([.0031,.0029,.0031])
    assert frame.date.tolist() == ['2024-01-31','2024-02-29','2024-03-31']
