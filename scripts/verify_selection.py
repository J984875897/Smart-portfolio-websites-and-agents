"""Offline S07-A: member drafts, correlation limits, source and count gates."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import numpy as np
import pandas as pd
from portfolio.data.alignment import TIMING_FIELDS
from portfolio.data.contracts import DataBundle
from portfolio.universe.clustering import cluster_correlations
from portfolio.universe.inputs import prepare_candidate_input
from portfolio.universe.screening import screen_candidates
from portfolio.universe.screening_samples import sample_screening_inputs
from portfolio.universe.selection import select_members
from verify_candidate_inputs import file_hashes
from verify_estimation import staged_output

PARAMS=dict(end_month='2025-01',decision_at='2025-02-01T06:00:00+08:00')


def synthetic_candidate(case='groups'):
    bundle,fx,timing,structures=sample_screening_inputs()
    signals=np.random.default_rng(5052).normal(.005,.03,(61,40))
    for i,aid in enumerate(bundle.assets.asset_id):
        values=signals[:,i//3] if case == 'groups' else np.linspace(-.02,.04,61)
        if case == 'groups' and i == 99: values=-signals[:,0]
        if case != 'constant':
            bundle.observations.loc[bundle.observations.asset_id == aid,'value']=values
    bundle.assets.loc[50:,'asset_class']='bond'
    return prepare_candidate_input(bundle,fx,timing,structures,**PARAMS)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'outputs/acceptance/S07A')
    parser.add_argument('--real-bundle',type=Path)
    args=parser.parse_args()
    source=args.real_bundle or Path(json.loads((ROOT/'outputs/acceptance/S02/import_summary.json').read_text())['real_bundle_path'])
    source=source.resolve();out=args.output.resolve()
    if out == source or source in out.parents or out in source.parents:
        raise ValueError('output and source bundle must be separate directories')
    before=file_hashes(source)
    hand=pd.DataFrame([[1,.9,.7,-1,np.nan],[.9,1,.9,-.9,np.nan],
                       [.7,.9,1,-.7,np.nan],[-1,-.9,-.7,1,np.nan],
                       [np.nan]*5],index=['A','B','C','NEG','CONST'],columns=['A','B','C','NEG','CONST'])
    grouping=cluster_correlations(hand);m=grouping.memberships.set_index('asset_id')
    assert m.loc['A','cluster_id'] == m.loc['B','cluster_id']
    assert m.loc['A','cluster_id'] != m.loc['C','cluster_id']
    assert m.loc['NEG','cluster_id'] != m.loc['A','cluster_id']
    assert m.loc['CONST','correlation_status'] == 'unavailable'
    c=synthetic_candidate();selected=select_members(c,k=30)
    assert len(selected.selected_asset_ids) == len(set(selected.selected_asset_ids)) == 30
    assert selected.evidence['selected_known_cluster_count'] == 30
    repeated=select_members(c,k=30)
    assert repeated.fingerprint == selected.fingerprint
    manual=select_members(c,k=30,included_asset_ids=['SYNTH_SCREEN_001','SYNTH_SCREEN_002'],
                          member_excluded_asset_ids=['SYNTH_SCREEN_000'],category_minimums={'bond':20})
    assert manual.reasons.loc[manual.reasons.selected,'asset_class'].eq('bond').sum() >= 20
    assert 'SYNTH_SCREEN_000' not in manual.selected_asset_ids
    identical=select_members(synthetic_candidate('identical'),k=30)
    constant=select_members(synthetic_candidate('constant'),k=30)
    assert len(identical.high_correlation_pairs) == 435
    assert identical.evidence['selected_known_cluster_count'] == 1
    assert constant.evidence['selected_known_cluster_count'] == 0
    assert constant.evidence['selected_unknown_correlation_count'] == 30
    errors={}
    for name,params in [
        ('n99',dict(excluded_asset_ids=['SYNTH_SCREEN_099'])),
        ('manual_conflict',dict(included_asset_ids=['SYNTH_SCREEN_001'],member_excluded_asset_ids=['SYNTH_SCREEN_001'])),
        ('category_shortfall',dict(category_minimums={'commodity':1})),
        ('member_pool_too_small',dict(member_excluded_asset_ids=[f'SYNTH_SCREEN_{i:03d}' for i in range(71)])),
    ]:
        try: select_members(c,k=30,**params)
        except ValueError as exc: errors[name]=str(exc)
        else: raise AssertionError(name+' should be blocked')
    real=DataBundle.load(source)
    real_input=prepare_candidate_input(real,pd.DataFrame(columns=['date','currency','hkd_per_unit','source_name']),
                                       pd.DataFrame(columns=TIMING_FIELDS),
                                       adjusted_price_assets=real.assets.asset_id.tolist(),**PARAMS)
    real_screened=screen_candidates(real_input,k=30)
    assert real_screened.cardinality.n == 0
    try: select_members(real_input,k=30)
    except ValueError as exc: errors['real_input']=str(exc)
    else: raise AssertionError('real daily input must remain blocked')
    assert file_hashes(source) == before
    summary=dict(stage='S07-A',synthetic_n=100,selected_count=30,
                 synthetic_selected_known_cluster_count=selected.evidence['selected_known_cluster_count'],
                 n99_blocked=True,real_n=0,no_network=True,source_files_unchanged=True,
                 portfolio_constructed=False,historical_universe_certified=False,
                 ui_implemented=False,weights_generated=False,risk_comparison_implemented=False,
                 synthetic_selection_fingerprint=selected.fingerprint,real_bundle_path=str(source),
                 source_file_hashes=before,blocked_cases=errors)
    with staged_output(out,source,before) as stage:
        for name,frame in [
            ('selection_reasons.csv',selected.reasons),('candidate_alternatives.csv',selected.alternatives),
            ('cluster_memberships.csv',selected.clusters.memberships),('cluster_merges.csv',selected.clusters.merges),
            ('high_correlation_pairs.csv',selected.high_correlation_pairs),
            ('manual_selection_reasons.csv',manual.reasons),('manual_high_correlation_pairs.csv',manual.high_correlation_pairs),
            ('identical_high_correlation_pairs.csv',identical.high_correlation_pairs),
            ('constant_selection_reasons.csv',constant.reasons),('hand_cluster_memberships.csv',grouping.memberships),
            ('hand_cluster_merges.csv',grouping.merges),('real_blocked_audit.csv',real_screened.audit),
        ]: frame.to_csv(stage/name,index=False)
        selected.selected_correlation.to_csv(stage/'selected_correlation.csv')
        hand.to_csv(stage/'hand_correlation.csv')
        def write_json(name,value):
            (stage/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        write_json('selection_evidence.json',selected.evidence)
        write_json('manual_selection_evidence.json',manual.evidence)
        write_json('identical_selection_evidence.json',identical.evidence)
        write_json('constant_selection_evidence.json',constant.evidence)
        write_json('summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False))


if __name__ == '__main__': main()
