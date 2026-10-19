"""Fixed monthly windows based on importer-declared availability evidence."""
from dataclasses import dataclass
from datetime import datetime
import hashlib
import re
import pandas as pd
from .returns import strict_date, finite_number
from .quality import CURRENCIES

TIMING_FIELDS = ['asset_id','date','market_timezone','price_start_at','price_end_at','fx_start_at','fx_end_at','available_at','source_name']

@dataclass
class AlignmentResult:
    report: pd.DataFrame
    coverage: pd.DataFrame
    matrix: pd.DataFrame
    window_start: str
    window_end: str
    decision_at: str


def _instant(value):
    if not isinstance(value,str) or 'T' not in value:
        return None
    try:
        parsed=datetime.fromisoformat(value)
        if parsed.utcoffset() is None: return None
        return pd.Timestamp(parsed).tz_convert('UTC')
    except (ValueError, TypeError, OverflowError): return None


def align_monthly(reconciliation, timing, *, asset_ids, end_month, decision_at, months=60):
    """Derive coverage without changing inputs; every failed period prevents inclusion."""
    if not isinstance(end_month,str) or not re.fullmatch(r'\d{4}-\d{2}',end_month): raise ValueError('end_month must be YYYY-MM')
    try: end=pd.Period(end_month,freq='M')
    except ValueError: raise ValueError('invalid end_month') from None
    decision=_instant(decision_at)
    if decision is None: raise ValueError('decision_at must be aware ISO datetime')
    if isinstance(months,bool) or not isinstance(months,int) or months<=0: raise ValueError('months must be a positive integer')
    if end>pd.Period(decision.tz_convert('Asia/Hong_Kong').strftime('%Y-%m'),freq='M'): raise ValueError('future end_month')
    if not reconciliation.columns.is_unique or not timing.columns.is_unique: raise ValueError('columns must be unique')
    aids=sorted(set(asset_ids))
    if any(not isinstance(x,str) or not x.strip() for x in aids): raise ValueError('invalid asset_ids')
    periods=pd.period_range(end=end,periods=months,freq='M')
    dates=[p.end_time.date().isoformat() for p in periods]
    def groups(frame):
        output={}
        for row in frame.to_dict('records'):
            date=strict_date(row.get('date'))
            if date: output.setdefault((row.get('asset_id'),date.strftime('%Y-%m')),[]).append(row)
        return output
    rec=groups(reconciliation)
    # pandas retains attrs after slicing/reordering; positional provenance would
    # silently point at the wrong physical source row. Bind the complete frame.
    if 'raw_bytes' in timing.attrs:
        from .importer import read_file
        try:
            loaded=read_file(timing.attrs['raw_bytes'],filename=timing.attrs.get('source_file'),sheet_name=timing.attrs.get('source_sheet') or 0)
        except (ValueError, TypeError, IndexError, KeyError) as exc:
            raise ValueError('file-backed timing must be an unchanged read_file frame') from exc
        if not timing.equals(loaded) or not timing.index.equals(loaded.index):
            raise ValueError('file-backed timing must be an unchanged read_file frame; reload the original file')
        # Only reparsed metadata is authoritative, including physical CSV lines.
        timing=loaded
    evidence=timing.copy(deep=True)
    digest=hashlib.sha256(timing.attrs.get('raw_bytes',timing.to_csv(index=False).encode())).hexdigest()
    rows=evidence.to_dict('records'); physical=timing.attrs.get('source_rows',list(range(2,len(rows)+2)))
    for i,row in enumerate(rows):
        for field,value in [('source_file',timing.attrs.get('source_file','dataframe.csv')),('source_sheet',timing.attrs.get('source_sheet','')),('source_row',physical[i]),('source_hash',digest)]:
            if 'raw_bytes' in timing.attrs or field not in row: row[field]=value
    times=groups(pd.DataFrame(rows))
    coverage=[]; reports=[]; columns={}
    for aid in aids:
        asset_rows=[]
        for p,date in zip(periods,dates):
            rr=rec.get((aid,str(p)),[]); tt=times.get((aid,str(p)),[])
            reasons=[]
            row={'asset_id':aid,'date':date,'status':'blocked','reason':'','hkd_return':float('nan'),'reconciliation_evidence':rr,'timing_evidence':tt}
            if len(rr)!=1: reasons.append('missing_return' if not rr else 'ambiguous_return')
            else:
                original=rr[0]; row.update({'reconciliation_'+k:v for k,v in original.items()})
                if original.get('status')!='valid': reasons.append(str(original.get('reason') or 'invalid_reconciliation'))
                number=finite_number(original.get('hkd_return'))
                if number is None or number < -1: reasons.append('invalid_hkd_return')
                else: row['hkd_return']=number
                start=(p-1).end_time.date().isoformat()
                if original.get('date')!=date or original.get('end_date')!=date or original.get('start_date')!=start: reasons.append('invalid_period_labels')
                if original.get('currency') not in CURRENCIES: reasons.append('invalid_currency')
            if len(tt)!=1: reasons.append('missing_timing' if not tt else 'ambiguous_timing')
            else:
                t=tt[0]; row.update({'timing_'+k:v for k,v in t.items()})
                zone=t.get('market_timezone')
                if zone not in {'Asia/Hong_Kong','America/New_York'}: reasons.append('invalid_market_timezone')
                else:
                    if decision.tz_convert(zone).date() < p.end_time.date(): reasons.append('period_not_complete_at_decision')
                if len(rr)==1 and rr[0].get('currency')!='HKD' and decision.date() < p.end_time.date():
                    reasons.append('period_not_complete_at_decision')
                if t.get('date')!=date: reasons.append('invalid_timing_date')
                if not isinstance(t.get('source_name'),str) or not t['source_name'].strip(): reasons.append('missing_source_name')
                observations={}; fields=['price_start_at','price_end_at']
                if len(rr)==1 and rr[0].get('currency')!='HKD': fields+=['fx_start_at','fx_end_at']
                for field in fields:
                    instant=_instant(t.get(field)); observations[field]=instant
                    if instant is None: reasons.append('invalid_'+field); continue
                    target=p-1 if 'start' in field else p
                    local=instant.tz_convert('UTC' if field.startswith('fx') else (zone if zone in {'Asia/Hong_Kong','America/New_York'} else 'UTC'))
                    if local.strftime('%Y-%m')!=str(target): reasons.append('wrong_month_'+field)
                    elif (target.end_time.date()-local.date()).days>7: reasons.append('stale_'+field)
                for kind in ['price','fx']:
                    first=observations.get(kind+'_start_at'); last=observations.get(kind+'_end_at')
                    if first is not None and last is not None and first>last: reasons.append('inverted_'+kind+'_times')
                available=_instant(t.get('available_at'))
                if available is None: reasons.append('invalid_available_at')
                else:
                    if any(x is not None and available<x for x in observations.values()): reasons.append('availability_before_observation')
                    if available>decision: reasons.append('not_available_at_decision')
            row['reason']=';'.join(dict.fromkeys(reasons)) or 'ok'; row['status']='blocked' if reasons else 'valid'
            coverage.append(row); asset_rows.append(row)
        valid=sum(r['status']=='valid' for r in asset_rows)
        reason=';'.join(dict.fromkeys(code for r in asset_rows for code in r['reason'].split(';') if code!='ok')) or 'ok'
        if asset_rows and asset_rows[0]['reason'].startswith('missing_return'): reason='window_start_history_insufficient;'+reason
        reports.append(dict(asset_id=aid,status='eligible' if valid==months else 'excluded',valid_months=valid,missing_months=months-valid,reason=reason))
        if valid==months: columns[aid]=[r['hkd_return'] for r in asset_rows]
    matrix=pd.DataFrame(columns,index=pd.Index(dates,name='date'),dtype=float)
    return AlignmentResult(pd.DataFrame(reports,columns=['asset_id','status','valid_months','missing_months','reason']),pd.DataFrame(coverage) if coverage else pd.DataFrame(columns=['asset_id','date','status','reason','hkd_return','reconciliation_evidence','timing_evidence']),matrix,dates[0],dates[-1],decision.isoformat())
