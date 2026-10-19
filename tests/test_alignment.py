import pandas as pd
import pytest
from portfolio.data.alignment import align_monthly
from portfolio.data.alignment_samples import sample_alignment_inputs


def run(decision='2025-02-01T06:00:00+08:00', **kwargs):
    r,t,a=sample_alignment_inputs()
    return align_monthly(r,t,asset_ids=a,end_month='2025-01',decision_at=decision,**kwargs)


def test_fixed_window_and_availability():
    early=run('2025-01-31T17:00:00+08:00'); late=run()
    assert list(early.matrix)==['HKD_COMPLETE']
    assert list(late.matrix)==['HKD_COMPLETE','USD_COMPLETE']
    assert len(late.matrix)==60
    assert late.window_start=='2020-02-29'
    assert late.window_end=='2025-01-31'
    assert late.report.set_index('asset_id').loc['SHORT_HISTORY','valid_months']==59


def test_duplicate_missing_and_immutable():
    r,t,a=sample_alignment_inputs(); before=r.copy(deep=True); tb=t.copy(deep=True)
    t=pd.concat([t,t.iloc[[1]]],ignore_index=True)
    result=align_monthly(r,t,asset_ids=a+['ABSENT'],end_month='2025-01',decision_at='2025-02-01T06:00:00+08:00')
    assert 'HKD_COMPLETE' not in result.matrix
    assert result.report.set_index('asset_id').loc['ABSENT','missing_months']==60
    pd.testing.assert_frame_equal(r,before)
    assert len(tb)+1==len(t)


@pytest.mark.parametrize('args',[{'end_month':'2025-1'},{'decision_at':'2025-02-01'},{'months':True},{'months':0},{'end_month':'2025-03'}])
def test_invalid_parameters(args):
    r,t,a=sample_alignment_inputs(); params=dict(asset_ids=a,end_month='2025-01',decision_at='2025-02-01T06:00:00+08:00');params.update(args)
    with pytest.raises(ValueError): align_monthly(r,t,**params)


def single(r,t,decision='2025-02-01T06:00:00+08:00'):
    return align_monthly(r,t,asset_ids=['HKD_COMPLETE'],end_month='2025-01',decision_at=decision,months=1)


@pytest.mark.parametrize('field,value,reason',[
    ('price_end_at','2025-01-31T16:00:00','invalid_price_end_at'),
    ('price_end_at','2025-01-23T16:00:00+08:00','stale_price_end_at'),
    ('price_end_at','2025-02-01T00:00:00+08:00','wrong_month_price_end_at'),
    ('price_start_at','','invalid_price_start_at'),
    ('available_at','2025-01-31T15:00:00+08:00','availability_before_observation'),
    ('market_timezone','UTC','invalid_market_timezone'),
    ('source_name','','missing_source_name'),
])
def test_bad_timing(field,value,reason):
    r,t,_=sample_alignment_inputs(); t.loc[(t.asset_id=='HKD_COMPLETE')&(t.date=='2025-01-31'),field]=value
    result=single(r,t)
    assert result.matrix.shape==(1,0)
    assert reason in result.coverage.iloc[0].reason


def test_staleness_boundary_equality_and_provenance():
    from portfolio.data.importer import read_file
    import hashlib
    r,t,_=sample_alignment_inputs(); t=t[(t.asset_id=='HKD_COMPLETE')&(t.date=='2025-01-31')].copy()
    t['price_end_at']='2025-01-24T16:00:00+08:00'
    t['available_at']='2025-01-31T16:00:00+08:00'
    t['source_file']='forged';t['source_hash']='forged';t['source_row']=999;t['source_sheet']='forged'
    payload=t.to_csv(index=False).encode(); uploaded=read_file(payload,filename='evidence.csv')
    result=single(r,uploaded,'2025-01-31T16:00:00+08:00')
    assert list(result.matrix)==['HKD_COMPLETE']
    row=result.coverage.iloc[0]
    assert row.timing_source_file=='evidence.csv'
    assert row.timing_source_hash==hashlib.sha256(payload).hexdigest()
    assert row.timing_source_row==2
    assert row.timing_source_sheet==''


