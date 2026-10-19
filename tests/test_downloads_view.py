from pathlib import Path
import copy
import json
from datetime import date
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]

def start(monkeypatch, tmp_path):
    monkeypatch.setenv('PORTFOLIO_DOWNLOADS_ROOT', str(tmp_path))
    at = AppTest.from_file(str(ROOT / 'app/main.py'), default_timeout=15).run()
    at.selectbox(key='workspace_route').set_value('downloads').run()
    assert not at.exception
    return at

def click(at, key):
    at.button(key=key).click().run()
    assert not at.exception

def test_no_auto_download(monkeypatch, tmp_path):
    import app.views.downloads as view
    monkeypatch.setattr(view, 'run_update', lambda *a, **k: (_ for _ in ()).throw(AssertionError('unexpected download')))
    at = start(monkeypatch, tmp_path)
    click(at, 'dl_prepare')
    assert at.session_state['dl_plan']['symbols'] == ('SPY', '2800.HK')
    click(at, 'dl_cancel')
    assert at.session_state['dl_plan'] is None
    click(at, 'dl_prepare')
    at.date_input(key='dl_end').set_value(date(2025, 3, 1)).run()
    assert at.session_state['dl_plan'] is None


def cached(tmp_path):
    from portfolio.data.updates import run_update
    from portfolio.data.providers.base import RawResponse
    from portfolio.data.providers.yahoo import CATALOG
    from portfolio.data.snapshots import list_runs, load_snapshot
    chart = json.loads((ROOT / 'tests/fixtures/source_responses/yahoo_chart.json').read_bytes())
    def fetch(symbol, *args):
        if symbol == 'SPY':
            return RawResponse(b'limited', 429)
        payload = copy.deepcopy(chart)
        identity = CATALOG[symbol]
        payload['chart']['result'][0]['meta'].update(symbol=symbol, currency=identity['currency'], instrumentType=identity['provider_type'])
        if symbol == 'AAPL':
            payload['chart']['result'][0]['indicators']['quote'][0]['close'][0] = None
        return RawResponse(json.dumps(payload).encode(), 200)
    run_update(tmp_path, ['SPY', '2800.HK', 'HKD=X', 'AAPL'], '2025-01-01', '2025-02-01', fetch=fetch)
    return [(run, load_snapshot(tmp_path, run)) for run in list_runs(tmp_path)]


def test_explicit_update_and_failed_update_preserves_active(monkeypatch, tmp_path):
    import app.views.downloads as view
    runs = cached(tmp_path)
    calls = []
    def update(*a, **k):
        calls.append((a,k))
        return runs[0][0]
    monkeypatch.setattr(view, 'run_update', update)
    at = start(monkeypatch, tmp_path)
    click(at, 'dl_open')
    active = at.session_state['dl_active']
    click(at, 'dl_prepare')
    assert not calls
    click(at, 'dl_start')
    assert len(calls) == 1
    assert at.session_state['dl_result']['run_id'] == runs[0][0]
    assert at.session_state['dl_active'] == active
    def fail(*a, **k):
        raise OSError('SECRET must not display')
    monkeypatch.setattr(view, 'run_update', fail)
    click(at, 'dl_prepare')
    click(at, 'dl_start')
    assert at.session_state['dl_active'] == active
    assert 'SECRET' not in str([e.value for e in at.error])


def test_offline_open_corrupt_handoff_and_fx(monkeypatch, tmp_path):
    import app.views.downloads as view
    runs = cached(tmp_path)
    mixed = next(run for run, m in runs if any(i['symbol'] == 'HKD=X' for i in m['items']))
    monkeypatch.setattr(view, 'run_update', lambda *a, **k: (_ for _ in ()).throw(AssertionError('network')))
    at = start(monkeypatch, tmp_path)
    at.selectbox(key='dl_run').set_value(mixed).run()
    click(at, 'dl_open')
    assert any('不可用' in str(df.value) for df in at.dataframe)
    assert any('部分可用' in str(df.value) for df in at.dataframe)
    assert {'dl_log', 'dl_manifest', 'dl_daily', 'dl_import_csv'} <= {e.key for e in at.get('download_button')}
    at.selectbox(key='dl_symbol').set_value('HKD=X').run()
    assert not any(b.key == 'dl_to_import' for b in at.button)
    at.selectbox(key='dl_symbol').set_value('2800.HK').run()
    manifest = at.session_state['dl_active']['manifest']
    item = next(i for i in manifest['items'] if i['symbol'] == '2800.HK')
    from portfolio.data.snapshots import read_artifact
    expected = read_artifact(tmp_path, mixed, item['import_file'])
    original = at.session_state['bundle']
    at.session_state['upload_token'] = ('old.csv', 'old')
    at.session_state['upload'] = b'old'
    at.session_state['default_asset_id'] = 'stale'
    at.session_state['default_share_class'] = 'stale'
    at.session_state['date_format'] = '%d/%m/%Y'
    click(at, 'dl_to_import')
    assert at.session_state['workspace_route'] == 'prepare_data'
    assert at.session_state['default_asset_id'] == ''
    assert at.session_state['default_share_class'] == ''
    assert at.session_state['date_format'] == '%Y-%m-%d'
    assert at.session_state['kind'] == 'adjusted_price'
    assert at.session_state['unit'] == 'decimal'
    assert mixed in at.session_state['source'][1]
    assert 'Yahoo chart' in at.session_state['supplier']
    assert at.session_state['supplier'] == f"Yahoo chart / {mixed} / raw sha256 {item['raw_sha256']}"
    assert at.session_state['source'][0] == expected
    assert len(at.session_state['bundle'].assets) == len(original.assets)
    assert 'adj_close' not in at.session_state['source'][0].decode().splitlines()[0]
    assert 'value' in at.session_state['source'][0].decode().splitlines()[0]
    at.run()
    assert mixed in at.session_state['source'][1]
    at.selectbox(key='workspace_route').set_value('downloads').run()
    active = at.session_state['dl_active']
    manifest = active['manifest']
    artifact = tmp_path / 'runs' / mixed / manifest['files'][0]['path']
    artifact.write_bytes(b'corrupt')
    at.selectbox(key='dl_run').set_value(mixed).run()
    click(at, 'dl_open')
    assert at.session_state['dl_active'] == active
    assert at.error


