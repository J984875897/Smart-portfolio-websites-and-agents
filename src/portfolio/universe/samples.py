"""Synthetic monthly inputs; never a real candidate list or investment result."""
import pandas as pd
from portfolio.data.contracts import DataBundle, TABLE_COLUMNS
from portfolio.data.alignment_samples import sample_alignment_inputs


def sample_candidate_inputs():
    rec, timing, aids = sample_alignment_inputs()
    # Reuse source observations, not the previously computed HKD returns/status.
    observations = rec[TABLE_COLUMNS['observations']].copy()
    currencies = dict(zip(rec.asset_id, rec.currency))
    assets = pd.DataFrame([
        dict(asset_id=a, ticker=a, name=a, tool_type='ETF', asset_class='equity',
             exchange='NYSE_ARCA' if currencies[a] != 'HKD' else 'HKEX',
             currency=currencies[a], share_class='', frequency='monthly') for a in aids
    ])
    fx = pd.DataFrame([
        dict(date=p.end_time.date().isoformat(), currency=c, hkd_per_unit=v, source_name='SYNTH FX')
        for p in pd.period_range('2019-12', '2025-01', freq='M')
        for c, v in [('USD', 7.8), ('EUR', 8.2)]
        if not (c == 'EUR' and str(p) == '2025-01')
    ])
    structures = pd.DataFrame([
        dict(asset_id=a, market='US' if currencies[a] != 'HKD' else 'HK',
             canonical_tool_type='ETF', structure='ordinary', review_status='declared',
             source_name='SYNTH classification', source_reference='SYNTH example', source_as_of='2025-01-01')
        for a in aids
    ])
    return DataBundle(assets=assets, observations=observations), fx, timing, structures
