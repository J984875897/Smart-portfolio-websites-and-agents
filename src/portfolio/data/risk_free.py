"""Declared HKD cash proxy, with fixed windows and conservative timing checks."""
from dataclasses import dataclass
import hashlib
import math
import re
import pandas as pd
from .alignment import _instant
from .returns import strict_date, finite_number

QUOTE_FIELDS=['date','quote_at','available_at','quote_percent','currency','benchmark','tenor','day_count','compounding','source_name']


@dataclass
class RiskFreeResult:
    report: pd.DataFrame
    series: pd.Series
    available: bool
    window_start: str
    window_end: str
    decision_at: str
    currency: str='HKD'
    frequency: str='monthly'
    proxy_method: str='hibor_1m_simple_act365f'


def risk_free_monthly(quotes: pd.DataFrame, *, end_month: str, decision_at: str, months: int=60) -> RiskFreeResult:
    """Return one row per target natural month; failed returns remain NaN."""
    if not isinstance(end_month,str) or not re.fullmatch(r'\d{4}-\d{2}',end_month):
        raise ValueError('end_month must be YYYY-MM')
    try: end=pd.Period(end_month,freq='M')
    except ValueError: raise ValueError('invalid end_month') from None
    decision=_instant(decision_at)
    if decision is None: raise ValueError('decision_at must be aware ISO datetime')
    if isinstance(months,bool) or not isinstance(months,int) or months<=0: raise ValueError('months must be a positive integer')
    if not quotes.columns.is_unique: raise ValueError('columns must be unique')
    if not set(QUOTE_FIELDS)<=set(quotes.columns): raise ValueError('missing required quote columns')
    if 'raw_bytes' in quotes.attrs:
        from .importer import read_file
        try:
            loaded=read_file(quotes.attrs['raw_bytes'],filename=quotes.attrs.get('source_file'),sheet_name=quotes.attrs.get('source_sheet') or 0)
        except (ValueError,TypeError,IndexError,KeyError) as exc:
            raise ValueError('file-backed quotes must be an unchanged read_file frame') from exc
        if not quotes.equals(loaded) or not quotes.index.equals(loaded.index):
            raise ValueError('file-backed quotes must be an unchanged read_file frame; reload the original file')
        quotes=loaded
    periods=pd.period_range(end=end,periods=months,freq='M')
    digest=hashlib.sha256(quotes.attrs.get('raw_bytes',quotes.to_csv(index=False).encode())).hexdigest()
    rows=quotes.to_dict('records'); file_backed='raw_bytes' in quotes.attrs
    physical=quotes.attrs.get('source_rows',list(range(2,len(rows)+2))) if file_backed else list(range(2,len(rows)+2))
    groups={}; invalid=[]
    for i,row in enumerate(rows):
        row.update(source_file=quotes.attrs.get('source_file','dataframe.csv') if file_backed else 'dataframe.csv',source_sheet=quotes.attrs.get('source_sheet','') if file_backed else '',source_row=physical[i],source_hash=digest)
        parsed=strict_date(row['date'])
        if parsed is None: invalid.append(row)
        else: groups.setdefault(parsed.strftime('%Y-%m'),[]).append(row)
    reports=[]
    for p in periods:
        date=p.end_time.date().isoformat(); start=(p-1).end_time.date().isoformat()
        start_at=pd.Timestamp(start+'T16:00:00',tz='Asia/Hong_Kong'); end_at=pd.Timestamp(date+'T16:00:00',tz='Asia/Hong_Kong')
        days=(end_at.date()-start_at.date()).days
        selected=groups.get(str(p),[]); reasons=[]
        row=dict(date=date,start_date=start,end_date=date,start_at=start_at.isoformat(),end_at=end_at.isoformat(),days=days,status='blocked',reason='',rf_hkd=float('nan'),quote_evidence=selected+invalid)
        # An unassignable date cannot be safely attributed to a month: fail closed.
        if invalid: reasons.append('invalid_date')
        if end_at>decision: reasons.append('period_not_complete_at_decision')
        if len(selected)!=1: reasons.append('missing_quote' if not selected else 'ambiguous_quote')
        else:
            q=selected[0]; row.update({'quote_'+key:value for key,value in q.items()})
            if q['date']!=date: reasons.append('invalid_period_label')
            for field,value in [('currency','HKD'),('benchmark','HKAB_HIBOR'),('tenor','1M'),('day_count','ACT/365F'),('compounding','simple')]:
                if not isinstance(q[field],str) or q[field]!=value: reasons.append('invalid_'+field)
            if not isinstance(q['source_name'],str) or not q['source_name'].strip(): reasons.append('missing_source_name')
            quote=_instant(q['quote_at']); available=_instant(q['available_at'])
            if quote is None: reasons.append('invalid_quote_at')
            else:
                if quote>start_at: reasons.append('quote_after_start')
                if start_at-quote>pd.Timedelta(days=7): reasons.append('stale_quote')
            if available is None: reasons.append('invalid_available_at')
            else:
                if quote is not None and available<quote: reasons.append('availability_before_quote')
                if available>start_at: reasons.append('availability_after_start')
                if available>decision: reasons.append('not_available_at_decision')
            rate=finite_number(q['quote_percent'])
            if rate is None: reasons.append('invalid_quote_percent')
            else:
                value=rate/100*days/365
                if not math.isfinite(value) or value < -1: reasons.append('invalid_rf_hkd')
                elif not reasons: row['rf_hkd']=value
        row['reason']=';'.join(dict.fromkeys(reasons)) or 'ok'; row['status']='blocked' if reasons else 'valid'
        reports.append(row)
    report=pd.DataFrame(reports)
    series=pd.Series(report.rf_hkd.to_numpy(),index=pd.Index(report.date,name='date'),name='rf_hkd',dtype=float)
    return RiskFreeResult(report,series,bool((report.status=='valid').all()),report.date.iloc[0],report.date.iloc[-1],decision.isoformat())
