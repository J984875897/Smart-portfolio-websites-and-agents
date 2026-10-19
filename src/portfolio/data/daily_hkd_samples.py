"""Clearly synthetic offline examples for the daily HKD preview."""
import pandas as pd
from .daily_monthly import aggregate_daily_prices
from .trading_calendar import trading_schedule


def _months(start_month, end_month):
    aggregate_daily_prices(pd.DataFrame(columns=['date', 'adj_close']), symbol='SPY',
                           start_month=start_month, end_month=end_month)
    return pd.period_range(pd.Period(start_month, freq='M') - 1, end_month, freq='M')


def sample_daily_prices(symbol, start_month, end_month, case='完整报价'):
    months = _months(start_month, end_month)
    schedule = trading_schedule('XHKG' if symbol.endswith('.HK') else 'XNYS',
                                months[0].start_time.strftime('%Y-%m-%d'),
                                (months[-1] + 1).start_time.strftime('%Y-%m-%d'))
    frame = schedule[['date']].copy()
    frame['adj_close'] = frame.date.map(lambda d: 100 * 1.1 ** (pd.Period(d[:7], freq='M').ordinal - months[0].ordinal))
    if case == '缺最后交易日':
        target = frame.index[frame.date.str.startswith(end_month)]
        if len(target): frame = frame.drop(target[-1])
    elif case != '完整报价':
        raise ValueError('unknown synthetic price case')
    frame.attrs['source_name'] = 'SYNTH 人工合成价格 / ' + case
    return frame


def sample_daily_fx(start_month, end_month, case='完整汇率'):
    months = _months(start_month, end_month)
    frame = pd.DataFrame([dict(date=m.end_time.strftime('%Y-%m-%d'), currency='USD',
                               hkd_per_unit=round(7.8 + .1 * n, 10), source_name='SYNTH 人工合成汇率')
                          for n, m in enumerate(months)])
    if case == '缺期末月': frame = frame.iloc[:-1].copy()
    elif case == '过旧': frame.loc[frame.index[-1], 'date'] = (months[-1].end_time.normalize() - pd.Timedelta(days=8)).strftime('%Y-%m-%d')
    elif case == '重复末日': frame = pd.concat([frame, frame.iloc[[-1]]], ignore_index=True)
    elif case != '完整汇率': raise ValueError('unknown synthetic FX case')
    frame.attrs.update(source_name='SYNTH 人工合成汇率 / ' + case, source_status='success', synthetic=True)
    return frame
