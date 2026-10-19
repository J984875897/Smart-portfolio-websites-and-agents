"""Explicit month-end total returns; never mutates imported source tables."""
from datetime import datetime, timedelta
import calendar
import math
import pandas as pd
from .quality import CURRENCIES, FREQUENCIES

SOURCE_FIELDS = ['source_file', 'source_sheet', 'source_row', 'source_hash']
LOCAL_COLUMNS = ['asset_id', 'date', 'start_date', 'end_date', 'currency', 'value_kind', 'frequency', 'value', 'local_return', 'start_price', 'end_price', 'status', 'reason', *SOURCE_FIELDS, *['start_'+x for x in SOURCE_FIELDS]]


def strict_date(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.strptime(value, '%Y-%m-%d').date()
        return parsed if parsed.isoformat() == value else None
    except ValueError:
        return None


def finite_number(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError, OverflowError):
        return None


def build_local_returns(bundle, *, adjusted_price_assets=()):
    """One result per observation, including failures; evidence joins by asset/date."""
    rows = bundle.observations.to_dict('records')
    confirmed = set(adjusted_price_assets)
    assets = {}
    for asset in bundle.assets.to_dict('records'):
        assets.setdefault(asset.get('asset_id'), []).append(asset)
    groups = {}
    parsed = [strict_date(r.get('date')) for r in rows]
    for i, (row, date) in enumerate(zip(rows, parsed)):
        if date:
            groups.setdefault((row.get('asset_id'), date.year, date.month), []).append(i)
    output = []
    for row, date in zip(rows, parsed):
        out = {x: row.get(x, '') for x in LOCAL_COLUMNS}
        out.update(local_return=float('nan'), start_price=float('nan'), end_price=float('nan'), start_date='', end_date=row.get('date', ''), status='blocked', reason='')
        reason = ''
        aid = row.get('asset_id')
        currency = row.get('currency')
        number = finite_number(row.get('value'))
        metadata = assets.get(aid, [])
        if date is None: reason = 'invalid_date'
        elif len(groups[(aid, date.year, date.month)]) > 1: reason = 'ambiguous_asset_month'
        elif currency not in CURRENCIES: reason = 'invalid_currency'
        elif len(metadata) != 1: reason = 'unknown_asset' if not metadata else 'ambiguous_asset_metadata'
        elif metadata[0].get('currency') != currency: reason = 'currency_conflict'
        elif row.get('frequency') not in FREQUENCIES: reason = 'invalid_frequency'
        elif row.get('frequency') != 'monthly' or date.day != calendar.monthrange(date.year, date.month)[1]: reason = 'alignment_required'
        elif number is None: reason = 'invalid_value'
        elif row.get('value_kind') in {'price', 'price_return'}: reason = 'not_total_return'
        elif row.get('value_kind') not in {'total_return', 'adjusted_price'}: reason = 'invalid_value_kind'
        elif row.get('value_kind') == 'total_return' and number < -1: reason = 'invalid_value'
        elif row.get('value_kind') == 'adjusted_price' and number <= 0: reason = 'invalid_value'
        elif row.get('value_kind') == 'adjusted_price' and aid not in confirmed: reason = 'unconfirmed_adjusted_price'
        if date:
            start = date.replace(day=1) - timedelta(days=1)
            out['start_date'] = start.isoformat()
        if not reason and row['value_kind'] == 'total_return':
            out['local_return'] = number
        elif not reason:
            out['end_price'] = number
            indices = groups.get((aid, start.year, start.month), [])
            if not indices:
                earlier = any(d and d < date and r.get('asset_id') == aid for r, d in zip(rows, parsed))
                reason = 'missing_previous_month' if earlier else 'first_period'
            elif len(indices) != 1:
                reason = 'invalid_previous_month'
            else:
                previous = rows[indices[0]]
                p = finite_number(previous.get('value'))
                if parsed[indices[0]] != start or previous.get('frequency') != 'monthly' or previous.get('value_kind') != 'adjusted_price' or previous.get('currency') != currency or p is None or p <= 0:
                    reason = 'invalid_previous_month'
                else:
                    result = number / p - 1
                    if not math.isfinite(result): reason = 'invalid_value'
                    else:
                        out.update(local_return=result, start_price=p)
                        out.update({'start_'+x: previous.get(x, '') for x in SOURCE_FIELDS})
        out.update(status='blocked' if reason else 'valid', reason=reason or 'ok')
        output.append(out)
    return pd.DataFrame(output, columns=LOCAL_COLUMNS)