@pytest.mark.parametrize('number',[float('nan'),float('inf'),-1.01,True])
def test_invalid_return(number):
    r,t,_=sample_alignment_inputs(); r['hkd_return']=r.hkd_return.astype(object); r.loc[(r.asset_id=='HKD_COMPLETE')&(r.date=='2025-01-31'),'hkd_return']=number
    assert 'invalid_hkd_return' in single(r,t).coverage.iloc[0].reason


def test_missing_duplicate_and_original_failure():
    r,t,_=sample_alignment_inputs(); selected=(r.asset_id=='HKD_COMPLETE')&(r.date=='2025-01-31')
    duplicate=pd.concat([r,r[selected]])
    assert 'ambiguous_return' in single(duplicate,t).coverage.iloc[0].reason
    assert 'missing_timing' in single(r,t.iloc[0:0]).coverage.iloc[0].reason
    r.loc[selected,'status']='blocked';r.loc[selected,'reason']='upstream_original_reason'
    assert 'upstream_original_reason' in single(r,t).coverage.iloc[0].reason


def test_reorder_and_empty_matrix_and_input_immutability():
    r,t,a=sample_alignment_inputs(); rb=r.copy(deep=True);tb=t.copy(deep=True)
    params=dict(end_month='2025-01',decision_at='2025-02-01T06:00:00+08:00')
    first=align_monthly(r,t,asset_ids=a,**params);second=align_monthly(r,t,asset_ids=list(reversed(a)),**params)
    pd.testing.assert_frame_equal(first.matrix,second.matrix)
    pd.testing.assert_frame_equal(r,rb);pd.testing.assert_frame_equal(t,tb)
    empty=align_monthly(r,t,asset_ids=['ABSENT'],**params)
    assert empty.matrix.shape==(60,0)


def test_us_offset_and_fx_required():
    r,t,a=sample_alignment_inputs()
    # Explicit DST offset converts correctly without assuming a constant NY offset.
    result=align_monthly(r,t,asset_ids=['USD_COMPLETE'],end_month='2024-07',decision_at='2024-08-01T06:00:00+08:00',months=1)
    assert result.matrix.shape==(1,1)
    mask=(t.asset_id=='USD_COMPLETE')&(t.date=='2024-07-31'); t.loc[mask,'fx_end_at']=''
    result=align_monthly(r,t,asset_ids=['USD_COMPLETE'],end_month='2024-07',decision_at='2024-08-01T06:00:00+08:00',months=1)
    assert 'invalid_fx_end_at' in result.coverage.iloc[0].reason


def test_empty_requested_assets_has_stable_schemas():
    r,t,_=sample_alignment_inputs()
    result=align_monthly(r,t,asset_ids=[],end_month='2025-01',decision_at='2025-02-01T06:00:00+08:00')
    assert result.matrix.shape==(60,0)
    assert set(['asset_id','date','status','reason','hkd_return'])<=set(result.coverage.columns)


def test_period_must_be_complete_at_decision():
    r,t,_=sample_alignment_inputs()
    mask=(t.asset_id=='HKD_COMPLETE')&(t.date=='2025-01-31')
    t.loc[mask,'price_end_at']='2025-01-24T16:00:00+08:00'
    t.loc[mask,'available_at']='2025-01-24T16:00:00+08:00'
    result=single(r,t,'2025-01-24T16:00:00+08:00')
    assert result.matrix.shape==(1,0)
    assert 'period_not_complete_at_decision' in result.coverage.iloc[0].reason
    assert single(r,t,'2025-01-31T16:00:00+08:00').matrix.shape==(1,1)


