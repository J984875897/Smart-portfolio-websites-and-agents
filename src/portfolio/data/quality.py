"""S02 diagnostic enums and row quality rules."""
from datetime import datetime
import math
import re

TOOL_TYPES = {'stock','ETF','fund','bond','index','cash','commodity','REIT','derivative','gold_trust','mutual_fund'}
ASSET_CLASSES = {'equity','bond','fixed_income','cash','commodity','real_estate','mixed','alternative'}
FREQUENCIES = {'daily','weekly','monthly','quarterly','annual'}
CURRENCIES = {'USD','HKD','CNY','CNH','EUR','GBP','JPY','AUD','CAD','CHF','SGD','NZD','KRW','TWD','INR'}

def validate_row(row, config):
    findings=[]
    def issue(code,message,severity='blocked'): findings.append((code,severity,message))
    for field,allowed in [('tool_type',TOOL_TYPES),('asset_class',ASSET_CLASSES),('currency',CURRENCIES),('frequency',FREQUENCIES)]:
        if not row[field]: issue('missing_'+field,f'{field} is required')
        elif row[field] not in allowed: issue('invalid_'+field,f'Unsupported {field}: {row[field]}')
    if not row['exchange']: issue('missing_exchange','Explicit exchange or market is required')
    try:
        original=row['date']; parsed=datetime.strptime(original,config.date_format)
        if parsed.strftime(config.date_format)!=original: raise ValueError()
        row['date']=parsed.strftime('%Y-%m-%d')
    except (ValueError,TypeError): issue('invalid_date','Date must match the explicit date format')
    try:
        if row['value']=='':
            row['value']=float('nan'); issue('missing_value','Missing value is retained as NaN')
        else:
            row['value']=float(row['value'])
            if not math.isfinite(row['value']): issue('invalid_value','Value must be finite')
            elif config.value_kind in {'price','adjusted_price'}:
                if row['value']<=0: issue('invalid_value','Price must be positive')
            else:
                if config.return_unit=='percent': row['value']/=100
                if row['value'] < -1: issue('invalid_value','Return below -100%')
                elif abs(row['value']) >= .5: issue('extreme_return','S02 diagnostic: absolute return >=50%; acknowledgement required','review')
    except (ValueError,TypeError):
        row['value']=float('nan'); issue('malformed_value','Numeric parsing failed')
    return findings
