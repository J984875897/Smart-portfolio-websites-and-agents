"""Artificial research scenarios, never real investment product evidence."""
import pandas as pd
from .contracts import DataBundle
from .fx import reconcile_hkd


def sample_alignment_inputs():
    assets=['HKD_COMPLETE','USD_COMPLETE','MISSING_MIDDLE','SHORT_HISTORY','MISSING_END_FX']
    currencies={a:('USD' if a in {'USD_COMPLETE','MISSING_END_FX'} else 'HKD') for a in assets}
    periods=pd.period_range('2020-01','2025-01',freq='M')
    observations=[]; timing=[]
    for aid in assets:
        for p in periods:
            if aid=='MISSING_MIDDLE' and str(p)=='2022-06': continue
            if aid=='SHORT_HISTORY' and p<=pd.Period('2020-02',freq='M'): continue
            date=p.end_time.date().isoformat(); start=(p-1).end_time.date().isoformat()
            observations.append(dict(asset_id=aid,date=date,value=.01,value_kind='total_return',currency=currencies[aid],frequency='monthly',source_file='synthetic.csv',source_sheet='',source_row=len(observations)+2,source_hash='synthetic'))
            us=currencies[aid]=='USD'; zone='America/New_York' if us else 'Asia/Hong_Kong'
            def price(d): return pd.Timestamp(d+'T16:00:00').tz_localize(zone).isoformat()
            finish=price(date)
            timing.append(dict(asset_id=aid,date=date,market_timezone=zone,price_start_at=price(start),price_end_at=finish,fx_start_at=start+'T21:00:00+00:00' if us else '',fx_end_at=date+'T21:00:00+00:00' if us else '',available_at=max(pd.Timestamp(finish),pd.Timestamp(date+'T21:00:00+00:00')).isoformat() if us else finish,source_name='Synthetic declared final monthly valuations'))
    # Distinct foreign currency preserves complete USD FX while withholding this asset's last quote.
    currencies['MISSING_END_FX']='EUR'
    for row in observations:
        if row['asset_id']=='MISSING_END_FX': row['currency']='EUR'
    fx=[]
    for p in pd.period_range('2019-12','2025-01',freq='M'):
        for currency in ['USD','EUR']:
            if currency=='EUR' and str(p)=='2025-01': continue
            fx.append(dict(date=p.end_time.date().isoformat(),currency=currency,hkd_per_unit=7.8 if currency=='USD' else 8.2,source_name='Synthetic FX'))
    bundle=DataBundle(assets=pd.DataFrame([dict(asset_id=a,currency=currencies[a]) for a in assets]),observations=pd.DataFrame(observations))
    return reconcile_hkd(bundle,pd.DataFrame(fx)).reconciliation,pd.DataFrame(timing),assets
