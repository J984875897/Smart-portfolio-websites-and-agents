"""Pearson must use the same complete training sample, with undefined constants."""
import json
import numpy as np
import pandas as pd
import pytest


def inputs():
    return pd.DataFrame({'A':[.01,.03,.02],'B':[.03,.05,.04],'C':[0,.01,.02],
                         'NEG':[-.01,-.03,-.02],'CONST':[.01,.01,.01]},
                        index=['2024-01-31','2024-02-29','2024-03-31'])


def corr(x=None,**options):
    from portfolio.evaluation.correlation import pearson_correlation
    return pearson_correlation(inputs() if x is None else x,
                               **(dict(train_start='2024-01',train_end='2024-03')|options))


def test_hand_correlation_and_constant_self_is_unavailable():
    r=corr()
    assert list(r.matrix) == ['A','B','C','CONST','NEG']
    np.testing.assert_allclose(r.matrix.loc[['A','B','C'],['A','B','C']],[[1,1,.5],[1,1,.5],[.5,.5,1]])
    assert r.matrix.loc['A','NEG'] == pytest.approx(-1)
    assert r.matrix.loc['CONST'].isna().all() and r.matrix['CONST'].isna().all()
    assert r.asset_status.loc['CONST','status'] == 'unavailable_constant'
    assert r.asset_status.loc['A','status'] == 'available'
    assert r.diagnostics['n_observations'] == 3
    assert r.diagnostics['constant_assets'] == ['CONST']
    json.dumps(r.diagnostics,allow_nan=False)


def test_future_values_order_and_dtype_do_not_affect_training():
    x=inputs();before=x.copy(deep=True);r=corr(x)
    future=pd.DataFrame({a:['outside training'] for a in x},index=['2024-04-30'])
    extended=pd.concat([x,future]).iloc[::-1,::-1]
    other=corr(extended)
    assert r.fingerprint == other.fingerprint
    assert r.diagnostics == other.diagnostics
    pd.testing.assert_frame_equal(r.matrix,other.matrix)
    pd.testing.assert_frame_equal(x,before)


def test_all_constant_and_single_asset():
    r=corr(inputs()[['CONST']])
    assert r.matrix.shape == (1,1) and r.matrix.isna().all().all()
    assert r.diagnostics['available_pairs'] == 0
    assert corr(inputs()[['A']]).matrix.iloc[0,0] == 1


def test_tiny_nonconstant_series_is_not_classified_as_constant():
    x=inputs()[['A','NEG']]*1e-200
    r=corr(x)
    assert r.diagnostics['constant_assets'] == []
    assert r.matrix.loc['A','NEG'] == pytest.approx(-1)


@pytest.mark.parametrize('case',['missing','duplicate_month','bad_date','duplicate_id','nonfinite','bool','one_month','empty'])
def test_bad_training_input_fails_without_pairwise_deletion(case):
    x=inputs();options={}
    if case=='missing': x=x.drop('2024-02-29')
    elif case=='duplicate_month':x.index=['2024-01-31','2024-01-31','2024-03-31']
    elif case=='bad_date':x.index=['2024-01-30','2024-02-29','2024-03-31']
    elif case=='duplicate_id':x.columns=['A','A','C','NEG','CONST']
    elif case=='nonfinite':x.iloc[0,0]=np.nan
    elif case=='bool':x=x.astype(object);x.iloc[0,0]=True
    elif case=='one_month':options=dict(train_end='2024-01')
    elif case=='empty':x=x.iloc[:,:0]
    with pytest.raises(ValueError):corr(x,**options)
