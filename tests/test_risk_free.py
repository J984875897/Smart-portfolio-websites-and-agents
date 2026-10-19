from io import BytesIO
import hashlib
import pandas as pd
import pytest
from portfolio.data.risk_free import risk_free_monthly
from portfolio.data.risk_free_samples import sample_risk_free_quotes
from portfolio.data.importer import read_file


def run(q=None, **kw):
    return risk_free_monthly(sample_risk_free_quotes() if q is None else q, **dict(end_month='2024-03', decision_at='2024-03-31T16:00:00+08:00', months=3, **kw))


def test_percent_quote_to_monthly_decimal():
    r=run()
    assert r.available
    assert r.series.tolist()==pytest.approx([.0031,.0029,.0031])
    assert r.report.days.tolist()==[31,29,31]
    assert r.currency=='HKD' and r.frequency=='monthly'


@pytest.mark.parametrize('case,code',[('缺中间报价','missing_quote'),('月中报价','quote_after_start'),('版本晚可得','availability_after_start'),('USD报价','invalid_currency')])
def test_failure_cases(case,code):
    r=run(sample_risk_free_quotes(case))
    assert not r.available and pd.isna(r.series.iloc[1])
    assert pd.isna(r.report.iloc[1].rf_hkd) and code in r.report.iloc[1].reason


@pytest.mark.parametrize('field,value,code',[(f,'wrong','invalid_'+f) for f in ['currency','benchmark','tenor','day_count','compounding']]+[('source_name','','missing_source_name'),('quote_percent',True,'invalid_quote_percent'),('quote_percent',float('nan'),'invalid_quote_percent'),('quote_percent',float('inf'),'invalid_quote_percent'),('quote_percent',-2000,'invalid_rf_hkd'),('quote_at','2024-01-31T11:15:00','invalid_quote_at'),('available_at','bad','invalid_available_at'),('date','2024-02-28','invalid_period_label'),('date','bad','invalid_date')])
def test_invalid_rows(field,value,code):
    q=sample_risk_free_quotes(); q[field]=q[field].astype(object); q.loc[1,field]=value
    r=run(q)
    assert not r.available
    assert code in ';'.join(r.report.reason)


@pytest.mark.parametrize('value,expected',[(0,0),(-3.65,-.0029),(.0365,.000029)])
def test_explicit_percent_zero_negative(value,expected):
    q=sample_risk_free_quotes(); q.loc[1,'quote_percent']=value
    assert run(q).series.iloc[1]==pytest.approx(expected)


@pytest.mark.parametrize('field,value,code',[('quote_at','2024-01-24T15:59:59+08:00','stale_quote'),('available_at','2024-01-31T11:14:59+08:00','availability_before_quote')])
def test_timing_failures(field,value,code):
    q=sample_risk_free_quotes(); q.loc[1,field]=value
    assert code in run(q).report.iloc[1].reason


def test_equal_boundaries_and_maturity():
    q=sample_risk_free_quotes(); q.loc[1,'quote_at']='2024-01-24T16:00:00+08:00'; q.loc[1,'available_at']='2024-01-31T08:00:00+00:00'
    assert run(q).available
    r=risk_free_monthly(q,end_month='2024-03',decision_at='2024-03-31T15:59:59+08:00',months=3)
    assert 'period_not_complete_at_decision' in r.report.iloc[2].reason
    q.loc[1,'quote_at']=q.loc[1,'available_at']
    assert run(q).available


def test_missing_ambiguous_and_fixed_window():
    q=sample_risk_free_quotes(); q=pd.concat([q,q.iloc[[1]].assign(date='2024-02-01')],ignore_index=True)
    assert 'ambiguous_quote' in run(q).report.iloc[1].reason
    r=risk_free_monthly(sample_risk_free_quotes(),end_month='2024-03',decision_at='2024-03-31T16:00:00+08:00')
    assert len(r.series)==60 and r.series.isna().sum()==57
    assert r.window_start=='2019-04-30' and r.window_end=='2024-03-31'


