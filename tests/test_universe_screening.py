from copy import deepcopy
import pandas as pd
import pytest
from portfolio.universe.inputs import prepare_candidate_input
from portfolio.universe.samples import sample_candidate_inputs


def candidate(specs=None, *, duplicate=False):
    specs = specs or [dict(asset_id='SYNTH_ETF')]
    bundle, fx, timing, structures = sample_candidate_inputs()
    frames = []
    for spec in specs:
        aid = spec['asset_id']
        asset = bundle.assets.loc[bundle.assets.asset_id == 'HKD_COMPLETE'].copy()
        asset['asset_id'] = aid; asset['ticker'] = spec.get('ticker', aid)
        for key in ['tool_type', 'asset_class', 'exchange', 'name']:
            if key in spec: asset[key] = spec[key]
        obs = bundle.observations.loc[bundle.observations.asset_id == 'HKD_COMPLETE'].copy()
        tm = timing.loc[timing.asset_id == 'HKD_COMPLETE'].copy()
        if spec.get('missing'): tm = tm.iloc[:-1]
        obs['asset_id'] = aid; tm['asset_id'] = aid
        st = structures.loc[structures.asset_id == 'HKD_COMPLETE'].copy()
        st['asset_id'] = aid
        st['canonical_tool_type'] = spec.get('canonical_tool_type', spec.get('tool_type', 'ETF'))
        for key in ['market', 'structure', 'review_status']:
            if key in spec: st[key] = spec[key]
        frames.append((asset, obs, tm, st))
    bundle.assets = pd.concat([x[0] for x in frames], ignore_index=True)
    if duplicate: bundle.assets = pd.concat([bundle.assets, bundle.assets.iloc[[0]]], ignore_index=True)
    bundle.observations = pd.concat([x[1] for x in frames], ignore_index=True)
    timing = pd.concat([x[2] for x in frames], ignore_index=True)
    structures = pd.concat([x[3] for x in frames], ignore_index=True)
    return prepare_candidate_input(bundle, fx, timing, structures, end_month='2025-01', decision_at='2025-02-01T06:00:00+08:00')


def screen(c, **kwargs):
    from portfolio.universe.screening import screen_candidates
    return screen_candidates(c, **(dict(k=30) | kwargs))


@pytest.mark.parametrize('tool,canonical,cls,direct', [
    ('stock','stock','equity',True),('stock','ADR','equity',True),
    ('REIT','REIT','real_estate',True),('stock','preferred_stock','equity',True),
    ('ETF','ETF','equity',False),('ETF','ETF','real_estate',False),
    ('fund','fund','equity',False),('mutual_fund','mutual_fund','mixed',False),
    ('ETF','ETF','fixed_income',False),('gold_trust','gold_trust','commodity',False),
    ('bond','bond','bond',False)])
def test_stock_toggle_retains_equity_funds(tool, canonical, cls, direct):
    c = candidate([dict(asset_id='SYNTH', tool_type=tool, canonical_tool_type=canonical, asset_class=cls)])
    r = screen(c)
    assert r.cardinality.n == (0 if direct else 1)
    if direct: assert 'direct_equity_excluded' in r.audit.iloc[0].reason
    assert screen(c, include_stocks=True).cardinality.n == 1


@pytest.mark.parametrize('overrides,reason', [
    (dict(structure='leveraged'),'unsupported_structure'),
    (dict(structure='inverse'),'unsupported_structure'),
    (dict(structure='complex'),'unsupported_structure'),
    (dict(structure='unknown'),'unsupported_structure'),
    (dict(review_status='pending'),'structure_pending'),
    (dict(tool_type='index'),'non_investment_product'),
    (dict(tool_type='cash',asset_class='cash'),'non_investment_product'),
    (dict(tool_type='derivative'),'unsupported_tool_type'),
    (dict(exchange='UNKNOWN'),'unknown_exchange'),
    (dict(market='US'),'market_exchange_conflict'),
    (dict(canonical_tool_type='stock'),'tool_classification_conflict'),
    (dict(asset_class='unknown'),'unknown_asset_class'),
    (dict(tool_type='stock',asset_class='commodity'),'asset_class_conflict'),
])
def test_exclusions_in_both_modes(overrides, reason):
    c = candidate([dict(asset_id='SYNTH') | overrides])
    for mode in [False, True]:
        r = screen(c, include_stocks=mode)
        assert r.cardinality.n == 0
        assert reason in r.audit.iloc[0].reason


def test_funnel_matrix_alignment_filters_and_no_mutation():
    c = candidate([dict(asset_id='SYNTH_Z'), dict(asset_id='SYNTH_A',exchange='NASDAQ',market='US'),
                   dict(asset_id='SYNTH_M',missing=True)], duplicate=True)
    before = deepcopy(c)
    r = screen(c)
    assert r.eligible_asset_ids == ('SYNTH_A','SYNTH_Z')
    assert list(r.matrix) == list(r.eligible_asset_ids)
    assert r.counts == dict(input_rows=4, identity_qualified=3, in_scope=3, data_qualified=2)
    assert r.audit.set_index('asset_id').loc['SYNTH_M','reason'].find('missing_timing') >= 0
    assert screen(c, markets=('US',)).eligible_asset_ids == ('SYNTH_A',)
    assert screen(c, markets=()).cardinality.n == 0
    assert screen(c, tool_types=()).cardinality.n == 0
    assert screen(c, asset_classes=('bond',)).cardinality.n == 0
    assert screen(c, excluded_asset_ids=('SYNTH_A',)).eligible_asset_ids == ('SYNTH_Z',)
    assert r.evidence['historical_universe_certified'] is False
    assert r.evidence['timing_basis'] == 'importer_declared'
    assert r.audit.listing_relationship_status.eq('not_verified').all()
    for field in ['assets','matrix','data_eligibility','structures']:
        pd.testing.assert_frame_equal(getattr(c,field), getattr(before,field))


