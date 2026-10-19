"""Offline synthetic acceptance with expectations independent of alignment output."""
import argparse
import json
from pathlib import Path
from portfolio.data.alignment import align_monthly
from portfolio.data.alignment_samples import sample_alignment_inputs


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='outputs/acceptance/S03B/synthetic');args=parser.parse_args()
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    rec,timing,assets=sample_alignment_inputs()
    rec.to_csv(output/'input_reconciliation.csv',index=False);timing.to_csv(output/'input_timing.csv',index=False)
    summary={'synthetic_only':True,'timing':'Source-declared, not independently certified','scenarios':{}}
    expected={'early':{'HKD_COMPLETE':60,'USD_COMPLETE':59,'MISSING_MIDDLE':59,'SHORT_HISTORY':59,'MISSING_END_FX':59},'late':{'HKD_COMPLETE':60,'USD_COMPLETE':60,'MISSING_MIDDLE':59,'SHORT_HISTORY':59,'MISSING_END_FX':59}}
    for name,decision in [('early','2025-01-31T17:00:00+08:00'),('late','2025-02-01T06:00:00+08:00')]:
        result=align_monthly(rec,timing,asset_ids=assets,end_month='2025-01',decision_at=decision)
        assert result.report.set_index('asset_id').valid_months.to_dict()==expected[name]
        eligible=['HKD_COMPLETE'] if name=='early' else ['HKD_COMPLETE','USD_COMPLETE']
        assert list(result.matrix)==eligible
        assert result.matrix.shape==(60,len(eligible))
        assert result.matrix.index[0]=='2020-02-29' and result.matrix.index[-1]=='2025-01-31'
        assert (abs(result.matrix-.01)<1e-12).all().all()
        assert 'missing_fx_end' in result.report.set_index('asset_id').loc['MISSING_END_FX','reason']
        result.report.to_csv(output/f'{name}_report.csv',index=False);result.coverage.to_csv(output/f'{name}_coverage.csv',index=False);result.matrix.to_csv(output/f'{name}_matrix.csv')
        summary['scenarios'][name]={'decision_at':result.decision_at,'eligible':eligible,'valid_months':expected[name],'window_start':result.window_start,'window_end':result.window_end,'assertions':'passed'}
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('Synthetic alignment acceptance passed: early 1, late 2 eligible; fixed 60 months.')

if __name__=='__main__': main()
