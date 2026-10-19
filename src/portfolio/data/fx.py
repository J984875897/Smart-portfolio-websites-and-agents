"""Strict exact-date FX validation and auditable HKD reconciliation."""
from dataclasses import dataclass
import hashlib
import math
import pandas as pd
from .returns import SOURCE_FIELDS, LOCAL_COLUMNS, strict_date, finite_number, build_local_returns
from .quality import CURRENCIES

FX_COLUMNS = ['date', 'currency', 'hkd_per_unit', 'source_name', *SOURCE_FIELDS, 'sources']
ISSUE_COLUMNS = ['date', 'currency', 'hkd_per_unit', 'source_name', *SOURCE_FIELDS, 'code', 'severity', 'message']
RECONCILIATION_COLUMNS = [*LOCAL_COLUMNS, 'fx_start', 'fx_end', 'fx_return', 'cross_term', 'hkd_return', *['fx_'+side+'_'+field for side in ['start', 'end'] for field in ['source_name', *SOURCE_FIELDS]], 'fx_start_sources', 'fx_end_sources']

@dataclass
class FxValidation:
    values: pd.DataFrame
    issues: pd.DataFrame

@dataclass
class HkdResult:
    local_returns: pd.DataFrame
    reconciliation: pd.DataFrame
    fx_issues: pd.DataFrame


def validate_fx(frame):
    """Reject every record of a conflicting/invalid key; preserve all duplicate evidence."""
    if not frame.columns.is_unique:
        raise ValueError('FX columns must be unique')
    required = ['date', 'currency', 'hkd_per_unit', 'source_name']
    payload = frame.attrs.get('raw_bytes', frame.to_csv(index=False).encode())
    digest = hashlib.sha256(payload).hexdigest()
    groups = {}
    issues = []
    def issue(row, code):
        issues.append({**{x: row.get(x, '') for x in ISSUE_COLUMNS}, 'code': code, 'severity': 'blocked', 'message': code})
    missing = [x for x in required if x not in frame.columns]
    if missing:
        issue({}, 'missing_columns:' + ','.join(missing))
        return FxValidation(pd.DataFrame(columns=FX_COLUMNS), pd.DataFrame(issues, columns=ISSUE_COLUMNS))
    source_rows = frame.attrs.get('source_rows', list(range(2, len(frame)+2)))
    file_backed = 'raw_bytes' in frame.attrs
    for i, original in enumerate(frame.to_dict('records')):
        row = dict(original)
        for field, fallback in [('source_file', frame.attrs.get('source_file', 'dataframe.csv')), ('source_sheet', frame.attrs.get('source_sheet', '')), ('source_row', source_rows[i]), ('source_hash', digest)]:
            if file_backed:
                row[field] = fallback
            else:
                row.setdefault(field, fallback)
        number = finite_number(row.get('hkd_per_unit'))
        errors = []
        if strict_date(row.get('date')) is None: errors.append('invalid_date')
        if row.get('currency') not in CURRENCIES: errors.append('invalid_currency')
        if number is None or number <= 0: errors.append('invalid_quote')
        source = row.get('source_name')
        if not isinstance(source, str) or not source.strip(): errors.append('missing_source_name')
        row['_number'] = number
        row['_errors'] = errors
        # String keys also retain malformed dates without making them valid.
        groups.setdefault((str(row.get('date')), str(row.get('currency'))), []).append(row)
    values = []
    for group in groups.values():
        invalid = any(r['_errors'] for r in group)
        conflict = len({r['_number'] for r in group if r['_number'] is not None}) > 1
        if invalid or conflict:
            for row in group:
                issue(row, ';'.join(row['_errors']) or ('conflicting_quote' if conflict else 'invalid_key_record'))
            continue
        first = group[0]
        evidence = [{x: r.get(x, '') for x in ['source_name', *SOURCE_FIELDS]} for r in group]
        values.append({**{x: first.get(x, '') for x in FX_COLUMNS}, 'hkd_per_unit': first['_number'], 'sources': evidence})
    return FxValidation(pd.DataFrame(values, columns=FX_COLUMNS), pd.DataFrame(issues, columns=ISSUE_COLUMNS))


def reconcile_hkd(bundle, fx_frame, *, adjusted_price_assets=()):
    local = build_local_returns(bundle, adjusted_price_assets=adjusted_price_assets)
    validated = validate_fx(fx_frame)
    quotes = {(r['date'], r['currency']): r for r in validated.values.to_dict('records')}
    rows = []
    for original in local.to_dict('records'):
        row = {x: original.get(x, '') for x in RECONCILIATION_COLUMNS}
        row.update({x: float('nan') for x in ['fx_start', 'fx_end', 'fx_return', 'cross_term', 'hkd_return']})
        row.update(fx_start_sources=[], fx_end_sources=[])
        if original['status'] != 'valid':
            rows.append(row)
            continue
        if row['currency'] == 'HKD':
            row.update(fx_start=1., fx_end=1., fx_return=0., cross_term=0., hkd_return=row['local_return'])
        else:
            absent = []
            for side in ['start', 'end']:
                quote = quotes.get((row[side+'_date'], row['currency']))
                if quote is None:
                    absent.append(side)
                else:
                    row['fx_'+side] = quote['hkd_per_unit']
                    row['fx_'+side+'_sources'] = quote['sources']
                    row.update({'fx_'+side+'_'+x: quote[x] for x in ['source_name', *SOURCE_FIELDS]})
            if absent:
                row.update(status='blocked', reason='missing_fx_'+'_and_'.join(absent))
            else:
                fx_return = row['fx_end']/row['fx_start']-1
                cross = row['local_return']*fx_return
                result = (1+row['local_return'])*row['fx_end']/row['fx_start']-1
                if all(math.isfinite(x) for x in [fx_return, cross, result]):
                    row.update(fx_return=fx_return, cross_term=cross, hkd_return=result)
                else:
                    row.update(status='blocked', reason='nonfinite_hkd_result')
        rows.append(row)
    return HkdResult(local, pd.DataFrame(rows, columns=RECONCILIATION_COLUMNS), validated.issues)