def test_duplicate_listings_from_A_excluded():
    c = candidate([dict(asset_id='SYNTH_A',ticker='DUP'),dict(asset_id='SYNTH_B',ticker='DUP')])
    r = screen(c)
    assert r.cardinality.n == 0 and r.counts['identity_qualified'] == 0
    assert r.audit.reason.str.contains('duplicate_listing_identity').all()


def test_exchange_alias_cannot_inflate_N_across_boundary():
    specs = [dict(asset_id=f'SYNTH_{i:03d}') for i in range(65)]
    specs += [dict(asset_id='SYNTH_ALIAS_A',ticker='DUP',exchange='HKEX'),
              dict(asset_id='SYNTH_ALIAS_B',ticker='DUP',exchange='SEHK')]
    r = screen(candidate(specs), k=20)
    assert r.cardinality.n == 65 and r.cardinality.status == 'pool_too_small'
    assert r.counts['identity_qualified'] == 65
    assert r.audit.set_index('asset_id').loc[['SYNTH_ALIAS_A','SYNTH_ALIAS_B'],'reason'].str.contains('duplicate_listing_identity').all()


def relations():
    return pd.DataFrame([dict(asset_id=a,product_group='SYNTH_GROUP',representative_asset_id='SYNTH_B',
                              review_status='declared',source_name='SYNTH',source_reference='SYNTH identity',source_as_of='2025-01-01')
                         for a in ['SYNTH_A','SYNTH_B']])


def test_explicit_cross_listing_group_requires_representative():
    c = candidate([dict(asset_id='SYNTH_A'),dict(asset_id='SYNTH_B')])
    r = screen(c, listing_relations=relations())
    assert r.eligible_asset_ids == ('SYNTH_B',)
    assert r.counts['identity_qualified'] == 1
    assert 'duplicate_product_listing' in r.audit.set_index('asset_id').loc['SYNTH_A','reason']
    rel = relations(); rel['representative_asset_id'] = ''
    assert screen(c, listing_relations=rel).cardinality.n == 0
    rel = relations(); rel.loc[0,'review_status'] = 'pending'
    assert screen(c, listing_relations=rel).cardinality.n == 0
    assert screen(c, listing_relations=relations(), excluded_asset_ids=('SYNTH_B',)).cardinality.n == 0


@pytest.mark.parametrize('kwargs', [dict(include_stocks='false'),dict(markets=('XX',)),dict(tool_types=('banana',)),
    dict(asset_classes=('banana',)),dict(excluded_asset_ids=('unknown',)),dict(markets='US')])
def test_invalid_options(kwargs):
    with pytest.raises(ValueError): screen(candidate(), **kwargs)


@pytest.mark.parametrize('target', ['columns','index','nonfinite','window','eligible','structure'])
def test_inconsistent_candidate_rejected(target):
    c = candidate()
    if target == 'columns': c.matrix = pd.concat([c.matrix,c.matrix],axis=1)
    if target == 'index': c.matrix.index = ['2025-01-31']*60
    if target == 'nonfinite': c.matrix.iloc[0,0] = float('nan')
    if target == 'window': c.evidence['window_months'] = 59
    if target == 'eligible': c.data_eligibility.loc[0,'valid_months'] = 59
    if target == 'structure': c.structures = pd.concat([c.structures,c.structures],ignore_index=True)
    with pytest.raises(ValueError): screen(c)


def test_result_fingerprint_tracks_options_and_input():
    from portfolio.universe.screening import universe_result_is_current
    c = candidate(); r = screen(c)
    assert universe_result_is_current(r,c,k=30)
    assert not universe_result_is_current(r,c,k=20)
    assert not universe_result_is_current(r,c,k=30,include_stocks=True)
    c.assets.loc[0,'name'] = 'changed'
    assert not universe_result_is_current(r,c,k=30)


def test_absent_structures_exclude_and_empty_candidate_is_safe():
    c = candidate(); c.structures.loc[0,'binding_status'] = 'missing'
    r = screen(c)
    assert r.cardinality.n == 0 and 'structure_missing' in r.audit.iloc[0].reason
    c = candidate(); c.assets = c.assets.iloc[:0]; c.matrix = c.matrix.iloc[:,:0]
    c.data_eligibility = c.data_eligibility.iloc[:0]; c.structures = c.structures.iloc[:0]
    assert screen(c).cardinality.n == 0


def test_invalid_structure_date_cannot_count_as_evidence():
    c = candidate(); c.structures.loc[0,'source_as_of'] = 'not-a-date'
    assert screen(c).cardinality.n == 0


def test_invalid_k_reports_error_without_losing_candidate_diagnostics():
    r = screen(candidate(),k=True)
    assert r.cardinality.status == 'invalid_k' and r.cardinality.n == 1
    assert len(r.audit) == 1


def test_multiple_exclusions_are_reported_once_and_do_not_inflate_funnel():
    c = candidate([dict(asset_id='SYNTH',tool_type='stock',structure='leveraged',missing=True)])
    r = screen(c,markets=(),excluded_asset_ids=('SYNTH',))
    assert r.counts == dict(input_rows=1,identity_qualified=1,in_scope=0,data_qualified=0)
    reasons = r.audit.iloc[0].reason.split(';')
    assert len(set(reasons)) == len(reasons)
    assert {'unsupported_structure','direct_equity_excluded','market_out_of_scope','manually_excluded','missing_timing'} <= set(reasons)
