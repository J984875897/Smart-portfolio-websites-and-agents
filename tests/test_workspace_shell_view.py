from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def start(tmp_path, monkeypatch):
    monkeypatch.setenv('PORTFOLIO_IMPORTS_ROOT', str(tmp_path / 'imports'))
    return AppTest.from_file(str(ROOT / 'app/main.py'), default_timeout=30).run()


def test_home_is_default_and_has_clear_first_action(tmp_path, monkeypatch):
    at = start(tmp_path, monkeypatch)
    assert not at.exception
    assert at.session_state['workspace_route'] == 'overview'
    assert any('准备数据' in b.label for b in at.button)
    assert any('尚未打开数据版本' in x.value for x in at.info)


def test_demo_does_not_write_imported_bundle(tmp_path, monkeypatch):
    at = start(tmp_path, monkeypatch)
    at.button(key='overview_demo').click().run()
    assert not at.exception
    assert at.session_state['workspace_route'] == 'screen_candidates'
    assert at.radio(key='cs_source').value == 'SYNTH 相关性与风险演示'
    assert at.session_state['bundle'].assets.empty
    assert at.session_state['cs_result'] is None


@pytest.mark.parametrize('route,title', [('downloads','市场数据与缓存'), ('returns_window','收益与窗口核对'),
    ('history_sources','历史资格与来源'), ('rates_factors','利率与因子')])
def test_advanced_route_has_group_heading(tmp_path, monkeypatch, route, title):
    at = start(tmp_path, monkeypatch)
    at.selectbox(key='workspace_route').set_value(route).run()
    assert not at.exception
    assert any(title in x.value for x in list(at.title) + list(at.subheader))


def test_overview_explains_daily_blocker(tmp_path, monkeypatch):
    from portfolio.data.contracts import DataBundle
    import pandas as pd
    at = start(tmp_path, monkeypatch)
    at.session_state['bundle'] = DataBundle(assets=pd.DataFrame({'asset_id':['A']}), observations=pd.DataFrame({'frequency':['daily']}))
    at.session_state['bundle_version'] = 'daily'
    at.run()
    assert any('需要月度准备' in x.value for x in list(at.warning) + list(at.info))
    assert at.button(key='overview_next').label == '前往核对资格'


def test_real_daily_n0_overview_keeps_monthly_blocker(tmp_path, monkeypatch):
    import json
    from portfolio.data.contracts import DataBundle
    source = Path(json.loads((ROOT/'outputs/acceptance/S02/import_summary.json').read_text())['real_bundle_path'])
    at = start(tmp_path, monkeypatch)
    at.session_state['bundle'] = DataBundle.load(source)
    at.session_state['bundle_version'] = source.name
    at.button(key='nav_screen_candidates').click().run()
    at.radio(key='cs_source').set_value('当前已打开导入版本').run()
    at.button(key='cs_compute').click().run()
    assert at.session_state['cs_result'].cardinality.n == 0
    at.button(key='nav_overview').click().run()
    messages = list(at.info) + list(at.warning) + list(at.error)
    assert any('需要月度准备' in x.value for x in messages)
    assert any('N = 0' in x.value for x in messages)
    assert at.session_state['ra_preview'] is None


def test_stage_can_return_home_without_opening_sidebar(tmp_path, monkeypatch):
    at = start(tmp_path, monkeypatch)
    at.button(key='overview_next').click().run()
    assert at.session_state['workspace_route'] == 'prepare_data'
    at.button(key='page_back_overview').click().run()
    assert not at.exception
    assert at.session_state['workspace_route'] == 'overview'
    assert at.session_state['bundle'].assets.empty
