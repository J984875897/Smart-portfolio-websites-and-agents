"""Independent mathematical checks for HKD training-window estimates."""
import json

import numpy as np
import pandas as pd
import pytest


def hand_input():
    x = pd.DataFrame({'A': [.01,.03,.02], 'B': [.03,.05,.04], 'C': [0,.01,.02]},
                     index=['2024-01-31','2024-02-29','2024-03-31'])
    return x, pd.Series({'A':'equity','B':'equity','C':'bond'})


def estimate(x=None, classes=None, **options):
    from portfolio.models.moments import estimate_moments
    default_x, default_classes = hand_input()
    return estimate_moments(default_x if x is None else x,
                            default_classes if classes is None else classes,
                            **(dict(train_start='2024-01',train_end='2024-03') | options))


def test_hand_means_covariance_and_annualization():
    r = estimate()
    assert r.asset_ids == ('A','B','C')
    np.testing.assert_allclose(r.summary.historical_mean_month, [.02,.04,.01])
    np.testing.assert_allclose(r.summary.class_mean_month, [.03,.03,.01])
    np.testing.assert_allclose(r.summary.estimated_mean_month, [.025,.035,.01])
    np.testing.assert_allclose(r.summary.estimated_mean_ann, [.30,.42,.12])
    expected = np.array([[.0001,.0001,.00005],[.0001,.0001,.00005],[.00005,.00005,.0001]])
    np.testing.assert_allclose(r.sample_cov_month, expected, atol=1e-18)
    np.testing.assert_allclose(r.sample_cov_ann, 12*expected)
    np.testing.assert_allclose(r.shrunk_cov_ann, 12*r.shrunk_cov_month)
    np.testing.assert_allclose(r.summary.sample_vol_ann, np.sqrt(12*np.diag(expected)))
    assert list(r.summary.class_members) == [2,2,1]
    assert r.diagnostics['singleton_classes'] == ['bond']
    assert r.diagnostics['n_observations'] == 3
    assert r.diagnostics['sample_covariance_ddof'] == 1
    assert r.diagnostics['shrinkage_empirical_ddof'] == 0
    for frame in [r.sample_cov_month,r.sample_cov_ann,r.shrunk_cov_month,r.shrunk_cov_ann]:
        assert list(frame.index) == list(frame.columns) == list(r.asset_ids)
    json.dumps(r.diagnostics,allow_nan=False)


def test_ledoit_wolf_against_independent_fourth_moment_formula():
    x, _ = hand_input(); r = estimate()
    z = x.to_numpy() - x.to_numpy().mean(axis=0)
    t,p = z.shape
    empirical = z.T @ z/t
    target_scale = np.trace(empirical)/p
    delta = np.square(empirical-target_scale*np.eye(p)).sum()/p
    beta = (np.square(z).T @ np.square(z)/t - np.square(empirical)).sum()/(p*t)
    alpha = min(beta,delta)/delta
    expected = (1-alpha)*empirical + alpha*target_scale*np.eye(p)
    assert r.diagnostics['shrinkage_coefficient'] == pytest.approx(alpha)
    np.testing.assert_allclose(r.shrunk_cov_month, expected,atol=1e-18)
    assert not np.allclose(r.sample_cov_month, empirical,atol=1e-15)


def test_only_training_values_determine_estimates_and_fingerprint():
    x,c = hand_input(); baseline = estimate(x,c)
    # Object dtype induced by unusable future values must not affect training.
    future = pd.DataFrame({'A':['not a training return'], 'B':[True], 'C':[np.inf]},index=['2024-04-30'])
    extended = pd.concat([x,future])
    r = estimate(extended,c)
    pd.testing.assert_frame_equal(r.summary,baseline.summary)
    pd.testing.assert_frame_equal(r.shrunk_cov_ann,baseline.shrunk_cov_ann)
    assert r.fingerprint == baseline.fingerprint
    assert r.diagnostics == baseline.diagnostics
    assert r.evidence == {}


def test_reorder_is_invariant_and_input_is_unchanged():
    x,c = hand_input(); before=x.copy(deep=True); bc=c.copy(deep=True)
    r=estimate(x,c); reordered=estimate(x[['C','B','A']].iloc[::-1],c.iloc[::-1])
    assert r.fingerprint == reordered.fingerprint
    pd.testing.assert_frame_equal(r.summary,reordered.summary)
    pd.testing.assert_frame_equal(r.shrunk_cov_month,reordered.shrunk_cov_month)
    pd.testing.assert_frame_equal(x,before); pd.testing.assert_series_equal(c,bc)


