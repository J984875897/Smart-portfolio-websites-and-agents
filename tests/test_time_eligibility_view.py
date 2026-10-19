from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

ROOT=Path(__file__).resolve().parents[1]

def start(monkeypatch,tmp_path):
    import socket
    monkeypatch.setattr(socket,'create_connection',lambda *a,**k:pytest.fail('network'))
    monkeypatch.setenv('PORTFOLIO_DOWNLOADS_ROOT',str(tmp_path))
    monkeypatch.setenv('PORTFOLIO_REFERENCE_DOWNLOADS_ROOT',str(tmp_path/'ref'))
    at=AppTest.from_file(str(ROOT/'app/main.py'),default_timeout=20).run()
    assert any('历史资格与来源' in option for option in at.selectbox(key='workspace_route').options)
    at.selectbox(key='workspace_route').set_value('history_sources').run()
    assert not at.exception
    return at

def test_no_c2_synthetic_boundary_and_invalidation(monkeypatch,tmp_path):
    at=start(monkeypatch,tmp_path)
    assert not at.get('download_button')
    original=at.session_state['bundle'].observations.copy(deep=True)
    at.radio(key='te_source').set_value('SYNTH 时间案例').run()
    assert not at.exception
    assert at.session_state['te_result'].rows.historical_observation_eligible.all()
    assert len(at.get('download_button'))==2
    at.text_input(key='te_decision').set_value('2025-02-01T23:59:59.999999Z').run()
    assert not at.session_state['te_result'].rows.historical_observation_eligible.any()
    at.text_input(key='te_decision').set_value('bad').run()
    assert at.session_state['te_result'] is None
    assert not at.get('download_button')
    assert at.session_state['bundle'].observations.equals(original)
    at.text_input(key='te_decision').set_value('0001-01-01T00:00:00+14:00').run()
    assert not at.exception and not at.get('download_button')

def test_previous_result_manual_evidence_only(monkeypatch,tmp_path):
    at=start(monkeypatch,tmp_path)
    at.selectbox(key='workspace_route').set_value('daily_hkd').run()
    at.checkbox(key='dh_price_confirm').check().run()
    at.checkbox(key='dh_fx_confirm').check().run()
    at.button(key='dh_compute').click().run()
    at.selectbox(key='workspace_route').set_value('history_sources').run()
    assert not at.exception
    assert not at.session_state['te_result'].rows.historical_observation_eligible.any()
    at.text_input(key='te_declaration').set_value('2025-02-01T00:00:00Z').run()
    assert at.session_state['te_result'].rows.time_status.tolist()==['declaration_only']

def test_cache_corruption_withdraws_result_and_exports(monkeypatch,tmp_path):
    from test_daily_monthly_view import cache
    from portfolio.data.monthly_cache import cached_monthly_prices
    from portfolio.data.daily_hkd import connect_daily_hkd
    from portfolio.data.daily_hkd_samples import sample_daily_fx
    from portfolio.data.snapshots import load_snapshot
    rid=cache(tmp_path)
    prices=cached_monthly_prices(tmp_path,rid,'SPY',start_month='2025-01',end_month='2025-01',confirmed=True)
    result=connect_daily_hkd(prices,sample_daily_fx('2025-01','2025-01'),fx_confirmed=True)
    at=start(monkeypatch,tmp_path)
    at.session_state['dh_result']=result
    before={p:p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    at.run()
    assert not at.exception and at.session_state['te_result'] is not None
    assert before=={p:p.read_bytes() for p in before}
    m=load_snapshot(tmp_path,rid)
    (tmp_path/'runs'/rid/m['items'][0]['raw_file']).write_bytes(b'corrupt')
    at.run()
    assert not at.exception and at.error
    assert at.session_state['te_result'] is None
    assert not at.get('download_button')
