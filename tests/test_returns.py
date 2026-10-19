import copy
import pandas as pd
import pytest
from portfolio.data.contracts import DataBundle


def bundle(rows, currency='USD'):
    records=[]
    for n, row in enumerate(rows):
        records.append(dict(asset_id='a', currency=currency, frequency='monthly', value_kind='total_return', source_file='input.csv', source_sheet='', source_row=n+2, source_hash='hash', **row))
    return DataBundle(assets=pd.DataFrame([dict(asset_id='a', currency=currency)]), observations=pd.DataFrame(records))


def build(b, **kwargs):
    from portfolio.data.returns import build_local_returns
    return build_local_returns(b, **kwargs)


def test_total_return_zero_loss_and_no_mutation():
    b=bundle([dict(date='2024-01-31',value=0),dict(date='2024-02-29',value=-1)])
    old=copy.deepcopy(b)
    result=build(b)
    assert result.local_return.tolist()==[0,-1]
    assert result.start_date.tolist()==['2023-12-31','2024-01-31']
    pd.testing.assert_frame_equal(old.observations,b.observations)


def test_adjusted_contiguous_price_evidence():
    b=bundle([dict(date='2023-12-31',value=100),dict(date='2024-01-31',value=101)])
    b.observations['value_kind']='adjusted_price'
    result=build(b,adjusted_price_assets=['a'])
    assert result.iloc[1].local_return==pytest.approx(.01)
    assert result.iloc[1].start_source_row==2
    assert result.iloc[1].source_row==3
    assert result.iloc[0].reason=='first_period'
    assert build(b).reason.tolist()==['unconfirmed_adjusted_price']*2


def test_gap_and_ambiguous_predecessor_block():
    b=bundle([dict(date='2023-12-31',value=100),dict(date='2024-02-29',value=101)])
    b.observations['value_kind']='adjusted_price'
    assert build(b,adjusted_price_assets=['a']).iloc[1].reason=='missing_previous_month'
    b=bundle([dict(date='2024-01-31',value=100),dict(date='2024-01-30',value=99),dict(date='2024-02-29',value=101)])
    b.observations['value_kind']='adjusted_price'
    r=build(b,adjusted_price_assets=['a'])
    assert r.reason.tolist()==['ambiguous_asset_month','ambiguous_asset_month','invalid_previous_month']
    assert r.local_return.isna().all()


@pytest.mark.parametrize('field,value,reason',[('date','2024-1-31','invalid_date'),('date','2024-01-30','alignment_required'),('frequency','daily','alignment_required'),('frequency','no','invalid_frequency'),('value',float('inf'),'invalid_value'),('value',-1.1,'invalid_value'),('currency','XXX','invalid_currency'),('currency','HKD','currency_conflict'),('value_kind','price','not_total_return'),('value_kind','price_return','not_total_return')])
def test_invalid_rows(field,value,reason):
    b=bundle([dict(date='2024-01-31',value=.01)])
    b.observations.loc[0,field]=value
    r=build(b).iloc[0]
    assert r.reason==reason
    assert pd.isna(r.local_return)


def test_empty_has_schema():
    assert 'local_return' in build(DataBundle()).columns


def test_different_kinds_same_month_block_every_observation():
    b=bundle([dict(date='2024-01-31',value=.01),dict(date='2024-01-31',value=100)])
    b.observations.loc[1,'value_kind']='adjusted_price'
    result=build(b,adjusted_price_assets=['a'])
    assert result.reason.tolist()==['ambiguous_asset_month']*2
    assert result.local_return.isna().all()


def test_invalid_predecessor_never_used():
    b=bundle([dict(date='2024-01-31',value=float('nan')),dict(date='2024-02-29',value=101)])
    b.observations['value_kind']='adjusted_price'
    result=build(b,adjusted_price_assets=['a'])
    assert result.reason.tolist()==['invalid_value','invalid_previous_month']


def test_nonexistent_date_blocked():
    assert build(bundle([dict(date='2023-02-29',value=.01)])).iloc[0].reason=='invalid_date'
