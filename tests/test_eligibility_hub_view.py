from tests.test_workspace_shell_view import start


def test_eligibility_hub_links_to_existing_checks(tmp_path, monkeypatch):
    at = start(tmp_path, monkeypatch)
    at.selectbox(key='workspace_route').set_value('eligibility').run()
    assert not at.exception
    labels = [b.label for b in at.button]
    for label in ['核对日线月度','核对港币收益','核对共同窗口','核对历史资格']:
        assert label in labels
    at.button(key='eligibility_alignment').click().run()
    assert not at.exception
    assert at.session_state['workspace'] == '共同窗口查验'


def test_risk_route_and_roundtrip_keep_research_inputs(tmp_path, monkeypatch):
    at = start(tmp_path, monkeypatch)
    at.button(key='overview_demo').click().run()
    at.number_input(key='cs_k').set_value(20).run()
    at.button(key='cs_compute').click().run()
    assert not any(b.key == 'ra_compute' for b in at.button)
    fp = at.session_state['cs_result'].fingerprint
    at.button(key='cs_to_risk').click().run()
    assert not at.exception
    assert at.button(key='ra_compute').label == '计算收益与风险'
    assert at.number_input(key='cs_k').value == 20
    assert at.session_state['cs_result'].fingerprint == fp
    at.button(key='ra_compute').click().run(timeout=60)
    risk_fp = at.session_state['ra_preview'].fingerprint
    assert any('研究预览已完成' in x.value for x in at.success)
    at.button(key='nav_overview').click().run()
    assert at.session_state['cs_k'] == 20
    assert at.button(key='overview_next').label == '前往收益与风险'
    at.button(key='overview_next').click().run()
    assert not at.exception
    assert at.session_state['ra_preview'].fingerprint == risk_fp
    at.number_input(key='cs_k').set_value(30).run()
    assert at.session_state['ra_preview'] is None


def test_all_routes_render_offline(tmp_path, monkeypatch):
    import socket
    from app.views.workspace_shell import ROUTES
    monkeypatch.setattr(socket, 'create_connection', lambda *a, **k: (_ for _ in ()).throw(AssertionError('network')))
    at = start(tmp_path, monkeypatch)
    for route in ROUTES:
        at.selectbox(key='workspace_route').set_value(route).run()
        assert not at.exception, route


def test_uploaded_weights_survive_overview_roundtrip(tmp_path, monkeypatch):
    from io import BytesIO
    import streamlit as st
    from tests.test_risk_workspace_view import compute, risk_compute
    from tests.test_candidate_screening_view import start as screening_start
    selected = {}
    original = st.file_uploader
    def uploader(*args, **kwargs):
        if kwargs.get('key', '').startswith('ra_weights_'):
            return selected.get('file')
        return original(*args, **kwargs)
    monkeypatch.setattr(st, 'file_uploader', uploader)
    at = compute(screening_start(tmp_path, monkeypatch))
    at.radio(key='ra_weight_mode').set_value('上传自定义多头权重 CSV').run()
    ids = at.session_state['cs_result'].eligible_asset_ids
    file = BytesIO(('asset_id,weight\n'+'\n'.join(f'{aid},0.01' for aid in ids)).encode())
    file.name = 'custom_weights.csv'
    selected['file'] = file
    at.run(); risk_compute(at)
    fp = at.session_state['ra_preview'].fingerprint
    at.button(key='nav_overview').click().run()
    # Streamlit cleans unmounted upload widgets when another page is shown.
    selected.clear()
    at.button(key='nav_risk_preview').click().run()
    assert not at.exception
    assert at.session_state['ra_preview'] is not None
    assert at.session_state['ra_preview'].fingerprint == fp
    assert any('custom_weights.csv' in x.value for x in at.caption)
    at.button(key='clear_retained_ra_weights').click().run()
    assert at.session_state['ra_preview'] is None
    assert at.button(key='ra_compute').disabled
