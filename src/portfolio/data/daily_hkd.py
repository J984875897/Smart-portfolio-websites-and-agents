"""Auditable same-month daily FX endpoints for monthly HKD previews."""
from dataclasses import dataclass
import hashlib
import pandas as pd
from .contracts import DataBundle
from .returns import strict_date, finite_number, SOURCE_FIELDS
from .fx import reconcile_hkd


@dataclass
class DailyHkdResult:
    prices: object
    fx_observations: pd.DataFrame
    fx_endpoints: pd.DataFrame
    reconciliation: pd.DataFrame
    metadata: dict


def _endpoints(frame, dates, max_age_days):
    required=['date','currency','hkd_per_unit','source_name']
    if not frame.columns.is_unique: raise ValueError('FX columns must be unique')
    if not set(required)<=set(frame.columns): raise ValueError('FX required columns missing')
    payload=frame.attrs.get('raw_bytes',frame.to_csv(index=False).encode())
    source_hash=frame.attrs.get('source_hash') or hashlib.sha256(payload).hexdigest()
    rows=[]
    source_rows=frame.attrs.get('source_rows',list(range(2,len(frame)+2)))
    for n, original in enumerate(frame.to_dict('records')):
        row=dict(original)
        for field,value in dict(source_file=frame.attrs.get('source_file','dataframe.csv'),source_sheet=frame.attrs.get('source_sheet',''),source_row=source_rows[n],source_hash=source_hash).items():
            if 'raw_bytes' in frame.attrs: row[field]=value
            else: row.setdefault(field,value)
        errors=[]; number=finite_number(row['hkd_per_unit'])
        if strict_date(row['date']) is None: errors.append('invalid_date')
        if row['currency']!='USD': errors.append('invalid_currency')
        if number is None or number<=0: errors.append('invalid_quote')
        if not isinstance(row['source_name'],str) or not row['source_name'].strip(): errors.append('missing_source_name')
        row.update(status='blocked' if errors else 'valid',reason=';'.join(errors) or 'ok')
        rows.append(row)
    observations=pd.DataFrame(rows,columns=[*required,*SOURCE_FIELDS,'status','reason'])
    global_error='invalid_date' if any(strict_date(r['date']) is None for r in rows) else ('invalid_currency' if any(r['currency']!='USD' for r in rows) else '')
    endpoints=[]
    for day in dates:
        candidates=[r for r in rows if strict_date(r['date']) is not None and r['date'][:7]==day[:7] and r['date']<=day]
        latest=max((r['date'] for r in candidates),default='')
        chosen=[r for r in candidates if r['date']==latest]
        row=dict(date=day,currency='USD',observed_date=latest,age_days=(pd.Timestamp(day)-pd.Timestamp(latest)).days if latest else None,hkd_per_unit=float('nan'),source_name='',**{f:'' for f in SOURCE_FIELDS})
        if chosen: row.update({f:chosen[0].get(f,'') for f in ['hkd_per_unit','source_name',*SOURCE_FIELDS]})
        reason=global_error or ('missing_month' if not chosen else ('duplicate_date' if len(chosen)!=1 else (chosen[0]['reason'] if chosen[0]['status']!='valid' else ('stale_quote' if row['age_days']>max_age_days else 'ok'))))
        row.update(status='valid' if reason=='ok' else 'blocked',reason=reason)
        endpoints.append(row)
    return observations,pd.DataFrame(endpoints),source_hash


def connect_daily_hkd(prices, fx_frame=None, *, fx_confirmed=False, max_age_days=7):
    """Join C1 prices to conservative FX endpoints, retaining every target row."""
    if isinstance(max_age_days,bool) or not isinstance(max_age_days,int) or not 0<=max_age_days<=7:
        raise ValueError('max_age_days must be integer 0–7')
    frame=fx_frame if fx_frame is not None else pd.DataFrame(columns=['date','currency','hkd_per_unit','source_name'])
    diagnostic_error=''
    try:
        observations,endpoints,source_hash=_endpoints(frame,prices.monthly.date.tolist(),max_age_days)
    except ValueError as error:
        if prices.metadata['currency']!='HKD': raise
        diagnostic_error=str(error)
        observations,endpoints,source_hash=_endpoints(pd.DataFrame(columns=['date','currency','hkd_per_unit','source_name']),prices.monthly.date.tolist(),max_age_days)
    valid=prices.returns[prices.returns.status=='valid']
    symbol=prices.metadata['symbol']; currency=prices.metadata['currency']
    temporary=pd.DataFrame([dict(date=r.date,asset_id=symbol,value=r.local_return,value_kind='total_return',currency=currency,frequency='monthly',source_hash=prices.metadata['source_hash']) for r in valid.itertuples()])
    bundle=DataBundle(assets=pd.DataFrame([dict(asset_id=symbol,currency=currency)]),observations=temporary)
    eligible=endpoints[endpoints.status=='valid'].copy()
    calculated=reconcile_hkd(bundle,eligible).reconciliation
    calculated_by_date={r['date']:r for r in calculated.to_dict('records')}
    endpoint_by_date={r['date']:r for r in endpoints.to_dict('records')}
    monthly={r['date']:r for r in prices.monthly.to_dict('records')}
    result=[]
    numeric=['fx_start','fx_end','fx_return','cross_term','hkd_return']
    for original in prices.returns.to_dict('records'):
        row={**calculated_by_date.get(original['date'],{}),**original}
        for field in numeric: row[field]=calculated_by_date.get(original['date'],{}).get(field,float('nan'))
        day=original['date']; previous=(pd.Period(day,freq='M')-1).end_time.strftime('%Y-%m-%d')
        errors=[]
        for side,label in [('start',previous),('end',day)]:
            row['price_'+side+'_observed_date']=monthly.get(label,{}).get('last_observed_date','')
            endpoint=endpoint_by_date.get(label,{})
            for field in ['observed_date','age_days','reason','source_name',*SOURCE_FIELDS]: row['fx_'+side+'_'+field]=endpoint.get(field,'')
            if currency=='USD' and endpoint.get('status')!='valid': errors.append('fx_'+side+':'+endpoint.get('reason','missing_month'))
        if original['status']=='valid':
            if currency=='USD':
                if fx_confirmed is not True: errors.append('unconfirmed_fx_unit')
                if frame.attrs.get('source_status','success')!='success': errors.append('source_not_success')
            if errors: row.update(status='blocked',reason=';'.join(errors))
            elif calculated_by_date.get(day,{}).get('status')!='valid': row.update(status='blocked',reason=calculated_by_date.get(day,{}).get('reason','missing_calculation'))
        if row['status']!='valid':
            for field in numeric: row[field]=float('nan')
        row.update(available_at='',historical_eligible=False)
        result.append(row)
    metadata=dict(price_source=dict(prices.metadata),fx_source={k:v for k,v in frame.attrs.items() if k!='raw_bytes'},source_hash=source_hash,fx_source_hash=source_hash,fx_diagnostic_error=diagnostic_error,unit='HKD per USD',max_age_days=max_age_days,fx_confirmed=fx_confirmed is True,available_at='',historical_eligible=False,quality_scope='current-version monthly valuation preview; endpoints only; no historical eligibility')
    return DailyHkdResult(prices,observations,endpoints,pd.DataFrame(result),metadata)
