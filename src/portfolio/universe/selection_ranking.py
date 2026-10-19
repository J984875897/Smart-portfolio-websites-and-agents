"""As-of, source-declared cost and liquidity metadata; missing is never zero."""
from numbers import Real

import numpy as np
import pandas as pd
from .input_evidence import frame_evidence, verified_frame

FIELDS=['asset_id','metric','value','source_reference','available_at']
METRICS={'annual_fee_rate','avg_daily_turnover_hkd'}


def _timestamp(value):
    if not isinstance(value,str) or not value.strip():
        raise ValueError('ranking available_at must be a timezone-aware timestamp')
    try:
        t=pd.Timestamp(value)
        if pd.isna(t) or t.tzinfo is None: raise ValueError()
        return t.tz_convert('UTC')
    except (TypeError,ValueError,OverflowError) as exc:
        raise ValueError('ranking available_at must be a timezone-aware timestamp') from exc


def prepare_ranking(data, *, asset_ids, decision_at):
    """Return one row per eligible ID and canonical declared records for evidence."""
    cutoff=_timestamp(decision_at)
    if data is None: data=pd.DataFrame(columns=FIELDS)
    checked=verified_frame(data,'ranking_data')
    file_evidence=frame_evidence(checked) if 'raw_bytes' in checked.attrs else None
    if not set(FIELDS) <= set(checked.columns):
        raise ValueError('ranking_data requires '+', '.join(FIELDS))
    records=[];seen=set();future=0
    for row in checked[FIELDS].to_dict('records'):
        aid=row['asset_id'];metric=row['metric'];value=row['value']
        if file_evidence is not None and isinstance(value,str):
            try: value=float(value) if value.strip() else None
            except ValueError as exc:
                raise ValueError('file ranking values must be numeric decimals or empty') from exc
        if not isinstance(aid,str) or aid not in asset_ids:
            raise ValueError('ranking asset_id must belong to the candidate input')
        if not isinstance(metric,str) or metric not in METRICS:
            raise ValueError('unknown ranking metric')
        if (isinstance(value,(bool,np.bool_)) or
            (value is not None and value is not pd.NA and not isinstance(value,Real))):
            raise ValueError('ranking values must be real numbers or missing')
        missing=value is None or value is pd.NA or np.isnan(value)
        if not missing and (not np.isfinite(value) or value < 0 or
                            (metric == 'annual_fee_rate' and value > 1)):
            raise ValueError('invalid ranking value or unit')
        if not isinstance(row['source_reference'],str) or not row['source_reference'].strip():
            raise ValueError('ranking source_reference required')
        available=_timestamp(row['available_at']);key=(aid,metric,available.isoformat())
        if key in seen: raise ValueError('duplicate ranking asset/metric/available_at')
        seen.add(key)
        future+=int(available > cutoff)
        records.append(dict(asset_id=aid,metric=metric,value=None if missing else float(value),
                            source_reference=row['source_reference'],available_at=available.isoformat()))
    records.sort(key=lambda r:(r['asset_id'],r['metric'],r['available_at']))
    table=pd.DataFrame(index=pd.Index(sorted(asset_ids),name='asset_id'))
    for metric,prefix in [('annual_fee_rate','fee'),('avg_daily_turnover_hkd','liquidity')]:
        table[metric]=np.nan
        table[prefix+'_status']='unknown'
        table[prefix+'_source_reference']=''
        table[prefix+'_available_at']=''
    for row in records:
        if pd.Timestamp(row['available_at']) > cutoff: continue
        prefix='fee' if row['metric'] == 'annual_fee_rate' else 'liquidity'
        table.loc[row['asset_id'],row['metric']]=np.nan if row['value'] is None else row['value']
        table.loc[row['asset_id'],prefix+'_status']='known' if row['value'] is not None else 'unknown'
        table.loc[row['asset_id'],prefix+'_source_reference']=row['source_reference']
        table.loc[row['asset_id'],prefix+'_available_at']=row['available_at']
    evidence=dict(basis='importer_declared_not_supplier_certified',decision_utc=cutoff.isoformat(),
                  file_evidence=file_evidence,
                  future_records_ignored=future,records=records,
                  quality_basis='S05_qualified_60_months_all_tied',
                  ranking_order=['new_known_cluster','valid_months_desc','known_fee_then_low_fee',
                                 'known_liquidity_then_high_HKD_turnover','asset_id'],
                  freshness_limit_enforced=False,fees_subtracted_from_returns=False)
    return table,evidence


def ranking_key(row):
    fee=row['annual_fee_rate'];liquidity=row['avg_daily_turnover_hkd']
    return (-int(row['valid_months']),pd.isna(fee),0. if pd.isna(fee) else float(fee),
            pd.isna(liquidity),0. if pd.isna(liquidity) else -float(liquidity),row['asset_id'])
