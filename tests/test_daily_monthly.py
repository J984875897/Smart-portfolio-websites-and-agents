import json
import socket
from pathlib import Path
import pandas as pd
import pytest


def sample():
    from portfolio.data.trading_calendar import trading_schedule
    days = trading_schedule('XNYS', '2024-12-01', '2025-02-01').date
    return pd.DataFrame({'date': days, 'adj_close': [100.0 if d < '2025-01' else 110.0 for d in days]})


def aggregate(prices, **kwargs):
    from portfolio.data.daily_monthly import aggregate_daily_prices
    return aggregate_daily_prices(prices, symbol='SPY', start_month='2025-01', end_month='2025-01', as_of='2025-02-02T00:00:00Z', **kwargs)


def test_calendar_official_dates_and_dst():
    from portfolio.data.trading_calendar import trading_schedule
    us = trading_schedule('XNYS', '2025-01-01', '2025-02-01')
    hk = trading_schedule('XHKG', '2025-01-01', '2025-02-01')
    assert len(us) == 20 and '2025-01-09' not in set(us.date)
    assert len(hk) == 19
    assert hk.set_index('date').loc['2025-01-28'].calendar_close_at == '2025-01-28T04:00:00+00:00'
    march = trading_schedule('XNYS', '2025-03-07', '2025-03-11').set_index('date')
    assert march.loc['2025-03-07'].calendar_close_at.endswith('21:00:00+00:00')
    assert march.loc['2025-03-10'].calendar_close_at.endswith('20:00:00+00:00')
    assert trading_schedule('XNYS', '2024-12-24', '2024-12-25').iloc[0].calendar_close_at.endswith('18:00:00+00:00')


def test_ratio_confirmation_nonmutation_and_reordering(monkeypatch):
    monkeypatch.setattr(socket, 'create_connection', lambda *a, **k: pytest.fail('network'))
    prices = sample(); original = prices.copy(deep=True)
    result = aggregate(prices, confirmed=True)
    assert result.returns.iloc[0].local_return == pytest.approx(.1)
    assert not result.returns.iloc[0].historical_eligible
    assert result.returns.iloc[0].available_at == ''
    assert pd.isna(aggregate(prices).returns.iloc[0].local_return)
    assert aggregate(prices.sample(frac=1), confirmed=True).returns.iloc[0].local_return == pytest.approx(.1)
    pd.testing.assert_frame_equal(prices, original)


def test_overflowing_endpoint_ratio_remains_blocked():
    prices = sample()
    prices['adj_close'] = [1e-308 if d < '2025-01' else 1e308 for d in prices.date]
    result = aggregate(prices, confirmed=True)
    assert (result.monthly.status == 'valid').all()
    assert result.returns.iloc[0].status == 'blocked'
    assert result.returns.iloc[0].reason == 'invalid_value'
    assert pd.isna(result.returns.iloc[0].local_return)


def test_duplicate_input_columns_are_rejected():
    prices = sample()
    prices = pd.concat([prices, prices[['adj_close']] * 2], axis=1)
    with pytest.raises(ValueError, match='unique'):
        aggregate(prices, confirmed=True)


@pytest.mark.parametrize('fault', ['previous', 'last', 'middle', 'duplicate', 'weekend', 'invalid_price', 'invalid_date', 'empty'])
def test_incomplete_months_block(fault):
    prices = sample()
    if fault == 'previous': prices = prices[prices.date >= '2025-01']
    elif fault == 'last': prices = prices[prices.date != '2025-01-31']
    elif fault == 'middle': prices = prices[prices.date != '2025-01-15']
    elif fault == 'duplicate': prices = pd.concat([prices, prices.iloc[[-1]]])
    elif fault == 'weekend': prices = pd.concat([prices, pd.DataFrame([{'date':'2025-01-04', 'adj_close':110}])])
    elif fault == 'invalid_price': prices.loc[prices.date == '2025-01-15', 'adj_close'] = float('inf')
    elif fault == 'invalid_date': prices.loc[0, 'date'] = 'bad'
    else: prices = prices.iloc[:0]
    result = aggregate(prices, confirmed=True)
    assert len(result.returns) == 1 and pd.isna(result.returns.iloc[0].local_return)
    assert result.returns.iloc[0].reason != 'ok'


def test_validation_and_maturity():
    from portfolio.data.daily_monthly import aggregate_daily_prices
    from portfolio.data.trading_calendar import trading_schedule
    with pytest.raises(ValueError): trading_schedule('XNYS', '2025-1-01', '2025-02-01')
    with pytest.raises(ValueError): trading_schedule('OTHER', '2025-01-01', '2025-02-01')
    with pytest.raises(ValueError): aggregate_daily_prices(sample(), symbol='SPY', start_month='2025-01', end_month='2025-01', as_of='2025-02-01')
    with pytest.raises(ValueError): aggregate_daily_prices(sample(), symbol='SPY', start_month='2025-01', end_month='2025-01', as_of='February 2, 2025 00:00 UTC')
    result = aggregate_daily_prices(sample(), symbol='SPY', start_month='2025-01', end_month='2025-01', confirmed=True, as_of='2025-02-01T04:59:59Z')
    assert pd.isna(result.returns.iloc[0].local_return)
    result = aggregate_daily_prices(sample(), symbol='SPY', start_month='2025-01', end_month='2025-01', confirmed=True, as_of='2025-02-01T05:00:00Z')
    assert result.returns.iloc[0].local_return == pytest.approx(.1)


