"""Offline S06-B acceptance: hand risk, raw Pearson, and qualified-weight previews."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import numpy as np
import pandas as pd
from portfolio.data.contracts import DataBundle
from portfolio.data.alignment import TIMING_FIELDS
from portfolio.evaluation.correlation import pearson_correlation
from portfolio.evaluation.diversification import portfolio_risk
from portfolio.evaluation.risk_preview import preview_candidate_risk
from portfolio.universe.inputs import prepare_candidate_input
from portfolio.universe.screening_samples import sample_screening_inputs
from portfolio.universe.screening import screen_candidates
from verify_candidate_inputs import file_hashes
from verify_estimation import staged_output

PARAMS=dict(end_month='2025-01',decision_at='2025-02-01T06:00:00+08:00')


def hand_cases():
    ids=['A','B'];mu=pd.Series([.06,.10],index=ids)
    def case(values,weights):
        return portfolio_risk(mu,pd.DataFrame(values,index=ids,columns=ids),
                              pd.Series(weights,index=ids),covariance_method='specified')
    cases={
        'two_asset_diagonal':case([[.04,0],[0,.09]],[.5,.5]),
        'two_asset_identical_direction':case([[.04,.06],[.06,.09]],[.5,.5]),
        'negative_contribution':case([[.04,-.03],[-.03,.09]],[.8,.2]),
        'zero_volatility':case([[0,0],[0,0]],[.5,.5]),
        'perfect_offset':case([[1,-1],[-1,1]],[.5,.5]),
    }
    ids20=[f'SYNTH_IDENTICAL_{i:02}' for i in range(20)]
    cases['twenty_identical']=portfolio_risk(pd.Series(.05,index=ids20),
                                            pd.DataFrame(.04,index=ids20,columns=ids20),
                                            pd.Series(.05,index=ids20),covariance_method='specified')
    expected={'two_asset_diagonal':(.08,.0325), 'two_asset_identical_direction':(.08,.0625),
              'negative_contribution':(.068,.0196), 'zero_volatility':(.08,0),
              'perfect_offset':(.08,0),'twenty_identical':(.05,.04)}
    rows=[];contributions=[]
    for name,result in cases.items():
        mean,var=expected[name]
        np.testing.assert_allclose([result.metrics['mean_ann'],result.metrics['variance_ann']],
                                   [mean,var],rtol=1e-12,atol=1e-15)
        if var > 0:
            np.testing.assert_allclose(result.contributions.volatility_contribution_ann.sum(),np.sqrt(var),rtol=1e-12)
        else:
            assert result.metrics['diversification_ratio'] is None
        rows.append(dict(scenario=name,**result.metrics,expected_mean_ann=mean,expected_variance_ann=var))
        contributions.append(result.contributions.rename_axis('asset_id').reset_index().assign(scenario=name))
    np.testing.assert_allclose(cases['twenty_identical'].metrics['effective_holdings'],20)
    np.testing.assert_allclose(cases['twenty_identical'].metrics['diversification_ratio'],1)
    assert cases['negative_contribution'].contributions.loc['B','risk_share'] < 0
    return cases,pd.DataFrame(rows),pd.concat(contributions,ignore_index=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'outputs/acceptance/S06B')
    parser.add_argument('--real-bundle',type=Path)
    args=parser.parse_args()
    source=args.real_bundle or Path(json.loads((ROOT/'outputs/acceptance/S02/import_summary.json').read_text())['real_bundle_path'])
    source=source.resolve();out=args.output.resolve()
    if out == source or source in out.parents or out in source.parents:
        raise ValueError('output and source bundle must be separate directories')
    before=file_hashes(source)
    cases,hand,contributions=hand_cases()
    x=pd.DataFrame({'A':[.01,.03,.02],'B':[.03,.05,.04],'C':[0,.01,.02],
                    'NEG':[-.01,-.03,-.02],'CONST':[.01,.01,.01]},
                   index=['2024-01-31','2024-02-29','2024-03-31'])
    corr=pearson_correlation(x,train_start='2024-01',train_end='2024-03')
    np.testing.assert_allclose(corr.matrix.loc[['A','B','C'],['A','B','C']],[[1,1,.5],[1,1,.5],[.5,.5,1]])
    assert corr.matrix.loc['A','NEG'] < -.999999999
    assert corr.matrix['CONST'].isna().all()
    constant=prepare_candidate_input(*sample_screening_inputs(),**PARAMS)
    weights=pd.Series(.01,index=constant.matrix.columns)
    zero=preview_candidate_risk(constant,weights,k=30)
    assert zero.sample_risk.metrics['diversification_ratio'] is None
    try:
        preview_candidate_risk(constant,weights,k=30,excluded_asset_ids=['SYNTH_SCREEN_099'])
    except ValueError as exc:
        assert '候选产品池' in str(exc)
    else: raise AssertionError('N99 must remain blocked')
    bundle,fx,timing,structures=sample_screening_inputs()
    bundle.observations['value']=np.random.default_rng(5052).normal(.005,.04,len(bundle.observations))
    bundle.observations.loc[bundle.observations.asset_id == 'SYNTH_SCREEN_000','value']=.01
    variable=prepare_candidate_input(bundle,fx,timing,structures,**PARAMS)
    preview=preview_candidate_risk(variable,weights,k=30)
    aid='SYNTH_SCREEN_000'
    assert preview.sample_risk.contributions.loc[aid,'asset_volatility_ann'] == 0
    assert preview.model_risk.contributions.loc[aid,'asset_volatility_ann'] > 0
    real=DataBundle.load(source)
    real_input=prepare_candidate_input(real,pd.DataFrame(columns=['date','currency','hkd_per_unit','source_name']),
                                       pd.DataFrame(columns=TIMING_FIELDS),
                                       adjusted_price_assets=real.assets.asset_id.tolist(),**PARAMS)
    screened=screen_candidates(real_input,k=30)
    assert screened.cardinality.n == 0
    try: preview_candidate_risk(real_input,pd.Series(dtype=float),k=30)
    except ValueError as exc:
        assert '候选产品池' in str(exc);real_error=str(exc)
    else: raise AssertionError('real daily input must remain blocked')
    with staged_output(out,source,before) as stage:
        def write(name,value):
            (stage/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        hand.to_csv(stage/'hand_calculation.csv',index=False)
        contributions.to_csv(stage/'risk_contributions.csv',index=False)
        corr.matrix.to_csv(stage/'correlation.csv')
        corr.asset_status.rename_axis('asset_id').to_csv(stage/'correlation_status.csv')
        write('correlation.json',dict(asset_ids=list(corr.matrix),
              values=[[None if pd.isna(v) else float(v) for v in row] for row in corr.matrix.to_numpy()],
              diagnostics=corr.diagnostics))
        preview.correlation.matrix.to_csv(stage/'qualified_correlation.csv')
        for label,result in [('sample',preview.sample_risk),('model',preview.model_risk)]:
            result.contributions.rename_axis('asset_id').to_csv(stage/f'qualified_{label}_contributions.csv')
        pd.DataFrame([dict(method=label,**result.metrics) for label,result in
                      [('sample',preview.sample_risk),('model',preview.model_risk)]]).to_csv(stage/'qualified_risk_comparison.csv',index=False)
        screened.audit.to_csv(stage/'real_blocked_audit.csv',index=False)
        write('qualified_evidence.json',preview.evidence)
        write('estimation_diagnostics.json',dict(hand={k:v.diagnostics for k,v in cases.items()},
              correlation=corr.diagnostics,constant_preview=dict(sample=zero.sample_risk.diagnostics,model=zero.model_risk.diagnostics),
              qualified_preview=dict(estimate=preview.estimate.diagnostics,sample=preview.sample_risk.diagnostics,
                                     model=preview.model_risk.diagnostics)))
        summary=dict(stage='S06-B',no_network=True,source_files_unchanged=True,source_file_hashes=before,
                     n99_blocked=True,real_n=0,real_block_reason=real_error,
                     historical_universe_certified=False,portfolio_constructed=False,ui_implemented=False,
                     nonconstant_preview_is_synthetic=True,positive_weight_count=100,target_k=30,
                     member_selection_implemented=False)
        write('summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
