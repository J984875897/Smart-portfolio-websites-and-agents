"""Explicit product policy; names, currencies and returns never infer a type."""
from portfolio.data.quality import ASSET_CLASSES
from portfolio.data.returns import strict_date

EXCHANGE_MARKETS = {'NASDAQ':'US', 'NYSE':'US', 'NYSE_ARCA':'US', 'AMEX':'US',
                    'CBOE':'US', 'BATS':'US', 'HKEX':'HK', 'SEHK':'HK'}
EXCHANGE_IDENTITIES = {exchange: ('HKEX' if exchange == 'SEHK' else exchange)
                       for exchange in EXCHANGE_MARKETS}
TOOL_ORIGINS = {'stock':{'stock'}, 'ADR':{'stock'}, 'preferred_stock':{'stock'},
                'REIT':{'REIT'}, 'ETF':{'ETF'}, 'fund':{'fund','mutual_fund'},
                'mutual_fund':{'mutual_fund','fund'}, 'bond':{'bond'},
                'commodity':{'commodity'}, 'gold_trust':{'gold_trust'},
                'index':{'index'}, 'cash':{'cash'}, 'FX':set(), 'derivative':{'derivative'}}
DIRECT_EQUITY = {'stock','ADR','REIT','preferred_stock'}
NON_PRODUCTS = {'index','cash','FX'}
CLASS_LIMITS = {'stock':{'equity'}, 'ADR':{'equity'}, 'REIT':{'real_estate','equity'},
                'preferred_stock':{'equity','bond','fixed_income'}, 'bond':{'bond','fixed_income'},
                'commodity':{'commodity'}, 'gold_trust':{'commodity'}}


def classify(asset, structure, *, include_stocks):
    reasons = []
    market = EXCHANGE_MARKETS.get(asset['exchange'], '')
    if not market: reasons.append('unknown_exchange')
    if structure['binding_status'] != 'declared' or structure['review_status'] != 'declared':
        reasons.append('structure_' + ('missing' if structure['binding_status'] == 'missing' else 'pending'))
    if any(not isinstance(structure.get(k), str) or not structure[k].strip()
           for k in ['source_name','source_reference','source_as_of']):
        reasons.append('missing_structure_evidence')
    if strict_date(structure['source_as_of']) is None:
        reasons.append('invalid_structure_date')
    if structure['market'] != market: reasons.append('market_exchange_conflict')
    tool = structure['canonical_tool_type']
    if tool not in TOOL_ORIGINS: reasons.append('unknown_tool_type')
    elif asset['tool_type'] not in TOOL_ORIGINS[tool]: reasons.append('tool_classification_conflict')
    if tool in NON_PRODUCTS: reasons.append('non_investment_product')
    if tool == 'derivative': reasons.append('unsupported_tool_type')
    if structure['structure'] != 'ordinary': reasons.append('unsupported_structure')
    cls = asset['asset_class']
    if cls not in ASSET_CLASSES: reasons.append('unknown_asset_class')
    elif tool in CLASS_LIMITS and cls not in CLASS_LIMITS[tool]: reasons.append('asset_class_conflict')
    if not include_stocks and tool in DIRECT_EQUITY: reasons.append('direct_equity_excluded')
    return market, tool, reasons
