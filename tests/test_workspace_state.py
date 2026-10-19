from types import SimpleNamespace as NS
import pandas as pd
from app.views.workspace_state import next_step, workspace_snapshot


def result(n=100, status='passed'):
    return NS(cardinality=NS(n=n, k=30, status=status, minimum_n=100), fingerprint='screen')


def test_empty_state_recommends_prepare_without_mutation():
    state = {'bundle_version': 'empty'}
    assert next_step(workspace_snapshot(state)).route == 'prepare_data'
    assert state == {'bundle_version': 'empty'}


def test_n_zero_is_blocked_and_actionable():
    snap = workspace_snapshot({'cs_result': result(0, 'pool_too_small')})
    assert snap.candidates.tone == 'blocked'
    assert '100' in snap.candidates.detail
    assert snap.risk.tone != 'ready'
    assert next_step(snap).route == 'screen_candidates'


def test_synth_passed_pool_can_continue_without_imported_data():
    snap = workspace_snapshot({'cs_result': result()})
    assert next_step(snap).route == 'risk_preview'
    assert snap.candidates.tone == 'ready'
    assert '未认证' in snap.candidates.detail


def test_risk_requires_current_matching_input_token():
    state = {'cs_result': result(), 'ra_preview': object(), 'ra_result_token': 'old', 'ra_input_token': 'new'}
    assert workspace_snapshot(state).risk.tone != 'ready'
    state['ra_result_token'] = 'new'
    assert workspace_snapshot(state).risk.tone == 'ready'


def test_daily_data_needs_monthly_preparation():
    bundle = NS(assets=pd.DataFrame({'asset_id': ['A']}), observations=pd.DataFrame({'frequency': ['daily']}))
    snap = workspace_snapshot({'bundle': bundle, 'bundle_version': 'real-v1'})
    assert next_step(snap).route == 'eligibility'
    assert '需要月度准备' in next_step(snap).detail


def test_new_real_version_does_not_show_old_success():
    snap = workspace_snapshot({'bundle_version': 'new', 'cs_source': '当前已打开导入版本',
                               'cs_previous_source': ('当前已打开导入版本', 'old'), 'cs_result': result()})
    assert snap.candidates.tone != 'ready'
