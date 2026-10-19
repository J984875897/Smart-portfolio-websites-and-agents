from io import BytesIO
import json
import numpy as np
import pandas as pd
import pytest


def test_risk_sample_is_reproducible_and_qualifies():
    from portfolio.universe.risk_samples import sample_risk_inputs
    from portfolio.universe.inputs import prepare_candidate_input
    from portfolio.universe.screening import screen_candidates
    a=sample_risk_inputs(); b=sample_risk_inputs()
    assert a[0].observations.equals(b[0].observations)
    c=prepare_candidate_input(*a,end_month='2025-01',decision_at='2025-02-01T06:00:00+08:00')
    result=screen_candidates(c,k=30)
    assert result.cardinality.status == 'passed' and result.matrix.shape == (60,100)
    x=result.matrix
    assert x.iloc[:,0].nunique() == 1
    assert x.iloc[:,1].corr(x.iloc[:,2]) == pytest.approx(1)
    assert x.iloc[:,1].corr(x.iloc[:,3]) == pytest.approx(-1)


def test_weight_alignment_and_no_normalization():
    from app.views.risk_exports import parse_weights
    w=parse_weights(b'asset_id,weight\nB,0.7\nA,0.3\n',['A','B'])
    assert w.to_dict() == {'A':.3,'B':.7}


@pytest.mark.parametrize('payload',[
    b'asset_id,weight\nA,1\n', b'asset_id,weight\nA,0.5\nC,0.5\n',
    b'asset_id,weight\nA,0.5\nA,0.5\n', b'asset_id,weight\nA,-0.1\nB,1.1\n',
    b'asset_id,weight\nA,True\nB,0\n', b'asset_id,weight\nA,inf\nB,0\n',
    b'asset_id,weight\nA,0.3\nB,0.3\n', b'asset_id,weight\nA,\nB,1\n',
    b'asset_id,weight,extra\nA,0.5,x\nB,0.5,x\n',
    b'asset_id,weight,weight\nA,.5,.5\nB,.5,.5\n',
    b'asset_id,weight\n A,.5\nB,.5\n', b'garbage', b'asset_id,weight\nA,nan\nB,1\n',
])
def test_invalid_weights_rejected(payload):
    from app.views.risk_exports import parse_weights
    with pytest.raises(ValueError): parse_weights(payload,['A','B'])


def test_exports_preserve_nulls_full_matrices_and_evidence():
    from app.views.risk_exports import preview_exports, correlation_pairs
    from portfolio.universe.screening_samples import sample_screening_inputs
    from portfolio.universe.inputs import prepare_candidate_input
    from portfolio.evaluation.risk_preview import preview_candidate_risk
    c=prepare_candidate_input(*sample_screening_inputs(),end_month='2025-01',decision_at='2025-02-01T06:00:00+08:00')
    p=preview_candidate_risk(c,pd.Series(.01,index=sorted(c.matrix.columns)),k=30)
    files=preview_exports(p)
    data=json.loads(files['risk_evidence.json'],parse_constant=lambda x:pytest.fail(x))
    assert data['sample_metrics']['diversification_ratio'] is None
    assert data['evidence']['portfolio_constructed'] is False
    assert data['evidence']['positive_weight_count'] == 100
    corr=pd.read_csv(BytesIO(files['correlation.csv']),index_col=0)
    assert corr.shape == (100,100) and corr.isna().all().all()
    assert correlation_pairs(p.correlation.matrix).empty
    assert pd.read_csv(BytesIO(files['return_estimates.csv'])).estimated_mean_ann.iloc[0] == pytest.approx(.12)


def test_overwide_csv_rows_are_not_silently_used_as_an_index():
    from app.views.risk_exports import parse_weights
    with pytest.raises(ValueError):
        parse_weights(b'asset_id,weight\nignored,A,0.5\nignored2,B,0.5\n',['A','B'])


def test_weight_shape_error_explains_columns_instead_of_encoding():
    from app.views.risk_exports import parse_weights
    with pytest.raises(ValueError,match='两列'):
        parse_weights(b'asset_id,weight\nignored,A,0.5\nignored2,B,0.5\n',['A','B'])
