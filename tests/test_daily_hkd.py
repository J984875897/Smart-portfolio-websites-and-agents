import importlib.util
import pandas as pd
import pytest
from test_daily_monthly import aggregate, sample


def connect(frame=None, **kwargs):
    assert importlib.util.find_spec('portfolio.data.daily_hkd'), 'daily HKD connector is missing'
    from portfolio.data.daily_hkd import connect_daily_hkd
    return connect_daily_hkd(aggregate(sample(), confirmed=True), frame, **kwargs)


def fx():
    return pd.DataFrame([dict(date=d,currency='USD',hkd_per_unit=v,source_name='SYNTH') for d,v in [('2024-12-31',7.8),('2025-01-31',7.9)]])


def test_hand_calculation_and_evidence():
    original=fx(); before=original.copy(deep=True)
    result=connect(original,fx_confirmed=True)
    row=result.reconciliation.iloc[0]
    assert row.hkd_return == pytest.approx(1.1*7.9/7.8-1)
    assert row.fx_start_observed_date=='2024-12-31'
    assert row.price_end_observed_date=='2025-01-31'
    assert not row.historical_eligible and row.available_at==''
    pd.testing.assert_frame_equal(original,before)


@pytest.mark.parametrize('value',[0,-1,True,False,float('inf'),float('nan')])
def test_latest_bad_quote_never_falls_back(value):
    frame=fx().astype({'hkd_per_unit':object})
    frame.loc[1,'hkd_per_unit']=value
    frame=pd.concat([frame,pd.DataFrame([dict(date='2025-01-30',currency='USD',hkd_per_unit=7.85,source_name='SYNTH')])])
    result=connect(frame,fx_confirmed=True)
    assert result.fx_endpoints.iloc[-1].reason=='invalid_quote'
    assert pd.isna(result.reconciliation.iloc[0].hkd_return)


@pytest.mark.parametrize('fault',['duplicate','invalid_date','currency','missing','source'])
def test_bad_endpoint_evidence(fault):
    frame=fx()
    if fault=='duplicate': frame=pd.concat([frame,frame.iloc[[-1]]])
    if fault=='invalid_date': frame.loc[0,'date']='bad'
    if fault=='currency': frame.loc[1,'currency']='HKD'
    if fault=='missing': frame=frame.iloc[:1]
    if fault=='source': frame.loc[1,'source_name']=''
    result=connect(frame,fx_confirmed=True)
    assert result.reconciliation.iloc[0].status=='blocked'
    assert pd.isna(result.reconciliation.iloc[0].hkd_return)


@pytest.mark.parametrize('age,limit,valid',[(7,7,True),(8,7,False),(1,0,False),(0,0,True)])
def test_inclusive_age(age,limit,valid):
    frame=fx(); frame.loc[1,'date']=(pd.Timestamp('2025-01-31')-pd.Timedelta(days=age)).strftime('%Y-%m-%d')
    row=connect(frame,fx_confirmed=True,max_age_days=limit).reconciliation.iloc[0]
    assert (row.status=='valid')==valid


@pytest.mark.parametrize('confirmed',[False,1,'yes'])
def test_confirmation_strict(confirmed):
    result=connect(fx(),fx_confirmed=confirmed)
    assert (result.fx_endpoints.status=='valid').all()
    assert result.reconciliation.iloc[0].status=='blocked'


def test_partial_and_local_blocked():
    frame=fx(); frame.attrs['source_status']='partial'
    assert connect(frame,fx_confirmed=True).reconciliation.iloc[0].status=='blocked'
    from portfolio.data.daily_hkd import connect_daily_hkd
    price=aggregate(sample(),confirmed=False)
    row=connect_daily_hkd(price,fx(),fx_confirmed=True).reconciliation.iloc[0]
    assert row.reason=='unconfirmed_adjusted_price' and pd.isna(row.hkd_return)


def test_hkd_without_fx_and_overflow():
    from portfolio.data.daily_hkd import connect_daily_hkd
    price=aggregate(sample(),confirmed=True); price.metadata['currency']='HKD'; price.returns['currency']='HKD'
    assert connect_daily_hkd(price).reconciliation.iloc[0].hkd_return==pytest.approx(.1)
    frame=fx(); frame['hkd_per_unit']=[1e-308,1e308]
    assert connect(frame,fx_confirmed=True).reconciliation.iloc[0].status=='blocked'


@pytest.mark.parametrize('limit',[-1,8,True,1.5])
def test_invalid_age_policy(limit):
    with pytest.raises(ValueError): connect(fx(),max_age_days=limit)


def test_missing_and_duplicate_columns():
    with pytest.raises(ValueError): connect(fx().drop(columns='date'))
    with pytest.raises(ValueError): connect(pd.concat([fx(),fx()[['date']]],axis=1))


def test_weekend_endpoint_and_no_cross_month_fill():
    from portfolio.data.daily_hkd import connect_daily_hkd
    price=aggregate(sample(),confirmed=True)
    price.monthly.loc[1,'date']='2025-05-31'; price.monthly.loc[0,'date']='2025-04-30'
    price.returns.loc[0,'date']='2025-05-31'
    frame=pd.DataFrame([dict(date=d,currency='USD',hkd_per_unit=v,source_name='SYNTH') for d,v in [('2025-04-30',7.8),('2025-05-30',7.9)]])
    result=connect_daily_hkd(price,frame,fx_confirmed=True)
    assert result.reconciliation.iloc[0].status=='valid'
    assert result.fx_endpoints.iloc[-1].age_days==1
    result=connect_daily_hkd(price,frame.iloc[:1],fx_confirmed=True)
    assert result.fx_endpoints.iloc[-1].reason=='missing_month'
    assert pd.isna(result.reconciliation.iloc[0].hkd_return)


def test_earlier_bad_row_is_diagnosed_without_blocking_newer_endpoint():
    frame=pd.concat([fx(),pd.DataFrame([dict(date='2025-01-20',currency='USD',hkd_per_unit=0,source_name='SYNTH')])])
    result=connect(frame,fx_confirmed=True)
    assert result.fx_observations.iloc[-1].reason=='invalid_quote'
    assert result.reconciliation.iloc[0].status=='valid'


def test_file_provenance_and_json_metadata():
    import json
    frame=fx(); frame.attrs.update(raw_bytes=b'original bytes',source_rows=[3,8],source_file='rates.csv',source_sheet='Sheet1')
    result=connect(frame,fx_confirmed=True)
    assert result.reconciliation.iloc[0].fx_end_source_row==8
    assert result.reconciliation.iloc[0].fx_end_source_sheet=='Sheet1'
    json.dumps(result.metadata)


def test_hkd_remains_valid_despite_malformed_irrelevant_fx():
    from portfolio.data.daily_hkd import connect_daily_hkd
    price=aggregate(sample(),confirmed=True); price.metadata['currency']='HKD'; price.returns['currency']='HKD'
    result=connect_daily_hkd(price,pd.DataFrame({'bad':[1]}))
    assert result.reconciliation.iloc[0].hkd_return==pytest.approx(.1)
    assert result.metadata['fx_diagnostic_error']=='FX required columns missing'