@pytest.mark.parametrize('boolean_price', [True, False])
def test_readonly_cache_rejects_raw_boolean_adjusted_endpoint(tmp_path, boolean_price):
    from portfolio.data.monthly_cache import cached_monthly_prices
    from portfolio.data.updates import run_update
    from portfolio.data.providers.base import RawResponse
    from portfolio.data.snapshots import MANIFEST
    days = sample()
    adjusted = list(days.adj_close)
    adjusted[-1] = boolean_price
    payload = {'chart': {'error': None, 'result': [{
        'meta': {'symbol': 'SPY', 'currency': 'USD', 'instrumentType': 'ETF',
                 'exchangeTimezoneName': 'America/New_York'},
        'timestamp': [int(pd.Timestamp(d, tz='America/New_York').timestamp()) for d in days.date],
        'indicators': {
            'quote': [{**{k: list(days.adj_close) for k in ['open', 'high', 'low', 'close']},
                       'volume': [1] * len(days)}],
            'adjclose': [{'adjclose': adjusted}],
        },
    }]}}
    raw = json.dumps(payload).encode()
    run = run_update(tmp_path, ['SPY'], '2024-12-01', '2025-02-01',
                     fetch=lambda *a: RawResponse(raw, 200))
    folder = tmp_path / 'runs' / run
    manifest = json.loads((folder / MANIFEST).read_text())
    assert (folder / manifest['items'][0]['raw_file']).read_bytes() == raw
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    with pytest.raises(ValueError, match='boolean adjusted price'):
        cached_monthly_prices(tmp_path, run, 'SPY', start_month='2025-01',
                              end_month='2025-01', confirmed=True,
                              as_of='2025-02-02T00:00:00Z')
    assert before == {p.name: p.read_bytes() for p in folder.iterdir()}


@pytest.mark.parametrize('fault', ['none', 'hash', 'identity', 'partial', 'unavailable'])
def test_readonly_cache(tmp_path, fault):
    from portfolio.data.monthly_cache import cached_monthly_prices
    from portfolio.data.updates import run_update
    from portfolio.data.providers.base import RawResponse
    from portfolio.data.snapshots import MANIFEST, digest
    days = sample()
    payload = {'chart': {'error':None, 'result':[{'meta':{'symbol':'SPY', 'currency':'USD', 'instrumentType':'ETF', 'exchangeTimezoneName':'America/New_York'}, 'timestamp':[int(pd.Timestamp(d, tz='America/New_York').timestamp()) for d in days.date], 'indicators':{'quote':[{**{k:list(days.adj_close) for k in ['open','high','low','close']}, 'volume':[1]*len(days)}], 'adjclose':[{'adjclose':list(days.adj_close)}]}}]}}
    if fault == 'identity': payload['chart']['result'][0]['meta']['currency'] = 'HKD'
    run = run_update(tmp_path, ['SPY'], '2024-12-01', '2025-02-01', fetch=lambda *a:RawResponse(json.dumps(payload).encode(), 200))
    folder = tmp_path/'runs'/run; manifest_path = folder/MANIFEST
    manifest = json.loads(manifest_path.read_text())
    if fault == 'hash': (folder/manifest['items'][0]['raw_file']).write_bytes(b'bad')
    if fault in {'partial','unavailable'}:
        manifest['items'][0]['status'] = fault
        manifest['items'][0]['import_file'] = None
        manifest['files'] = [f for f in manifest['files'] if not f['path'].startswith('import_')]
        manifest_path.write_text(json.dumps(manifest))
    before = {p.name:p.read_bytes() for p in folder.iterdir()}
    if fault in {'hash','identity','unavailable'}:
        with pytest.raises(ValueError): cached_monthly_prices(tmp_path, run, 'SPY', start_month='2025-01', end_month='2025-01', confirmed=True, as_of='2025-02-02T00:00:00Z')
    else:
        result = cached_monthly_prices(tmp_path, run, 'SPY', start_month='2025-01', end_month='2025-01', confirmed=True, as_of='2025-02-02T00:00:00Z')
        assert result.metadata['manifest'] == manifest
        if fault == 'partial': assert result.returns.iloc[0].reason == 'source_not_success'
        else: assert result.returns.iloc[0].local_return == pytest.approx(.1)
    assert before == {p.name:p.read_bytes() for p in folder.iterdir()}


def test_cache_rejects_unlocatable_raw_price_before_filter(tmp_path):
    from portfolio.data.monthly_cache import cached_monthly_prices
    from portfolio.data.updates import run_update
    from portfolio.data.providers.base import RawResponse
    from portfolio.data.snapshots import MANIFEST
    days = sample()
    values = list(days.adj_close) + [120.0]
    payload = {'chart': {'error': None, 'result': [{
        'meta': {'symbol': 'SPY', 'currency': 'USD', 'instrumentType': 'ETF', 'exchangeTimezoneName': 'America/New_York'},
        'timestamp': [int(pd.Timestamp(d, tz='America/New_York').timestamp()) for d in days.date] + [None],
        'indicators': {'quote': [{**{k: values for k in ['open', 'high', 'low', 'close']}, 'volume': [1000] * len(values)}], 'adjclose': [{'adjclose': values}]},
    }]}}
    raw = json.dumps(payload).encode()
    run = run_update(tmp_path, ['SPY'], '2024-12-01', '2025-02-01', fetch=lambda *a: RawResponse(raw, 200))
    folder = tmp_path / 'runs' / run
    assert json.loads((folder / MANIFEST).read_text())['items'][0]['status'] == 'success'
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    with pytest.raises(ValueError, match='timestamp'):
        cached_monthly_prices(tmp_path, run, 'SPY', start_month='2025-01', end_month='2025-01', confirmed=True, as_of='2025-02-02T00:00:00Z')
    assert before == {p.name: p.read_bytes() for p in folder.iterdir()}
