"""Offline S06-A acceptance: arithmetic checks, numerical diagnostics, S05 gates."""
import argparse
from contextlib import contextmanager
from tempfile import TemporaryDirectory
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import numpy as np
import pandas as pd
from portfolio.data.contracts import DataBundle
from portfolio.data.alignment import TIMING_FIELDS
from portfolio.models.moments import estimate_moments
from portfolio.models.estimation_input import estimate_candidates
from portfolio.universe.inputs import prepare_candidate_input
from portfolio.universe.screening import screen_candidates
from portfolio.universe.screening_samples import sample_screening_inputs
from verify_candidate_inputs import file_hashes

PARAMS=dict(end_month='2025-01',decision_at='2025-02-01T06:00:00+08:00')


@contextmanager
def staged_output(destination, source, source_hashes):
    """Never follow existing file aliases; replace complete files and verify source afterward."""
    destination.mkdir(parents=True,exist_ok=True)
    with TemporaryDirectory(prefix='s06a-',dir=destination.parent) as temp:
        stage=Path(temp)
        yield stage
        files=list(stage.iterdir())
        for item in files:
            target=destination/item.name
            if target.is_symlink() or (target.exists() and
                (not target.is_file() or target.stat().st_nlink > 1)):
                raise ValueError('output file alias or non-regular target: '+str(target))
        if file_hashes(source) != source_hashes:
            raise ValueError('source files changed before publication')
        # replace() does not follow a target symlink or modify its underlying inode.
        for item in sorted(files,key=lambda p:p.name == 'summary.json'):
            item.replace(destination/item.name)
        if file_hashes(source) != source_hashes:
            raise ValueError('source files changed after publication')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'outputs/acceptance/S06A')
    parser.add_argument('--real-bundle',type=Path)
    args=parser.parse_args()
    source=args.real_bundle or Path(json.loads((ROOT/'outputs/acceptance/S02/import_summary.json').read_text())['real_bundle_path'])
    source=source.resolve();out=args.output.resolve()
    if out == source or source in out.parents or out in source.parents:
        raise ValueError('output and source bundle must be separate directories')
    before=file_hashes(source)
    x=pd.DataFrame({'A':[.01,.03,.02],'B':[.03,.05,.04],'C':[0,.01,.02]},
                    index=['2024-01-31','2024-02-29','2024-03-31'])
    classes=pd.Series({'A':'equity','B':'equity','C':'bond'})
    hand=estimate_moments(x,classes,train_start='2024-01',train_end='2024-03')
    expected=np.array([[.0001,.0001,.00005],[.0001,.0001,.00005],[.00005,.00005,.0001]])
    np.testing.assert_allclose(hand.sample_cov_month,expected,rtol=0,atol=1e-18)
    np.testing.assert_allclose(hand.summary.estimated_mean_ann,[.30,.42,.12],rtol=0,atol=1e-14)
    z=x.to_numpy()-x.to_numpy().mean(axis=0);t,p=z.shape
    empirical=z.T@z/t;target=np.trace(empirical)/p*np.eye(p)
    delta=np.square(empirical-target).sum()/p
    beta=(np.square(z).T@np.square(z)/t-np.square(empirical)).sum()/(p*t)
    alpha=min(beta,delta)/delta
    np.testing.assert_allclose(hand.shrunk_cov_month,(1-alpha)*empirical+alpha*target,atol=1e-18)
    assert abs(hand.diagnostics['shrinkage_coefficient']-alpha) < 1e-12
    high=pd.DataFrame(np.random.default_rng(5052).normal(.005,.04,(60,100)),
                      columns=[f'SYNTH_EST_{i:03d}' for i in range(100)],
                      index=pd.period_range('2020-02','2025-01',freq='M').to_timestamp('M').strftime('%Y-%m-%d'))
    high_result=estimate_moments(high,pd.Series('equity',index=high.columns),
                                train_start='2020-02',train_end='2025-01')
    assert high_result.diagnostics['sample_covariance']['rank'] <= 59
    assert high_result.diagnostics['usable_for_optimization']
    constant=prepare_candidate_input(*sample_screening_inputs(),**PARAMS)
    constant_result=estimate_candidates(constant,k=30)
    assert not constant_result.diagnostics['usable_for_optimization']
    try:
        estimate_candidates(constant,k=30,excluded_asset_ids=['SYNTH_SCREEN_099'])
    except ValueError as exc:
        assert '候选产品池' in str(exc);n99_blocked=True
    else:
        raise AssertionError('N99 must be blocked')
    bundle,fx,timing,structures=sample_screening_inputs()
    bundle.observations['value']=np.random.default_rng(5052).normal(.005,.04,len(bundle.observations))
    bundle.assets.loc[bundle.assets.index[50:],'asset_class']='bond'
    qualified=estimate_candidates(prepare_candidate_input(bundle,fx,timing,structures,**PARAMS),k=30)
    assert qualified.diagnostics['usable_for_optimization']
    real=DataBundle.load(source)
    real_input=prepare_candidate_input(real,pd.DataFrame(columns=['date','currency','hkd_per_unit','source_name']),
                                       pd.DataFrame(columns=TIMING_FIELDS),
                                       adjusted_price_assets=real.assets.asset_id.tolist(),**PARAMS)
    screened=screen_candidates(real_input,k=30)
    assert screened.cardinality.n == 0
    assert screened.audit.reason.str.contains('monthly_preparation_required').all()
    try:
        estimate_candidates(real_input,k=30)
    except ValueError as exc:
        real_error=str(exc)
        assert '候选产品池' in real_error
    else:
        raise AssertionError('real daily input must remain blocked')
    assert file_hashes(source) == before
    with staged_output(out,source,before) as out:
        table=hand.summary.copy();table['expected_estimated_mean_ann']=[.30,.42,.12]
        table.rename_axis('asset_id').to_csv(out/'hand_calculation.csv')
        hand.sample_cov_month.to_csv(out/'sample_covariance_month.csv')
        pd.DataFrame(expected,index=x.columns,columns=x.columns).to_csv(out/'expected_sample_covariance_month.csv')
        hand.shrunk_cov_month.to_csv(out/'shrunk_covariance_month.csv')
        hand.sample_cov_ann.to_csv(out/'sample_covariance_ann.csv')
        hand.shrunk_cov_ann.to_csv(out/'shrunk_covariance_ann.csv')
        high.to_csv(out/'high_dimensional_training_returns.csv')
        high_result.sample_cov_month.to_csv(out/'high_dimensional_sample_covariance_month.csv')
        high_result.shrunk_cov_month.to_csv(out/'high_dimensional_shrunk_covariance_month.csv')
        qualified.summary.rename_axis('asset_id').to_csv(out/'qualified_nonconstant_summary.csv')
        screened.audit.to_csv(out/'real_blocked_audit.csv',index=False)
        diagnostics=dict(hand=hand.diagnostics,high_dimensional=high_result.diagnostics,
                         qualified_constant=constant_result.diagnostics,qualified_nonconstant=qualified.diagnostics)
        def write_json(name,value):
            (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        write_json('estimation_diagnostics.json',diagnostics)
        write_json('qualified_nonconstant_evidence.json',qualified.evidence)
        summary=dict(stage='S06-A',no_network=True,source_files_unchanged=True,
                     synthetic_n100_degenerate=True,nonconstant_n100_usable=True,n99_blocked=n99_blocked,
                     real_n=0,real_block_reason=real_error,real_bundle_path=str(source),
                     historical_universe_certified=False,portfolio_constructed=False,
                     correlation_implemented=False,ui_implemented=False,
                     source_file_hashes=before)
        write_json('summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
