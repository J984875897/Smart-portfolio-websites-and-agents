"""Conservative daily completeness diagnostics and original currency previews."""
from dataclasses import dataclass
import hashlib
import re
import pandas as pd
from .contracts import DataBundle
from .returns import build_local_returns, strict_date, finite_number
from .providers.yahoo import CATALOG
from .trading_calendar import trading_schedule, TIMEZONES, CALENDAR_VERSION


@dataclass
class DailyMonthlyResult:
    sessions: pd.DataFrame
    monthly: pd.DataFrame
    returns: pd.DataFrame
    metadata: dict


def aggregate_daily_prices(prices, *, symbol, start_month, end_month, confirmed=False, as_of=None):
    if symbol not in CATALOG or symbol == 'HKD=X':
        raise ValueError('select one of the six price samples')
    for month in (start_month, end_month):
        if not isinstance(month, str) or not re.fullmatch(r'\d{4}-\d{2}', month) or not '2015-01' <= month <= '2026-12':
            raise ValueError('month must be YYYY-MM within 2015–2026')
        try: pd.Period(month, freq='M')
        except ValueError as error: raise ValueError('invalid month') from error
    if start_month > end_month: raise ValueError('start month must precede end month')
    try:
        if as_of is not None and (not isinstance(as_of, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})', as_of)):
            raise ValueError('as_of requires timezone ISO timestamp')
        now = pd.Timestamp.now(tz='UTC') if as_of is None else pd.Timestamp(as_of)
        if now.tzinfo is None or pd.isna(now): raise ValueError('as_of requires timezone')
    except (TypeError, ValueError) as error: raise ValueError('as_of requires timezone ISO timestamp') from error
    if not isinstance(prices, pd.DataFrame) or not {'date','adj_close'} <= set(prices.columns):
        raise ValueError('date and adj_close columns required')
    if not prices.columns.is_unique:
        raise ValueError('input column names must be unique')
    identity = CATALOG[symbol]; market = 'XHKG' if identity['currency'] == 'HKD' else 'XNYS'
    months = pd.period_range(pd.Period(start_month, freq='M')-1, end_month, freq='M')
    start = months[0].start_time.strftime('%Y-%m-%d'); end = (months[-1]+1).start_time.strftime('%Y-%m-%d')
    schedule = trading_schedule(market, start, end)
    source_hash = prices.attrs.get('source_hash') or hashlib.sha256(prices.to_csv(index=False).encode()).hexdigest()
    metadata = dict(symbol=symbol, calendar=market, calendar_version=CALENDAR_VERSION, market_timezone=TIMEZONES[market],
                    calendar_mapping='XHKG cash market' if market == 'XHKG' else 'XNYS cash market proxy',
                    currency=identity['currency'], source_name=prices.attrs.get('source_name','manual'), source_hash=source_hash,
                    available_at='', historical_eligible=False, as_of=now.isoformat(), confirmed=confirmed is True,
                    quality_scope='calendar price preview only; not historical eligibility')
    groups = {}; invalid = []
    for n, row in enumerate(prices.to_dict('records'), 1):
        day = row['date']
        item = dict(date=day, adj_close=row['adj_close'], source_row=row.get('source_row',n))
        if strict_date(day) is None: invalid.append({**item,'status':'invalid_date'})
        elif start <= day < end: groups.setdefault(day, []).append(item)
    sessions = []
    closes = schedule.set_index('date').calendar_close_at.to_dict()
    for day in sorted(set(closes) | set(groups)):
        items = groups.get(day, [])
        if not items: sessions.append(dict(date=day, adj_close=float('nan'), source_row='', status='missing_price', calendar_close_at=closes[day]))
        for item in items:
            number = finite_number(item['adj_close'])
            status = 'duplicate_date' if len(items)>1 else ('unexpected_session' if day not in closes else ('invalid_price' if number is None or number<=0 else 'ok'))
            sessions.append({**item,'status':status,'calendar_close_at':closes.get(day,'')})
    sessions.extend({**row,'calendar_close_at':''} for row in invalid)
    sessions = pd.DataFrame(sessions, columns=['date','adj_close','source_row','status','calendar_close_at'])
    monthly = []
    for month in months:
        label = str(month); expected = schedule[schedule.date.str.startswith(label)]
        observed = sessions[sessions.date.map(lambda d:isinstance(d,str) and d.startswith(label))]
        missing = list(observed.loc[observed.status == 'missing_price','date'])
        failures = sorted(set(observed.status)-{'ok'})
        if invalid: failures.append('invalid_date')
        mature = (month+1).start_time.tz_localize(TIMEZONES[market]) <= now
        if not mature: failures.append('month_not_mature')
        last = expected.iloc[-1] if len(expected) else None
        valid = not failures and last is not None
        actual = observed[observed.source_row != '']
        monthly.append(dict(date=month.end_time.strftime('%Y-%m-%d'), month=label,
            expected_end_date=last.date if last is not None else '', last_observed_date=max(actual.date) if len(actual) else '',
            end_price=float(groups[last.date][0]['adj_close']) if valid else float('nan'),
            calendar_close_at=last.calendar_close_at if last is not None else '', expected_sessions=len(expected),
            valid_sessions=int((observed.status=='ok').sum()), missing_dates=missing, status='valid' if valid else 'blocked', reason=';'.join(failures) or 'ok'))
    monthly = pd.DataFrame(monthly)
    observations = pd.DataFrame([dict(date=r.date, asset_id=symbol, value=r.end_price, value_kind='adjusted_price', currency=identity['currency'], frequency='monthly', source_hash=source_hash) for r in monthly.itertuples() if r.status=='valid'])
    bundle = DataBundle(assets=pd.DataFrame([dict(asset_id=symbol,currency=identity['currency'])]), observations=observations)
    calculated = build_local_returns(bundle, adjusted_price_assets=[symbol] if confirmed is True else [])
    rows = []
    for i in range(1,len(monthly)):
        current, previous = monthly.iloc[i], monthly.iloc[i-1]
        found = calculated[calculated.date == current.date]
        row = found.iloc[0].to_dict() if len(found) else dict(date=current.date,local_return=float('nan'))
        reason = current.reason if current.status!='valid' else ('previous_month:'+previous.reason if previous.status!='valid' else ('unconfirmed_adjusted_price' if confirmed is not True else 'ok'))
        if reason == 'ok' and len(found) and row['status'] != 'valid':
            reason = row['reason']
        row.update({k:v for k,v in metadata.items() if k in {'calendar','calendar_version','market_timezone','currency','source_name','source_hash','available_at','historical_eligible'}})
        row.update(status='valid' if reason=='ok' else 'blocked',reason=reason)
        if reason!='ok': row['local_return']=float('nan')
        rows.append(row)
    return DailyMonthlyResult(sessions, monthly, pd.DataFrame(rows), metadata)
