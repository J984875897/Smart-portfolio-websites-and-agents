"""Independent synthetic acceptance; no downloads or data version writes."""
from pathlib import Path
import sys
from decimal import Decimal
import json
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from portfolio.data.risk_free import risk_free_monthly
from portfolio.data.risk_free_samples import sample_risk_free_quotes, CASES


def main():
    output=ROOT/'outputs/acceptance/S03C/synthetic'
    for case in CASES:
        quotes=sample_risk_free_quotes(case); original=quotes.copy(deep=True)
        result=risk_free_monthly(quotes,end_month='2024-03',decision_at='2024-03-31T16:00:00+08:00',months=3)
        pd.testing.assert_frame_equal(quotes,original)
        if case=='完整报价':
            expected=[Decimal('3.65')/Decimal('100')*days/Decimal('365') for days in [Decimal('31'),Decimal('29'),Decimal('31')]]
            assert result.available
            assert all(abs(Decimal(str(actual))-want)<Decimal('1e-15') for actual,want in zip(result.series,expected))
            assert result.report.days.tolist()==[31,29,31]
        else:
            assert not result.available and result.report.status.tolist()==['valid','blocked','valid']
            assert pd.isna(result.series.iloc[1]) and pd.isna(result.report.iloc[1].rf_hkd)
        folder=output/case; folder.mkdir(parents=True,exist_ok=True)
        quotes.to_csv(folder/'inputs.csv',index=False)
        result.report.to_csv(folder/'report.csv',index=False)
        result.series.to_csv(folder/'rf_hkd.csv')
        (folder/'summary.json').write_text(json.dumps(dict(synthetic=True,case=case,available=result.available,valid_months=int((result.report.status=='valid').sum()),currency=result.currency,frequency=result.frequency,proxy_method=result.proxy_method,window_start=result.window_start,window_end=result.window_end,decision_at=result.decision_at),ensure_ascii=False,indent=2)+'\n')
    immature=risk_free_monthly(sample_risk_free_quotes(),end_month='2024-03',decision_at='2024-03-31T15:59:59+08:00',months=3)
    assert pd.isna(immature.series.iloc[2]) and pd.isna(immature.report.iloc[2].rf_hkd)
    assert 'period_not_complete_at_decision' in immature.report.iloc[2].reason
    print('PASS: five SYNTH cases, independent Decimal calculation, blocked NaNs, immutable inputs, immature March.')


if __name__=='__main__': main()
