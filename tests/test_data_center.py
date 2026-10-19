from pathlib import Path
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]

def start(tmp_path, monkeypatch):
    monkeypatch.setenv('PORTFOLIO_IMPORTS_ROOT', str(tmp_path / 'imports'))
    assert (ROOT / 'app/main.py').exists(), 'S02 UI entry point is missing'
    at = AppTest.from_file(str(ROOT / 'app/main.py'), default_timeout=15).run()
    return at.selectbox(key='workspace_route').set_value('prepare_data').run()

def click(at, key):
    at.button(key=key).click().run()
    assert not at.exception
    return at

def load(at, sample='ten_products.csv'):
    at.selectbox(key='sample').set_value(sample).run()
    return click(at, 'load_sample')

def test_empty_and_preview_commit_dedup(tmp_path, monkeypatch):
    at = start(tmp_path, monkeypatch)
    assert not at.exception
    assert len(at.session_state['bundle'].assets) == 0
    load(at)
    click(at, 'check')
    assert len(at.session_state['bundle'].assets) == 0
    assert len(at.session_state['preview'].rows) == 10
    click(at, 'commit')
    assert len(at.session_state['bundle'].assets) == 10
    load(at, 'repeated_two.csv')
    click(at, 'check')
    click(at, 'commit')
    assert len(at.session_state['bundle'].assets) == 10
    assert len(at.session_state['bundle'].observations) == 10

def test_config_change_invalidates_preview(tmp_path, monkeypatch):
    at = load(start(tmp_path, monkeypatch))
    click(at, 'check')
    at.text_input(key='supplier').set_value('Changed').run()
    assert at.session_state['preview'] is None
    assert not any(b.key == 'commit' for b in at.button)

def test_dirty_ack_and_classification_audit(tmp_path, monkeypatch):
    at = load(start(tmp_path, monkeypatch), 'dirty_data.csv')
    click(at, 'check')
    assert at.session_state['preview'].counts['blocked'] > 0
    assert at.session_state['preview'].counts['review'] > 0
    assert not at.checkbox(key='ack').value
    at.checkbox(key='ack').check().run()
    click(at, 'commit')
    assert len(at.session_state['bundle'].observations) == 1
    assert at.session_state['bundle'].observations.iloc[0]['value'] == .7
    load(at)
    click(at, 'check')
    at.selectbox(key='override_asset').set_value('p0').run()
    at.selectbox(key='override_class').set_value('mixed').run()
    click(at, 'apply_override')
    assert at.session_state['preview'] is None
    click(at, 'check')
    click(at, 'commit')
    assert len(at.session_state['bundle'].classification_history) > 0

def test_fresh_session_loads_disk_version(tmp_path, monkeypatch):
    at = load(start(tmp_path, monkeypatch))
    click(at, 'check')
    click(at, 'commit')
    fresh = start(tmp_path, monkeypatch)
    assert len(fresh.session_state['bundle'].assets) == 0
    click(fresh, 'load_version')
    assert len(fresh.session_state['bundle'].assets) == 10
    assert any(fresh.session_state['bundle_version'] in x.value for x in fresh.warning)

def test_missing_value_mapping_blocks_rows(tmp_path, monkeypatch):
    at = load(start(tmp_path, monkeypatch))
    at.selectbox(key='map_value').set_value('').run()
    click(at, 'check')
    assert at.session_state['preview'].counts['blocked'] == 10
    assert at.button(key='commit').disabled

def test_manual_alias_and_invalidation(tmp_path, monkeypatch):
    at = load(start(tmp_path, monkeypatch))
    click(at, 'check')
    click(at, 'commit')
    load(at, 'repeated_two.csv')
    payload, filename, synthetic = at.session_state['source']
    at.session_state['source'] = (payload.replace(b'0000', b'ALT'), filename, synthetic)
    at.run()
    at.selectbox(key='map_asset_id').set_value('').run()
    click(at, 'check')
    assert at.session_state['preview'].rows.iloc[0]['asset_id'] != 'p0'
    at.text_input(key='alias_ticker').set_value('ALT').run()
    at.text_input(key='alias_exchange').set_value('HKEX').run()
    at.selectbox(key='alias_currency').set_value('HKD').run()
    at.selectbox(key='alias_target').set_value('p0').run()
    click(at, 'apply_alias')
    assert at.session_state['preview'] is None
    assert at.session_state['alias_map'][('SYNTH','HKEX','ALT','','HKD')] == 'p0'
    click(at, 'check')
    assert at.session_state['preview'].counts.get('blocked', 0) == 0
    click(at, 'commit')
    assert len(at.session_state['bundle'].assets) == 10
    assert 'ALT' in at.session_state['bundle'].aliases['ticker'].tolist()

