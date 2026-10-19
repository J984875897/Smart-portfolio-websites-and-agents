from pathlib import Path
import json
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def start(monkeypatch, tmp_path):
    monkeypatch.setenv('PORTFOLIO_DOWNLOADS_ROOT', str(tmp_path))
    import portfolio.data.providers.yahoo as yahoo
    monkeypatch.setattr(yahoo, 'fetch_yahoo', lambda *a, **k: pytest.fail('unexpected network'))
    at = AppTest.from_file(str(ROOT / 'app/main.py'), default_timeout=20).run()
    at.selectbox(key='workspace_route').set_value('daily_monthly').run()
    assert not at.exception
    return at


def compute(at, confirm=True):
    if confirm:
        at.checkbox(key='dm_confirm').check().run()
    at.button(key='dm_compute').click().run()
    assert not at.exception
    return at.session_state['dm_result']


def test_default_and_complete_and_parameter_invalidation(monkeypatch, tmp_path):
    at = start(monkeypatch, tmp_path)
    assert at.session_state['dm_result'] is None
    assert not at.get('download_button')
    result = compute(at)
    assert result.returns.iloc[0].local_return == pytest.approx(.1)
    assert result.metadata['historical_eligible'] is False
    assert len(at.get('download_button')) == 4
    at.text_input(key='dm_end_month').set_value('2025-02').run()
    assert at.session_state['dm_result'] is None
    assert not at.get('download_button')


@pytest.mark.parametrize('case', ['缺最后交易日', '缺月中交易日', '重复日期'])
def test_incomplete_cases_block(monkeypatch, tmp_path, case):
    at = start(monkeypatch, tmp_path)
    at.selectbox(key='dm_case').set_value(case).run()
    result = compute(at)
    assert result.returns.local_return.isna().all()
    assert result.returns.iloc[0].status == 'blocked'


def test_confirmation_month_changes_and_bundle_isolation(monkeypatch, tmp_path):
    at = start(monkeypatch, tmp_path)
    original = at.session_state['bundle'].observations.copy(deep=True)
    assert compute(at, False).returns.local_return.isna().all()
    at.text_input(key='dm_start_month').set_value('2025-03').run()
    at.text_input(key='dm_end_month').set_value('2025-03').run()
    assert compute(at).returns.iloc[0].local_return == pytest.approx(.1)
    at.selectbox(key='workspace_route').set_value('prepare_data').run()
    assert at.session_state['bundle'].observations.equals(original)


def test_future_month_and_confirmation_withdrawal(monkeypatch, tmp_path):
    import app.views.daily_monthly as view
    real_aggregate = view.aggregate_daily_prices

    def aggregate_as_of(prices, **kwargs):
        return real_aggregate(prices, **kwargs, as_of='2026-10-16T00:00:00Z')

    monkeypatch.setattr(view, 'aggregate_daily_prices', aggregate_as_of)
    at = start(monkeypatch, tmp_path)
    compute(at)
    at.checkbox(key='dm_confirm').uncheck().run()
    assert at.session_state['dm_result'] is None
    assert not at.get('download_button')
    at.text_input(key='dm_start_month').set_value('2026-12').run()
    at.text_input(key='dm_end_month').set_value('2026-12').run()
    result = compute(at)
    assert result.returns.local_return.isna().all()
    assert 'month_not_mature' in result.returns.iloc[0].reason


def test_cache_empty_and_root_change_withdraw_results(monkeypatch, tmp_path):
    at = start(monkeypatch, tmp_path)
    compute(at)
    monkeypatch.setenv('PORTFOLIO_DOWNLOADS_ROOT', str(tmp_path/'other'))
    at.run()
    assert at.session_state['dm_result'] is None
    at.radio(key='dm_mode').set_value('已下载缓存').run()
    assert at.error
    assert at.button(key='dm_compute').disabled
    assert not at.get('download_button')


def cache(tmp_path):
    from portfolio.data.updates import run_update
    from portfolio.data.providers.base import RawResponse
    payload = json.loads((ROOT/'tests/fixtures/source_responses/yahoo_chart.json').read_bytes())
    payload['chart']['result'][0]['meta']['symbol'] = 'SPY'
    return run_update(tmp_path, ['SPY'], '2024-12-01', '2025-02-01',
                      fetch=lambda *a: RawResponse(json.dumps(payload).encode(), 200))


def test_cache_readonly_and_corruption_removes_exports(monkeypatch, tmp_path):
    rid = cache(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    at = start(monkeypatch, tmp_path)
    at.radio(key='dm_mode').set_value('已下载缓存').run()
    assert at.selectbox(key='dm_run').value == rid
    assert compute(at) is not None
    assert {p: p.read_bytes() for p in before} == before
    manifest = tmp_path/'runs'/rid/'snapshot_manifest.json'
    content = json.loads(manifest.read_bytes())
    original_created = content['created_utc']
    content['created_utc'] = 'changed'
    manifest.write_text(json.dumps(content))
    at.run()
    assert at.session_state['dm_result'] is None
    assert not at.get('download_button')
    assert at.button(key='dm_compute').disabled
    content['created_utc'] = original_created
    manifest.write_text(json.dumps(content))
    at.run()
    at.selectbox(key='dm_run').set_value(rid).run()
    compute(at)
    raw = tmp_path/'runs'/rid/content['items'][0]['raw_file']
    raw.write_bytes(b'corrupt')
    at.run()
    assert at.session_state['dm_result'] is None
    assert not at.get('download_button')
    assert at.error
