"""Research preview re-enters S05, retains evidence, and distinguishes risk methods."""
from copy import deepcopy
import numpy as np
import pandas as pd
import pytest
from portfolio.universe.inputs import prepare_candidate_input
from portfolio.universe.screening_samples import sample_screening_inputs


def inputs(vary=False):
    bundle,fx,timing,structures=sample_screening_inputs()
    if vary:
        bundle.observations['value']=np.random.default_rng(5052).normal(.005,.04,len(bundle.observations))
        # A zero-volatility series in a nondegenerate universe exposes the model/empirical difference.
        bundle.observations.loc[bundle.observations.asset_id == 'SYNTH_SCREEN_000','value']=.01
    c=prepare_candidate_input(bundle,fx,timing,structures,end_month='2025-01',decision_at='2025-02-01T06:00:00+08:00')
    return c,pd.Series(.01,index=c.matrix.columns)


def test_constant_universe_returns_unavailable_not_infinite():
    from portfolio.evaluation.risk_preview import preview_candidate_risk
    c,w=inputs();r=preview_candidate_risk(c,w,k=30)
    assert r.correlation.matrix.isna().all().all()
    assert r.sample_risk.metrics['volatility_ann'] == 0
    assert r.sample_risk.metrics['diversification_ratio'] is None
    assert r.model_risk.metrics['diversification_ratio'] is None
    assert r.evidence['historical_universe_certified'] is False
    assert r.evidence['portfolio_constructed'] is False
    assert r.evidence['preview_kind'] == 'specified_long_only_weights_not_selected_members'
    assert r.evidence['target_k'] == 30 and r.evidence['positive_weight_count'] == 100


def test_nonconstant_sample_and_model_are_distinct_bound_and_unchanged():
    from portfolio.evaluation.risk_preview import preview_candidate_risk
    c,w=inputs(True);before=deepcopy(c);r=preview_candidate_risk(c,w,k=30)
    aid='SYNTH_SCREEN_000'
    assert r.sample_risk.contributions.loc[aid,'asset_volatility_ann'] == 0
    assert r.model_risk.contributions.loc[aid,'asset_volatility_ann'] > 0
    assert r.correlation.matrix[aid].isna().all()
    assert r.sample_risk.diagnostics['covariance_method'] == 'sample'
    assert r.model_risk.diagnostics['covariance_method'] == 'ledoit_wolf'
    assert r.sample_risk.metrics['mean_ann'] == r.model_risk.metrics['mean_ann']
    assert r.sample_risk.metrics['volatility_ann'] != r.model_risk.metrics['volatility_ann']
    pd.testing.assert_frame_equal(c.matrix,before.matrix)
    r.evidence['inputs']['timing']['rows']=-1
    assert c.evidence['inputs']['timing']['rows'] != -1
    other=preview_candidate_risk(c,w.iloc[::-1],k=30)
    assert r.fingerprint == other.fingerprint


def test_count_failure_is_not_bypassed_by_preview():
    from portfolio.evaluation.risk_preview import preview_candidate_risk
    c,w=inputs()
    with pytest.raises(ValueError,match='候选产品池'):
        preview_candidate_risk(c,w,k=30,excluded_asset_ids=['SYNTH_SCREEN_099'])


def test_weights_must_explicitly_bind_all_qualified_ids():
    from portfolio.evaluation.risk_preview import preview_candidate_risk
    c,w=inputs(True)
    with pytest.raises(ValueError,match='weights'):
        preview_candidate_risk(c,w.iloc[:-1],k=30)
    w[:]=0;w.iloc[:2]=.5
    r=preview_candidate_risk(c,w,k=30)
    assert r.sample_risk.metrics['positive_weight_count'] == 2
    assert r.evidence['portfolio_constructed'] is False
