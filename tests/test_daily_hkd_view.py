from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def start(monkeypatch, tmp_path):
    monkeypatch.setenv('PORTFOLIO_DOWNLOADS_ROOT', str(tmp_path))
    monkeypatch.setenv('PORTFOLIO_REFERENCE_DOWNLOADS_ROOT', str(tmp_path/'reference'))
    import portfolio.data.providers.yahoo as yahoo
    monkeypatch.setattr(yahoo, 'fetch_yahoo', lambda *a, **k: pytest.fail('unexpected network'))
    at = AppTest.from_file(str(ROOT/'app/main.py'), default_timeout=20).run()
    at.selectbox(key='workspace_route').set_value('daily_hkd').run()
    assert not at.exception
    return at


def compute(at, confirmed=True):
    if confirmed:
        at.checkbox(key='dh_price_confirm').check().run()
        if any(x.key == 'dh_fx_confirm' for x in at.checkbox):
            at.checkbox(key='dh_fx_confirm').check().run()
    at.button(key='dh_compute').click().run()
    assert not at.exception
    return at.session_state['dh_result']


def exports(at):
    return [x for x in at.get('download_button') if x.key != 'dh_template']


def test_default_complete_invalidation_and_bundle(monkeypatch, tmp_path):
    at = start(monkeypatch, tmp_path)
    before = at.session_state['bundle'].observations.copy(deep=True)
    assert at.session_state['dh_result'] is None
    assert not exports(at)
    result = compute(at)
    assert result.reconciliation.iloc[0].hkd_return == pytest.approx(.114102564102564)
    assert result.metadata['historical_eligible'] is False
    assert len(exports(at)) == 7
    assert at.session_state['bundle'].observations.equals(before)
    at.number_input(key='dh_max_age').set_value(6).run()
    assert at.session_state['dh_result'] is None
    assert not exports(at)
    compute(at)
    at.checkbox(key='dh_fx_confirm').uncheck().run()
    assert at.session_state['dh_result'] is None
    assert not exports(at)


@pytest.mark.parametrize('case,reason', [('缺期末月','missing_month'), ('过旧','stale_quote'), ('重复末日','duplicate_date')])
def test_fx_failures(monkeypatch, tmp_path, case, reason):
    at = start(monkeypatch, tmp_path)
    at.selectbox(key='dh_fx_case').set_value(case).run()
    row = compute(at).reconciliation.iloc[0]
    assert row.status == 'blocked'
    assert reason in row.reason
    assert row.hkd_return != row.hkd_return


def test_unconfirmed_price_and_hkd(monkeypatch, tmp_path):
    at = start(monkeypatch, tmp_path)
    assert compute(at, False).reconciliation.hkd_return.isna().all()
    at.selectbox(key='dh_symbol').set_value('2800.HK').run()
    assert not any(x.key == 'dh_fx_confirm' for x in at.checkbox)
    assert compute(at).reconciliation.iloc[0].hkd_return == pytest.approx(.1)


def test_empty_cache_and_root_invalidation(monkeypatch, tmp_path):
    at = start(monkeypatch, tmp_path)
    compute(at)
    monkeypatch.setenv('PORTFOLIO_REFERENCE_DOWNLOADS_ROOT', str(tmp_path/'changed'))
    at.run()
    assert at.session_state['dh_result'] is None
    assert not exports(at)
    at.radio(key='dh_fx_mode').set_value('已下载缓存').run()
    assert at.error and at.button(key='dh_compute').disabled
    at.radio(key='dh_price_mode').set_value('已下载缓存').run()
    assert at.button(key='dh_compute').disabled


