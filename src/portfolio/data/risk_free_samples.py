"""Synthetic declared quotes; never a historical HIBOR data source."""
import pandas as pd

CASES=('完整报价','缺中间报价','月中报价','版本晚可得','USD报价')


def sample_risk_free_quotes(case='完整报价'):
    if case not in CASES:
        raise ValueError('unknown synthetic case')
    rows=[]
    for date,quoted in zip(['2024-01-31','2024-02-29','2024-03-31'],['2023-12-29','2024-01-31','2024-02-29']):
        rows.append(dict(date=date,quote_at=quoted+'T11:15:00+08:00',available_at=quoted+'T12:15:00+08:00',quote_percent=3.65,currency='HKD',benchmark='HKAB_HIBOR',tenor='1M',day_count='ACT/365F',compounding='simple',source_name='SYNTH: artificial HIBOR quote'))
    if case=='缺中间报价': rows.pop(1)
    if case=='月中报价': rows[1]['quote_at']='2024-02-01T11:15:00+08:00'
    if case=='版本晚可得': rows[1]['available_at']='2024-02-01T12:15:00+08:00'
    if case=='USD报价': rows[1]['currency']='USD'
    return pd.DataFrame(rows)
