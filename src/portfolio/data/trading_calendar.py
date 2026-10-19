"""Pinned market calendar proxies; close labels are not publication evidence."""
from importlib.metadata import version
import pandas as pd
import exchange_calendars as xcals
from .returns import strict_date

CALENDAR_VERSION = version('exchange_calendars')
TIMEZONES = {'XNYS':'America/New_York', 'XHKG':'Asia/Hong_Kong'}


def trading_schedule(market, start, end):
    if market not in TIMEZONES or strict_date(start) is None or strict_date(end) is None:
        raise ValueError('market and strict YYYY-MM-DD dates required')
    if not '2014-01-01' <= start < end <= '2027-01-01':
        raise ValueError('calendar range must be within 2014–2026')
    calendar = xcals.get_calendar(market, start='2014-01-01', end='2026-12-31')
    schedule = calendar.schedule
    selected = schedule.loc[(schedule.index >= pd.Timestamp(start)) & (schedule.index < pd.Timestamp(end))]
    return pd.DataFrame({'date':selected.index.strftime('%Y-%m-%d'),
                         'calendar_close_at':[x.isoformat() for x in selected['close']],
                         'market_timezone':TIMEZONES[market], 'calendar':market,
                         'calendar_version':CALENDAR_VERSION})