@pytest.mark.parametrize('kw',[{'months':True},{'months':0},{'months':1.5},{'end_month':'2024-3'},{'end_month':'2024-13'},{'decision_at':'2024-03-31'},{'decision_at':'bad'}])
def test_invalid_parameters(kw):
    args=dict(end_month='2024-03',decision_at='2024-03-31T16:00:00+08:00',months=3); args.update(kw)
    with pytest.raises(ValueError): risk_free_monthly(sample_risk_free_quotes(),**args)


def test_schema():
    q=sample_risk_free_quotes()
    with pytest.raises(ValueError): run(q.drop(columns='currency'))
    with pytest.raises(ValueError): run(pd.concat([q,q[['currency']]],axis=1))


def test_reordering_immutable_and_dataframe_provenance():
    q=sample_risk_free_quotes(); before=q.copy(deep=True)
    q.attrs['source_rows']=[999]*3; q['source_file']='forged'
    r=run(q); reordered=run(q.iloc[::-1])
    pd.testing.assert_series_equal(r.series,reordered.series)
    assert r.report.iloc[0].quote_source_file=='dataframe.csv'
    assert r.report.iloc[0].quote_source_hash==hashlib.sha256(q.to_csv(index=False).encode()).hexdigest()
    pd.testing.assert_frame_equal(q.drop(columns='source_file'),before)


@pytest.mark.parametrize('kind',['csv','xlsx'])
def test_physical_provenance_and_unchanged_frame(kind):
    q=sample_risk_free_quotes()
    if kind=='csv':
        head,body=q.to_csv(index=False).encode().split(b'\n',1); payload=head+b'\n\n'+body
        frame=read_file(payload,filename='quotes.csv'); expected=3
    else:
        stream=BytesIO()
        with pd.ExcelWriter(stream,engine='openpyxl') as w:
            pd.DataFrame({'a':[1]}).to_excel(w,sheet_name='unused',index=False)
            q.to_excel(w,sheet_name='quotes',index=False)
        payload=stream.getvalue(); frame=read_file(payload,filename='quotes.xlsx',sheet_name='quotes'); expected=2
    frame.attrs['source_rows']=[999]*3
    r=run(frame)
    assert r.available and r.report.iloc[0].quote_source_row==expected
    assert r.report.iloc[0].quote_source_hash==hashlib.sha256(payload).hexdigest()
    for changed in [frame.iloc[::-1],frame.iloc[1:].reset_index(drop=True),frame.set_axis([4,5,6])]:
        with pytest.raises(ValueError,match='unchanged read_file'): run(changed)


def test_complete_sixty_month_window_and_no_older_replacement():
    base=sample_risk_free_quotes().iloc[0].to_dict(); rows=[]
    for period in pd.period_range(end='2024-03',periods=61,freq='M'):
        start=(period-1).end_time.date().isoformat()
        rows.append(dict(base,date=period.end_time.date().isoformat(),quote_at=start+'T16:00:00+08:00',available_at=start+'T16:00:00+08:00'))
    q=pd.DataFrame(rows)
    args=dict(end_month='2024-03',decision_at='2024-03-31T16:00:00+08:00')
    result=risk_free_monthly(q,**args)
    assert result.available and len(result.series)==60
    q=q[q.date!='2021-02-28']
    result=risk_free_monthly(q,**args)
    assert len(result.series)==60 and result.series.isna().sum()==1
    assert pd.isna(result.series.loc['2021-02-28'])


def test_late_version_has_both_start_and_decision_evidence():
    q=sample_risk_free_quotes(); q.loc[1,'available_at']='2024-04-01T12:15:00+08:00'
    reason=run(q).report.iloc[1].reason
    assert 'availability_after_start' in reason and 'not_available_at_decision' in reason


def test_file_frame_value_mutation_rejected():
    frame=read_file(sample_risk_free_quotes().to_csv(index=False).encode(),filename='q.csv')
    frame.loc[1,'quote_percent']='9.0'
    with pytest.raises(ValueError,match='unchanged read_file'): run(frame)
