"""Complete linkage must not collapse correlation chains or erase hedges."""
import numpy as np
import pandas as pd
import pytest


def matrix():
    return pd.DataFrame([[1,.9,.7,-1],[.9,1,.9,-.9],[.7,.9,1,-.7],[-1,-.9,-.7,1]],
                        index=list('ABCD'),columns=list('ABCD'))


def test_complete_linkage_chain_tie_and_negative_correlation():
    from portfolio.universe.clustering import cluster_correlations
    r=cluster_correlations(matrix())
    m=r.memberships.set_index('asset_id')
    assert m.loc['A','cluster_id'] == m.loc['B','cluster_id']
    assert m.loc['A','cluster_id'] != m.loc['C','cluster_id']
    assert m.loc['D','cluster_id'] not in m.loc[list('ABC'),'cluster_id'].tolist()
    assert len(r.merges) == 1
    assert r.diagnostics['known_cluster_count'] == 3
    assert r.diagnostics['method'] == 'complete_linkage_1_minus_rho'


def test_threshold_equality_and_column_order_have_identical_fingerprint():
    from portfolio.universe.clustering import cluster_correlations
    x=pd.DataFrame([[1,.85],[.85,1]],index=['A','B'],columns=['A','B'])
    a=cluster_correlations(x);b=cluster_correlations(x.loc[['B','A'],['B','A']])
    assert a.memberships.cluster_id.nunique() == 1
    assert a.fingerprint == b.fingerprint
    pd.testing.assert_frame_equal(a.memberships,b.memberships)
    assert cluster_correlations(x,rho_threshold=.86).memberships.cluster_id.nunique() == 2


def test_constants_remain_unknown_not_independent_evidence():
    from portfolio.universe.clustering import cluster_correlations
    x=matrix();x['E']=np.nan;x.loc['E']=np.nan
    r=cluster_correlations(x)
    assert r.diagnostics['unknown_assets'] == ['E']
    assert r.memberships.set_index('asset_id').loc['E','correlation_status'] == 'unavailable'
    assert r.diagnostics['known_cluster_count'] == 3
    all_unknown=cluster_correlations(pd.DataFrame(np.nan,index=['B','A'],columns=['B','A']))
    assert all_unknown.diagnostics['known_cluster_count'] == 0
    assert all_unknown.memberships.cluster_id.nunique() == 2


@pytest.mark.parametrize('change',[
    lambda x:x.rename(columns={'A':'X'}),
    lambda x:x.rename(index={'B':'A'},columns={'B':'A'}),
    lambda x:x.assign(A=[1,.8,.7,-1]),
    lambda x:x.assign(A=[1,.9,np.nan,-1]),
    lambda x:x.assign(A=[2,.9,.7,-1]),
    lambda x:x.assign(A=[True,.9,.7,-1]),
    lambda x:x.rename(index={'A':' A'},columns={'A':' A'}),
    lambda x:x.assign(A=[np.inf,.9,.7,-1]),
    lambda x:x.iloc[:0],
])
def test_bad_correlation_matrix_is_rejected(change):
    from portfolio.universe.clustering import cluster_correlations
    with pytest.raises(ValueError): cluster_correlations(change(matrix()))


@pytest.mark.parametrize('threshold',[True,-.1,1.1,float('nan'),'0.85'])
def test_bad_threshold_is_rejected(threshold):
    from portfolio.universe.clustering import cluster_correlations
    with pytest.raises(ValueError): cluster_correlations(matrix(),rho_threshold=threshold)


def test_does_not_modify_input():
    from portfolio.universe.clustering import cluster_correlations
    x=matrix();before=x.copy(deep=True)
    cluster_correlations(x)
    pd.testing.assert_frame_equal(x,before)