def test_cache_corruption_withdraws(monkeypatch, tmp_path):
    from test_daily_monthly_view import cache
    import json
    rid = cache(tmp_path)
    before = {p:p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    at = start(monkeypatch, tmp_path)
    at.radio(key='dh_price_mode').set_value('已下载缓存').run()
    compute(at)
    assert {p:p.read_bytes() for p in before} == before
    manifest_path = tmp_path/'runs'/rid/'snapshot_manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    original_created = manifest['created_utc']
    manifest['created_utc'] = 'changed'
    manifest_path.write_text(json.dumps(manifest))
    at.run()
    assert at.session_state['dh_result'] is None
    assert at.button(key='dh_compute').disabled
    manifest['created_utc'] = original_created
    manifest_path.write_text(json.dumps(manifest))
    at.run()
    compute(at)
    (manifest_path.parent/manifest['items'][0]['raw_file']).write_bytes(b'corrupt')
    at.run()
    assert at.session_state['dh_result'] is None
    assert not exports(at)
    assert at.button(key='dh_compute').disabled


def test_samples_and_upload_identity():
    from portfolio.data.daily_hkd_samples import sample_daily_prices, sample_daily_fx
    from app.views.daily_hkd import read_fx_upload, input_token
    frame = sample_daily_prices('SPY','2025-01','2025-01')
    assert frame.attrs['source_name'].startswith('SYNTH')
    fx = sample_daily_fx('2025-01','2025-01')
    assert fx.hkd_per_unit.tolist() == [7.8,7.9]
    raw = b'date,currency,hkd_per_unit,source_name\n2024-12-31,USD,7.8,manual\n2025-01-31,USD,7.9,manual\n'
    imported = read_fx_upload(raw,'fx.csv',0)
    assert imported.attrs['raw_bytes'] == raw
    assert imported.attrs['source_rows'] == [2,3]
    tokens = [input_token((raw,'fx.csv',0)), input_token((raw+b'\n','fx.csv',0)), input_token((raw,'other.csv',0)), input_token((raw,'fx.csv',1))]
    assert len(set(tokens)) == 4


def test_upload_bytes_name_sheet_and_errors_withdraw(monkeypatch, tmp_path):
    """Native uploader transport is substituted; parser and page lifecycle are real."""
    from io import BytesIO
    import pandas as pd
    import app.views.daily_hkd as view
    payload = {'file': None}
    monkeypatch.setattr(view.st, 'file_uploader', lambda *a, **k: payload['file'])
    def uploaded(raw, name):
        value = BytesIO(raw)
        value.name = name
        return value
    raw = b'date,currency,hkd_per_unit,source_name\n2024-12-31,USD,7.8,manual\n2025-01-31,USD,7.9,manual\n'
    payload['file'] = uploaded(raw, 'fx.csv')
    at = start(monkeypatch, tmp_path)
    at.radio(key='dh_fx_mode').set_value('CSV / XLSX 文件').run()
    result = compute(at)
    assert result.reconciliation.iloc[0].hkd_return == pytest.approx(.114102564102564)
    assert result.fx_observations.source_row.tolist() == [2,3]
    payload['file'] = uploaded(raw+b'\n', 'fx.csv')
    at.run()
    assert at.session_state['dh_result'] is None and not exports(at)
    compute(at)
    payload['file'] = uploaded(raw, 'renamed.csv')
    at.run()
    assert at.session_state['dh_result'] is None and not exports(at)
    workbook = BytesIO()
    frame = pd.read_csv(BytesIO(raw))
    with pd.ExcelWriter(workbook, engine='openpyxl') as writer:
        frame.to_excel(writer, sheet_name='first', index=False)
        frame.to_excel(writer, sheet_name='second', index=False)
    payload['file'] = uploaded(workbook.getvalue(), 'fx.xlsx')
    at.run()
    compute(at)
    at.selectbox(key='dh_fx_sheet').set_value('second').run()
    assert at.session_state['dh_result'] is None and not exports(at)
    result = compute(at)
    assert set(result.fx_observations.source_sheet) == {'second'}
    payload['file'] = uploaded(b'date,date\n1,2', 'bad.csv')
    at.run()
    assert at.session_state['dh_result'] is None and not exports(at)
    assert at.error and at.button(key='dh_compute').disabled


@pytest.mark.parametrize('provider', ['HKMA 官方日线', 'Yahoo HKD=X 非官方日线'])
def test_fx_cache_readonly_and_corruption(monkeypatch, tmp_path, provider):
    import json
    from test_fx_cache import yahoo, page
    from portfolio.data.providers.base import RawResponse
    from portfolio.data.updates import run_update
    from portfolio.data.reference_updates import run_reference_update
    if provider.startswith('HKMA'):
        root = tmp_path/'reference'
        rid = run_reference_update(root, ['HKMA_USDHKD'], '2024-12-01', '2025-02-01',
            fetch=lambda *a, **k: RawResponse(page([('2024-12-31',7.8),('2025-01-31',7.9)]),200))
    else:
        root = tmp_path
        rid = run_update(root, ['HKD=X'], '2024-12-01', '2025-02-01', fetch=lambda *a: RawResponse(yahoo(),200))
    before = {p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
    at = start(monkeypatch, tmp_path)
    at.radio(key='dh_fx_mode').set_value('已下载缓存').run()
    at.selectbox(key='dh_fx_provider').set_value(provider).run()
    result = compute(at)
    assert result.reconciliation.iloc[0].hkd_return == pytest.approx(.114102564102564)
    assert {p:p.read_bytes() for p in before} == before
    path = root/'runs'/rid/'snapshot_manifest.json'
    manifest = json.loads(path.read_bytes())
    item = manifest['items'][0]
    raw_path = item['raw_file'] if provider.startswith('Yahoo') else item['raw_files'][0]
    (path.parent/raw_path).write_bytes(b'corrupt')
    at.run()
    assert at.session_state['dh_result'] is None and not exports(at)
    assert at.error and at.button(key='dh_compute').disabled


def test_price_failure_confirmation_and_month_root_changes(monkeypatch, tmp_path):
    at = start(monkeypatch, tmp_path)
    at.selectbox(key='dh_price_case').set_value('缺最后交易日').run()
    row = compute(at).reconciliation.iloc[0]
    assert row.status == 'blocked' and 'missing_price' in row.reason
    at.selectbox(key='dh_price_case').set_value('完整报价').run()
    compute(at)
    at.checkbox(key='dh_price_confirm').uncheck().run()
    assert at.session_state['dh_result'] is None and not exports(at)
    compute(at)
    at.text_input(key='dh_end_month').set_value('2025-02').run()
    assert at.session_state['dh_result'] is None and not exports(at)
    compute(at)
    monkeypatch.setenv('PORTFOLIO_DOWNLOADS_ROOT', str(tmp_path/'other'))
    at.run()
    assert at.session_state['dh_result'] is None and not exports(at)