def test_failed_run_does_not_replace_usable_cache(monkeypatch, tmp_path):
    from portfolio.data.updates import run_update
    from portfolio.data.providers.base import RawResponse
    cached(tmp_path)
    at = start(monkeypatch, tmp_path)
    click(at, 'dl_open')
    active = at.session_state['dl_active']
    failed = run_update(tmp_path, ['SPY'], '2025-01-01', '2025-02-01', fetch=lambda *a: RawResponse(b'limited', 429))
    at.run()
    at.selectbox(key='dl_run').set_value(failed).run()
    click(at, 'dl_open')
    assert at.session_state['dl_active'] == active
    assert at.session_state['dl_result']['run_id'] == failed


def test_partial_diagnostics_mixed_and_all_partial(monkeypatch, tmp_path):
    from portfolio.data.snapshots import read_artifact
    from portfolio.data.updates import run_update
    from portfolio.data.providers.base import RawResponse
    runs = cached(tmp_path)
    mixed, manifest = runs[0]
    at = start(monkeypatch, tmp_path)
    click(at, 'dl_open')
    active = at.session_state['dl_active']
    assert 'AAPL' not in at.selectbox(key='dl_symbol').options
    assert any(e.key == 'dl_active_diag_daily_AAPL' for e in at.get('download_button'))
    partial = next(i for i in manifest['items'] if i['symbol'] == 'AAPL')
    daily = read_artifact(tmp_path, mixed, partial['daily_file'])
    assert any(df.value['close'].isna().any() for df in at.dataframe if 'close' in df.value)
    # Capture real download arguments, including exact stored bytes and manifest metadata.
    import app.views.downloads as view
    captured = {}
    original = view.st.download_button
    def capture(label, data, *args, **kwargs):
        captured[kwargs.get('key')] = data
        return original(label, data, *args, **kwargs)
    monkeypatch.setattr(view.st, 'download_button', capture)
    at.run()
    assert captured['dl_active_diag_daily_AAPL'] == daily
    exported = json.loads(captured['dl_manifest'])
    assert exported['provider_endpoint_version'] == 'v8'
    assert exported['adapter_version'] == 'yahoo-chart-v1'
    assert exported['client_versions'] == manifest['client_versions']
    at.session_state['dl_result'] = manifest
    at.run()
    assert len([e for e in at.get('download_button') if '_diag_daily_' in str(e.key)]) == 1
    chart = json.loads((ROOT/'tests/fixtures/source_responses/yahoo_chart.json').read_bytes())
    chart['chart']['result'][0]['meta']['symbol'] = 'SPY'
    chart['chart']['result'][0]['indicators']['quote'][0]['close'][0] = None
    rid = run_update(tmp_path, ['SPY'], '2025-01-01', '2025-02-01', fetch=lambda *a: RawResponse(json.dumps(chart).encode(), 200))
    at.run()
    at.selectbox(key='dl_run').set_value(rid).run()
    click(at, 'dl_open')
    assert at.session_state['dl_active'] == active
    assert at.session_state['dl_result']['run_id'] == rid
    assert any(e.key == 'dl_result_diag_daily_SPY' for e in at.get('download_button'))
    assert not any('diag' in str(b.key) for b in at.button)
    # Changed result manifests and corrupt daily files cannot be exported.
    at.session_state['dl_result'] = {**at.session_state['dl_result'], 'created_utc': 'changed'}
    at.run()
    assert not any(e.key == 'dl_result_diag_daily_SPY' for e in at.get('download_button'))
    at.session_state['dl_result'] = __import__('portfolio.data.snapshots', fromlist=['load_snapshot']).load_snapshot(tmp_path, rid)
    item = at.session_state['dl_result']['items'][0]
    (tmp_path/'runs'/rid/item['daily_file']).write_bytes(b'corrupt')
    at.run()
    assert not any(e.key == 'dl_result_diag_daily_SPY' for e in at.get('download_button'))