def test_us_period_label_not_reached_in_market_timezone():
    r,t,_=sample_alignment_inputs()
    mask=(t.asset_id=='USD_COMPLETE')&(t.date=='2025-01-31')
    t.loc[mask,'price_end_at']='2025-01-30T16:00:00-05:00'
    t.loc[mask,'fx_end_at']='2025-01-30T21:00:00+00:00'
    t.loc[mask,'available_at']='2025-01-30T21:00:00+00:00'
    result=align_monthly(r,t,asset_ids=['USD_COMPLETE'],end_month='2025-01',decision_at='2025-01-31T09:00:00+08:00',months=1)
    assert result.matrix.shape==(1,0)
    assert 'period_not_complete_at_decision' in result.coverage.iloc[0].reason


def test_foreign_period_label_not_reached_in_utc():
    r,t,_=sample_alignment_inputs()
    mask=(t.asset_id=='USD_COMPLETE')&(t.date=='2025-01-31')
    t.loc[mask,'market_timezone']='Asia/Hong_Kong'
    t.loc[mask,'price_end_at']='2025-01-30T16:00:00+08:00'
    t.loc[mask,'fx_end_at']='2025-01-30T08:00:00+00:00'
    t.loc[mask,'available_at']='2025-01-30T08:00:00+00:00'
    # Start price declared NY remains in its correct month after HK conversion.
    result=align_monthly(r,t,asset_ids=['USD_COMPLETE'],end_month='2025-01',decision_at='2025-01-31T01:00:00+08:00',months=1)
    assert 'period_not_complete_at_decision' in result.coverage.iloc[0].reason
    assert result.matrix.shape==(1,0)


@pytest.mark.parametrize('transform',[lambda f:f.iloc[1:],lambda f:f.iloc[::-1].reset_index(drop=True),lambda f:f.set_axis([10,11])])
def test_transformed_file_timing_is_rejected(transform):
    from portfolio.data.importer import read_file
    r,t,_=sample_alignment_inputs()
    t=t[(t.asset_id=='HKD_COMPLETE')&t.date.isin(['2024-12-31','2025-01-31'])]
    frame=read_file(t.to_csv(index=False).encode(),filename='timing.csv')
    with pytest.raises(ValueError,match='unchanged read_file'):
        single(r,transform(frame))


def test_physical_provenance_reparsed_even_for_blocked_rows():
    from portfolio.data.importer import read_file
    r,t,_=sample_alignment_inputs()
    t=t[(t.asset_id=='HKD_COMPLETE')&t.date.isin(['2024-12-31','2025-01-31'])].copy()
    t.loc[t.date=='2025-01-31','price_end_at']=''
    payload=t.to_csv(index=False).encode()
    # Blank physical line before records changes provenance, not the row index.
    header,body=payload.split(b'\n',1)
    uploaded=read_file(header+b'\n\n'+body,filename='timing.csv')
    uploaded.attrs['source_rows']=[999,999]
    result=single(r,uploaded)
    assert result.coverage.iloc[0].timing_source_row==4
    assert 'invalid_price_end_at' in result.coverage.iloc[0].reason


def test_xlsx_complete_frame_binds_sheet_and_rejects_transformation():
    from io import BytesIO
    from portfolio.data.importer import read_file
    r,t,_=sample_alignment_inputs()
    t=t[(t.asset_id=='HKD_COMPLETE')&t.date.isin(['2024-12-31','2025-01-31'])].copy()
    stream=BytesIO()
    with pd.ExcelWriter(stream,engine='openpyxl') as writer:
        pd.DataFrame({'unused':['x']}).to_excel(writer,sheet_name='other',index=False)
        t.to_excel(writer,sheet_name='timing',index=False)
    uploaded=read_file(stream.getvalue(),filename='timing.xlsx',sheet_name='timing')
    uploaded.attrs['source_rows']=[999,999]
    result=single(r,uploaded)
    assert result.matrix.shape==(1,1)
    assert result.coverage.iloc[0].timing_source_sheet=='timing'
    assert result.coverage.iloc[0].timing_source_row==3
    with pytest.raises(ValueError,match='unchanged read_file'):
        single(r,uploaded.iloc[1:].reset_index(drop=True))