def test_save_error_preserves_prior_bundle(tmp_path, monkeypatch):
    from portfolio.data import DataBundle
    at = load(start(tmp_path, monkeypatch))
    click(at, 'check')
    def fail_save(self, path):
        raise PermissionError('read-only directory')
    monkeypatch.setattr(DataBundle, 'save', fail_save)
    click(at, 'commit')
    assert len(at.session_state['bundle'].assets) == 0
    assert at.session_state['preview'] is not None
    assert any('保存失败' in err.value for err in at.error)

def test_units_mapping_and_source_change_clear_ack(tmp_path, monkeypatch):
    at = load(start(tmp_path, monkeypatch), 'dirty_data.csv')
    click(at, 'check')
    at.checkbox(key='ack').check().run()
    at.selectbox(key='unit').set_value('decimal').run()
    assert at.session_state['preview'] is None
    assert not at.session_state['ack']
    at.selectbox(key='unit').set_value('percent').run()
    click(at, 'check')
    assert not at.checkbox(key='ack').value
    at.checkbox(key='ack').check().run()
    at.selectbox(key='map_value').set_value('').run()
    assert at.session_state['preview'] is None
    assert not at.session_state['ack']
    load(at, 'ten_products.csv')
    assert at.session_state['preview'] is None
    assert not at.session_state['ack']

def test_corrupt_load_preserves_current_bundle(tmp_path, monkeypatch):
    at = load(start(tmp_path, monkeypatch))
    click(at, 'check')
    click(at, 'commit')
    version = at.session_state['bundle_version']
    observations = tmp_path / 'imports' / version / 'observations.csv'
    observations.write_bytes(observations.read_bytes() + b'corrupt')
    at.run()
    click(at, 'load_version')
    assert len(at.session_state['bundle'].assets) == 10
    assert at.session_state['bundle_version'] == version
    assert any('无法打开版本' in err.value for err in at.error)

def test_empty_supplier_is_scoped_error(tmp_path, monkeypatch):
    at = load(start(tmp_path, monkeypatch))
    click(at, 'check')
    at.text_input(key='supplier').set_value('').run()
    assert not at.exception
    assert at.session_state['preview'] is None
    assert any('来源名称' in err.value for err in at.error)

def test_only_economic_override_preserves_tool_type(tmp_path, monkeypatch):
    at = load(start(tmp_path, monkeypatch))
    click(at, 'check')
    assert at.selectbox(key='override_type').value == ''
    at.selectbox(key='override_class').set_value('mixed').run()
    click(at, 'apply_override')
    assert at.session_state['overrides']['p0'] == {'asset_class':'mixed'}
    click(at, 'check')
    click(at, 'commit')
    product = at.session_state['bundle'].assets.set_index('asset_id').loc['p0']
    assert product['tool_type'] == 'ETF'
    assert product['asset_class'] == 'mixed'

def test_corrupt_xlsx_shows_scoped_error(tmp_path, monkeypatch):
    at = start(tmp_path, monkeypatch)
    at.session_state['source'] = (b'not-a-workbook', 'bad.xlsx', False)
    at.run()
    assert not at.exception
    assert at.error

def test_identical_upload_reselection_after_sample(tmp_path, monkeypatch):
    from io import BytesIO
    import streamlit

    # AppTest cannot select browser files; mock only the uploader response.
    uploaded = BytesIO((ROOT / 'tests/fixtures/imports/ten_products.csv').read_bytes())
    uploaded.name = 'user.csv'
    selection = {'file': uploaded}
    monkeypatch.setattr(streamlit, 'file_uploader', lambda *args, **kwargs: selection['file'])
    at = start(tmp_path, monkeypatch)
    assert not at.exception
    assert at.session_state['source'][1] == 'user.csv'
    assert any('来源文件：user.csv' in item.value for item in at.caption)
    assert at.selectbox(key='kind').value == 'price'
    assert at.selectbox(key='unit').value == 'decimal'

    load(at, 'dirty_data.csv')
    at.run()  # The unchanged mounted upload must not override the sample.
    assert at.session_state['source'][1] == 'SYNTH_dirty_data.csv'
    click(at, 'check')
    at.checkbox(key='ack').check().run()
    assert at.session_state['preview'] is not None
    assert at.session_state['ack']

    selection['file'] = None
    at.run()
    assert not at.exception
    assert at.session_state['source'][1] == 'SYNTH_dirty_data.csv'
    assert at.session_state['preview'] is not None
    assert at.session_state['ack']

    selection['file'] = uploaded  # Identical name and bytes, deliberately reselected.
    at.run()
    assert not at.exception
    assert at.session_state['source'][1] == 'user.csv'
    assert any('来源文件：user.csv' in item.value for item in at.caption)
    assert not any('来源文件：SYNTH_' in item.value for item in at.caption)
    assert at.session_state['preview'] is None
    assert not at.session_state['ack']
    assert not any(b.key == 'commit' for b in at.button)
    assert at.selectbox(key='kind').value == 'price'
    assert at.selectbox(key='unit').value == 'decimal'