def test_sixty_months_one_hundred_assets_have_explicit_rank_and_shrinkage():
    rng = np.random.default_rng(5052)
    x = pd.DataFrame(rng.normal(.005,.04,(60,100)),
                     index=pd.period_range('2020-02','2025-01',freq='M').to_timestamp('M').strftime('%Y-%m-%d'),
                     columns=[f'A{i:03}' for i in range(100)])
    r = estimate(x,pd.Series('equity',index=x.columns),train_start='2020-02',train_end='2025-01')
    assert r.shrunk_cov_month.shape == (100,100)
    assert r.diagnostics['sample_covariance']['rank'] <= 59
    assert 0 < r.diagnostics['shrinkage_coefficient'] <= 1
    assert r.diagnostics['shrunk_covariance']['min_eigenvalue'] > 0
    assert r.diagnostics['usable_for_optimization'] is True


@pytest.mark.parametrize('values,constant', [([.01,.01,.01],True),([0,0,0],True),([0,.01,.02],False)])
def test_single_asset_and_degenerate_case(values,constant):
    x,_=hand_input();x=x[['A']];x['A']=values
    r=estimate(x,pd.Series({'A':'equity'}))
    assert r.diagnostics['constant_assets'] == (['A'] if constant else [])
    assert r.diagnostics['usable_for_optimization'] is (not constant)
    assert r.sample_cov_month.shape == (1,1)
    if constant:
        assert r.summary.loc['A','sample_vol_ann'] == 0
        assert r.shrunk_cov_month.iloc[0,0] == 0
    json.dumps(r.diagnostics,allow_nan=False)


def test_constant_empirical_volatility_is_not_replaced_by_model_volatility():
    x,c=hand_input();x['A']=.01
    r=estimate(x,c)
    assert r.summary.loc['A','sample_vol_ann'] == 0
    assert r.summary.loc['A','shrunk_vol_ann'] > 0
    assert r.diagnostics['constant_assets'] == ['A']
    assert 'constant_series_model_variance' in r.diagnostics['warnings']


@pytest.mark.parametrize('value', [np.nan,np.inf,-np.inf,-1.01,True,'0.01',1+2j])
def test_invalid_training_returns_rejected(value):
    x,c=hand_input();x=x.astype(object);x.iloc[0,0]=value
    with pytest.raises(ValueError,match='return'):
        estimate(x,c)


@pytest.mark.parametrize('mode', ['empty','duplicate_id','blank_id','duplicate_month','missing_month','not_month_end','one_month','missing_class','blank_class','unknown_class','duplicate_class','extra_class','bad_start','reversed_window','empty_window'])
def test_invalid_contract_rejected(mode):
    x,c=hand_input(); options={}
    if mode=='empty': x=x.iloc[:,:0];c=c.iloc[:0]
    elif mode=='duplicate_id': x.columns=['A','A','C']
    elif mode=='blank_id': x.columns=['','B','C']
    elif mode=='duplicate_month': x.index=['2024-01-31','2024-01-31','2024-03-31']
    elif mode=='missing_month': x=x.drop('2024-02-29')
    elif mode=='not_month_end': x.index=['2024-01-30','2024-02-29','2024-03-31']
    elif mode=='one_month': options=dict(train_start='2024-01',train_end='2024-01')
    elif mode=='missing_class': c=c.drop('A')
    elif mode=='blank_class': c['A']=''
    elif mode=='unknown_class': c['A']='invented'
    elif mode=='duplicate_class': c=pd.concat([c,c.iloc[:1]])
    elif mode=='extra_class': c['D']='bond'
    elif mode=='bad_start': options['train_start']='2024-1'
    elif mode=='reversed_window': options=dict(train_start='2024-03',train_end='2024-01')
    elif mode=='empty_window': options=dict(train_start='2030-01',train_end='2030-03')
    with pytest.raises(ValueError): estimate(x,c,**options)


def test_total_loss_minus_one_is_valid():
    x,c=hand_input();x.loc['2024-01-31','A']=-1
    assert np.isfinite(estimate(x,c).sample_cov_ann.to_numpy()).all()
