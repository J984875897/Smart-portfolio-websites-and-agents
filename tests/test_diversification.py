"""Explicit-weight HKD annual risk calculations, independent of optimization."""
import json
import numpy as np
import pandas as pd
import pytest


def inputs():
    return (pd.Series({'A':.06,'B':.10}),
            pd.DataFrame([[.04,0],[0,.09]],index=['A','B'],columns=['A','B']),
            pd.Series({'A':.5,'B':.5}))


def risk(mu=None,cov=None,w=None,method='specified'):
    from portfolio.evaluation.diversification import portfolio_risk
    a,b,c=inputs()
    return portfolio_risk(a if mu is None else mu,b if cov is None else cov,c if w is None else w,
                          covariance_method=method)


def test_two_asset_hand_calculation_and_contribution_sum():
    r=risk();sigma=np.sqrt(.0325)
    assert r.metrics['mean_ann'] == pytest.approx(.08)
    assert r.metrics['variance_ann'] == pytest.approx(.0325)
    assert r.metrics['volatility_ann'] == pytest.approx(sigma)
    assert r.metrics['effective_holdings'] == pytest.approx(2)
    assert r.metrics['diversification_ratio'] == pytest.approx(.25/sigma)
    np.testing.assert_allclose(r.contributions.volatility_contribution_ann,[.01/sigma,.0225/sigma])
    assert r.contributions.volatility_contribution_ann.sum() == pytest.approx(sigma)
    assert r.contributions.risk_share.sum() == pytest.approx(1)
    assert r.diagnostics['covariance_method'] == 'specified'
    assert r.diagnostics['formal_portfolio'] is False
    json.dumps(r.metrics,allow_nan=False);json.dumps(r.diagnostics,allow_nan=False)


def test_twenty_equal_weights_and_completely_correlated_dr_one():
    ids=[f'A{i:02}' for i in range(20)]
    sigma=np.linspace(.1,.4,20)
    r=risk(pd.Series(.05,index=ids),pd.DataFrame(np.outer(sigma,sigma),index=ids,columns=ids),pd.Series(1/20,index=ids))
    assert r.metrics['effective_holdings'] == pytest.approx(20)
    assert r.metrics['diversification_ratio'] == pytest.approx(1)
    assert r.metrics['positive_weight_count'] == 20


def test_negative_contribution_is_preserved_and_correlation_reduces_risk():
    _,cov,w=inputs();cov.loc['A','B']=cov.loc['B','A']=-.03;w[:]=[.8,.2]
    r=risk(cov=cov,w=w)
    assert r.metrics['volatility_ann'] == pytest.approx(.14)
    assert r.contributions.loc['B','volatility_contribution_ann'] < 0
    assert r.contributions.volatility_contribution_ann.sum() == pytest.approx(.14)
    assert r.metrics['volatility_ann'] < risk(w=w).metrics['volatility_ann']


@pytest.mark.parametrize('cov_values', [[[0,0],[0,0]],[[1,-1],[-1,1]]])
def test_zero_portfolio_risk_is_unavailable_not_infinite(cov_values):
    _,cov,_=inputs();cov[:]=cov_values
    r=risk(cov=cov)
    assert r.metrics['volatility_ann'] == 0
    assert r.metrics['mean_ann'] == pytest.approx(.08)
    assert r.metrics['diversification_ratio'] is None
    assert r.contributions.volatility_contribution_ann.isna().all()
    assert r.contributions.risk_share.isna().all()
    assert r.diagnostics['risk_status'] == 'unavailable_zero_portfolio_volatility'
    json.dumps(r.metrics,allow_nan=False)


def test_zero_weight_and_tiny_positive_variance_are_preserved():
    _,cov,w=inputs();w[:]=[1,0]
    r=risk(cov=cov*1e-20,w=w)
    assert r.metrics['positive_weight_count'] == 1
    assert r.metrics['effective_holdings'] == 1
    assert r.metrics['volatility_ann'] > 0
    assert r.metrics['diversification_ratio'] == pytest.approx(1)
    assert r.contributions.loc['B','volatility_contribution_ann'] == 0


def test_id_alignment_reordering_and_no_mutation():
    mu,cov,w=inputs();before=cov.copy(deep=True)
    r=risk(mu,cov,w);other=risk(mu.iloc[::-1],cov.iloc[::-1,::-1],w.iloc[::-1])
    assert r.fingerprint == other.fingerprint
    pd.testing.assert_frame_equal(r.contributions,other.contributions)
    pd.testing.assert_frame_equal(cov,before)


@pytest.mark.parametrize('case',['negative_weight','sum_wrong','bool_weight','nan_weight','string_weight','extra_weight','missing_weight','duplicate_weight','mu_nan','mu_bool','mu_extra','duplicate_mu','cov_nan','cov_bool','cov_negative_diag','cov_asymmetric','cov_non_psd','cov_duplicate','cov_misaligned','unknown_method'])
def test_invalid_annual_inputs_fail_instead_of_normalizing(case):
    mu,cov,w=inputs();method='specified'
    if case=='negative_weight':w[:]=[1.1,-.1]
    elif case=='sum_wrong':w[:]=[.4,.4]
    elif case=='bool_weight':w=w.astype(object);w.iloc[0]=True
    elif case=='nan_weight':w.iloc[0]=np.nan
    elif case=='string_weight':w=w.astype(object);w.iloc[0]='0.5'
    elif case=='extra_weight':w['C']=0
    elif case=='missing_weight':w=w.iloc[:1]
    elif case=='duplicate_weight':w.index=['A','A']
    elif case=='mu_nan':mu.iloc[0]=np.nan
    elif case=='mu_bool':mu=mu.astype(object);mu.iloc[0]=True
    elif case=='mu_extra':mu['C']=.1
    elif case=='duplicate_mu':mu.index=['A','A']
    elif case=='cov_nan':cov.iloc[0,0]=np.nan
    elif case=='cov_bool':cov=cov.astype(object);cov.iloc[0,0]=True
    elif case=='cov_negative_diag':cov.iloc[0,0]=-.0000000000001
    elif case=='cov_asymmetric':cov.iloc[0,1]=.01
    elif case=='cov_non_psd':cov.loc['A','B']=cov.loc['B','A']=.1
    elif case=='cov_duplicate':cov.columns=['A','A']
    elif case=='cov_misaligned':cov.index=['A','C']
    elif case=='unknown_method':method='hidden'
    with pytest.raises(ValueError):risk(mu,cov,w,method)


def test_covariance_spectral_overflow_is_rejected_not_exported_as_infinity():
    _,cov,w=inputs();cov[:]=1e308;w[:]=[1,0]
    with pytest.raises(ValueError,match='covariance'):
        risk(cov=cov,w=w)


def test_covariance_method_must_be_a_supported_string():
    with pytest.raises(ValueError,match='covariance method'):
        risk(method=[])
