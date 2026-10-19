"""Selections are reproducible drafts, with qualification and time evidence intact."""
from copy import deepcopy
import json
import numpy as np
import pandas as pd
import pytest
from portfolio.universe.inputs import prepare_candidate_input
from portfolio.universe.screening_samples import sample_screening_inputs


@pytest.fixture(scope='module')
def candidate():
    bundle,fx,timing,structures=sample_screening_inputs()
    rng=np.random.default_rng(5052)
    signals=rng.normal(.005,.03,(61,40))
    for i,aid in enumerate(bundle.assets.asset_id):
        # Groups of three exact copies, with negative copies kept distinct.
        values=signals[:,i//3]
        if i == 99: values=-signals[:,0]
        bundle.observations.loc[bundle.observations.asset_id == aid,'value']=values
    bundle.assets.loc[50:,'asset_class']='bond'
    return prepare_candidate_input(bundle,fx,timing,structures,end_month='2025-01',
                                   decision_at='2025-02-01T06:00:00+08:00')


def ranking(records):
    return pd.DataFrame([dict(asset_id=aid,metric=metric,value=value,
                             source_reference='SYNTH declared ranking',available_at=available)
                         for aid,metric,value,available in records])


def test_k30_known_groups_covered_before_duplicates_and_draft_evidence(candidate):
    from portfolio.universe.selection import select_members
    r=select_members(candidate,k=30)
    assert len(r.selected_asset_ids) == len(set(r.selected_asset_ids)) == 30
    m=r.clusters.memberships.set_index('asset_id')
    assert m.loc[list(r.selected_asset_ids),'cluster_id'].nunique() == 30
    assert r.evidence['portfolio_constructed'] is False
    assert r.evidence['selection_status'] == 'draft'
    assert r.evidence['historical_universe_certified'] is False
    assert r.evidence['cardinality']['n'] == 100
    assert r.evidence['weights_generated'] is False
    assert r.reasons.selected.sum() == 30
    assert len(r.alternatives) == 70
    assert r.selected_correlation.shape == (30,30)
    assert set(r.selected_correlation) == set(r.selected_asset_ids)
    json.dumps(r.evidence,allow_nan=False)


def test_manual_items_and_category_minimums_are_binding(candidate):
    from portfolio.universe.selection import select_members
    locked=['SYNTH_SCREEN_001','SYNTH_SCREEN_002']
    r=select_members(candidate,k=30,included_asset_ids=locked,
                     member_excluded_asset_ids=['SYNTH_SCREEN_000'],category_minimums={'bond':20})
    assert set(locked) <= set(r.selected_asset_ids)
    assert 'SYNTH_SCREEN_000' not in r.selected_asset_ids
    selected=r.reasons.loc[r.reasons.selected]
    assert selected.asset_class.eq('bond').sum() >= 20
    assert selected.set_index('asset_id').loc[locked,'selection_reason'].eq('manual_inclusion').all()
    assert r.evidence['cardinality']['n'] == 100
    assert not r.high_correlation_pairs.empty
    assert 'selected_high_correlation_pairs' in r.evidence['warnings']


def test_reordered_inputs_and_repeated_calls_are_identical_and_do_not_mutate(candidate):
    from portfolio.universe.selection import select_members
    c=deepcopy(candidate);before=deepcopy(c)
    data=ranking([('SYNTH_SCREEN_002','annual_fee_rate',.001,'2025-01-01T00:00:00Z'),
                  ('SYNTH_SCREEN_001','annual_fee_rate',.01,'2025-01-01T00:00:00Z')])
    a=select_members(c,k=30,ranking_data=data)
    c.matrix=c.matrix.iloc[:,::-1];c.assets=c.assets.iloc[::-1];c.structures=c.structures.iloc[::-1]
    c.data_eligibility=c.data_eligibility.iloc[::-1]
    b=select_members(c,k=30,ranking_data=data.iloc[::-1])
    assert a.selected_asset_ids == b.selected_asset_ids
    assert a.fingerprint == b.fingerprint
    pd.testing.assert_frame_equal(a.reasons,b.reasons)
    pd.testing.assert_frame_equal(candidate.matrix,before.matrix)
    pd.testing.assert_frame_equal(candidate.assets,before.assets)


def test_fees_liquidity_unknowns_and_future_records(candidate):
    from portfolio.universe.selection import select_members
    data=ranking([
        ('SYNTH_SCREEN_000','annual_fee_rate',.02,'2025-01-01T00:00:00Z'),
        ('SYNTH_SCREEN_001','annual_fee_rate',.001,'2025-01-01T00:00:00Z'),
        ('SYNTH_SCREEN_002','annual_fee_rate',0.,'2025-03-01T00:00:00Z'),
        ('SYNTH_SCREEN_003','avg_daily_turnover_hkd',100.,'2025-01-01T00:00:00Z'),
        ('SYNTH_SCREEN_004','avg_daily_turnover_hkd',200.,'2025-01-01T00:00:00Z')])
    r=select_members(candidate,k=30,ranking_data=data)
    assert 'SYNTH_SCREEN_001' in r.selected_asset_ids
    assert 'SYNTH_SCREEN_002' not in r.selected_asset_ids
    assert 'SYNTH_SCREEN_004' in r.selected_asset_ids
    assert 'SYNTH_SCREEN_003' not in r.selected_asset_ids
    assert r.evidence['ranking']['future_records_ignored'] == 1
    assert r.reasons.set_index('asset_id').loc['SYNTH_SCREEN_002','fee_status'] == 'unknown'
    past=select_members(candidate,k=30,ranking_data=data.iloc[[0,1,3,4]])
    assert past.selected_asset_ids == r.selected_asset_ids
    changed=data.copy();changed.loc[1,'value']=.03
    other=select_members(candidate,k=30,ranking_data=changed)
    assert other.fingerprint != r.fingerprint
    assert 'SYNTH_SCREEN_000' in other.selected_asset_ids


def test_latest_available_record_is_used_including_exact_decision_time(candidate):
    from portfolio.universe.selection import select_members
    data=ranking([('SYNTH_SCREEN_001','annual_fee_rate',.1,'2024-01-01T00:00:00Z'),
                  ('SYNTH_SCREEN_001','annual_fee_rate',.001,'2025-01-31T22:00:00Z')])
    r=select_members(candidate,k=30,ranking_data=data)
    assert r.reasons.set_index('asset_id').loc['SYNTH_SCREEN_001','annual_fee_rate'] == .001


@pytest.mark.parametrize('params,match',[
    ({'excluded_asset_ids':['SYNTH_SCREEN_099']},'候选产品池'),
    ({'included_asset_ids':['missing']},'纳入'),
    ({'included_asset_ids':['SYNTH_SCREEN_001'],'member_excluded_asset_ids':['SYNTH_SCREEN_001']},'冲突'),
    ({'included_asset_ids':[f'SYNTH_SCREEN_{i:03d}' for i in range(31)]},'超过'),
    ({'member_excluded_asset_ids':[f'SYNTH_SCREEN_{i:03d}' for i in range(71)]},'不足'),
    ({'category_minimums':{'commodity':1}},'类别'),
    ({'category_minimums':{'bond':31}},'超过'),
    ({'category_minimums':{'bond':True}},'整数'),
    ({'category_minimums':{'bond':1.5}},'整数'),
    ({'category_minimums':{'bond':-1}},'整数'),
    ({'category_minimums':{'unknown':0}},'类别'),
    ({'included_asset_ids':'SYNTH_SCREEN_001'},'集合'),
    ({'member_excluded_asset_ids':['missing']},'排除'),
])
def test_invalid_selection_does_not_return_partial_success(candidate,params,match):
    from portfolio.universe.selection import select_members
    with pytest.raises(ValueError,match=match): select_members(candidate,k=30,**params)


def test_manually_included_out_of_scope_item_cannot_bypass_s05(candidate):
    from portfolio.universe.selection import select_members
    with pytest.raises(ValueError,match='纳入'):
        select_members(candidate,k=20,excluded_asset_ids=['SYNTH_SCREEN_001'],
                       included_asset_ids=['SYNTH_SCREEN_001'])


@pytest.mark.parametrize('field,value',[
    ('metric','unknown'),('asset_id','missing'),('value',True),('value',float('inf')),
    ('value',-.1),('value','0.1'),('value',1.1),('source_reference',''),
    ('available_at','2024-01-01'),('available_at','invalid'),
])
def test_invalid_ranking_data_is_rejected(candidate,field,value):
    from portfolio.universe.selection import select_members
    data=ranking([('SYNTH_SCREEN_001','annual_fee_rate',.1,'2024-01-01T00:00:00Z')])
    data[field]=pd.Series([value],dtype=object)
    with pytest.raises(ValueError): select_members(candidate,k=30,ranking_data=data)


def test_duplicate_ranking_time_rejected_and_missing_values_not_zero(candidate):
    from portfolio.universe.selection import select_members
    data=ranking([('SYNTH_SCREEN_001','annual_fee_rate',.1,'2024-01-01T00:00:00Z')])
    with pytest.raises(ValueError): select_members(candidate,k=30,ranking_data=pd.concat([data,data]))
    data['value']=np.nan
    r=select_members(candidate,k=30,ranking_data=data)
    assert r.reasons.set_index('asset_id').loc['SYNTH_SCREEN_001','fee_status'] == 'unknown'


def test_all_identical_candidates_admit_limits_not_diversification():
    from portfolio.universe.selection import select_members
    bundle,fx,timing,structures=sample_screening_inputs()
    for aid in bundle.assets.asset_id:
        bundle.observations.loc[bundle.observations.asset_id == aid,'value']=np.linspace(-.02,.04,61)
    c=prepare_candidate_input(bundle,fx,timing,structures,end_month='2025-01',
                               decision_at='2025-02-01T06:00:00+08:00')
    r=select_members(c,k=30)
    assert r.evidence['selected_known_cluster_count'] == 1
    assert len(r.high_correlation_pairs) == 30*29//2
    assert 'selected_high_correlation_pairs' in r.evidence['warnings']
    assert r.evidence['diversification_certified'] is False


def test_all_constant_candidates_preserve_unknown_correlation():
    from portfolio.universe.selection import select_members
    c=prepare_candidate_input(*sample_screening_inputs(),end_month='2025-01',
                               decision_at='2025-02-01T06:00:00+08:00')
    r=select_members(c,k=30)
    assert r.evidence['selected_known_cluster_count'] == 0
    assert r.evidence['selected_unknown_correlation_count'] == 30
    assert r.selected_correlation.isna().all().all()
    assert r.reasons.max_selected_correlation.isna().all()
    assert 'selected_unknown_correlations' in r.evidence['warnings']


def test_constant_does_not_receive_new_group_coverage_priority(candidate):
    from portfolio.universe.selection import select_members
    c=deepcopy(candidate);c.matrix['SYNTH_SCREEN_000']=.01
    r=select_members(c,k=30)
    assert 'SYNTH_SCREEN_000' not in r.selected_asset_ids
    assert 'SYNTH_SCREEN_001' in r.selected_asset_ids


def test_once_only_scope_iterators_preserve_exclusions(candidate):
    from portfolio.universe.selection import select_members
    a=select_members(candidate,k=20,excluded_asset_ids=['SYNTH_SCREEN_000'],
                     markets=['US','HK'],asset_classes=['equity','bond'])
    b=select_members(candidate,k=20,excluded_asset_ids=iter(['SYNTH_SCREEN_000']),
                     markets=iter(['US','HK']),asset_classes=iter(['equity','bond']))
    assert a.selected_asset_ids == b.selected_asset_ids
    assert b.evidence['cardinality']['n'] == 99
    assert 'SYNTH_SCREEN_000' not in b.selected_asset_ids
    assert a.fingerprint == b.fingerprint


@pytest.mark.parametrize('format',['csv','xlsx'])
def test_standard_file_rankings_are_parsed_after_byte_verification(candidate,format):
    from io import BytesIO
    from portfolio.data.importer import read_file
    from portfolio.universe.selection import select_members
    data=ranking([('SYNTH_SCREEN_001','annual_fee_rate',.001,'2024-01-01T00:00:00Z')])
    if format == 'csv': payload=data.to_csv(index=False).encode()
    else:
        file=BytesIO();data.to_excel(file,index=False);payload=file.getvalue()
    loaded=read_file(payload,filename='SYNTH_ranking.'+format)
    r=select_members(candidate,k=30,ranking_data=loaded)
    assert 'SYNTH_SCREEN_001' in r.selected_asset_ids
    assert r.reasons.set_index('asset_id').loc['SYNTH_SCREEN_001','annual_fee_rate'] == .001
    assert r.evidence['ranking']['file_evidence']['raw_sha256']
    assert loaded.value.iloc[0] == '0.001'
    loaded['value']=.0001
    with pytest.raises(ValueError,match='unchanged'):
        select_members(candidate,k=30,ranking_data=loaded)
