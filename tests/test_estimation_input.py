"""Only S05-qualified 60-month inputs may enter the formal estimation path."""
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from portfolio.universe.inputs import prepare_candidate_input
from portfolio.universe.screening_samples import sample_screening_inputs

PARAMS=dict(end_month='2025-01',decision_at='2025-02-01T06:00:00+08:00')


def candidate(vary=False):
    bundle,fx,timing,structures=sample_screening_inputs()
    if vary:
        rng=np.random.default_rng(5052)
        bundle.observations['value']=rng.normal(.005,.04,len(bundle.observations))
        bundle.assets.loc[bundle.assets.index[50:],'asset_class']='bond'
    return prepare_candidate_input(bundle,fx,timing,structures,**PARAMS)


def test_boundary_count_pass_does_not_make_constant_sample_usable():
    from portfolio.models.estimation_input import estimate_candidates
    c=candidate();before=deepcopy(c)
    r=estimate_candidates(c,k=30)
    assert r.diagnostics['n_observations'] == 60 and len(r.asset_ids) == 100
    assert not r.diagnostics['usable_for_optimization']
    assert len(r.diagnostics['constant_assets']) == 100
    assert r.evidence['historical_universe_certified'] is False
    assert r.evidence['portfolio_constructed'] is False
    assert r.evidence['timing_basis'] == 'importer_declared'
    assert r.evidence['input_fingerprint'] == c.input_fingerprint
    assert len(r.evidence['screening_fingerprint']) == 64
    assert r.evidence['cardinality']['status'] == 'passed'
    pd.testing.assert_frame_equal(c.matrix,before.matrix)
    pd.testing.assert_frame_equal(c.assets,before.assets)
    r.evidence['inputs']['timing']['rows']=-1
    assert c.evidence['inputs']['timing']['rows'] != -1


def test_nonconstant_raw_input_is_qualified_reordered_and_estimated():
    from portfolio.models.estimation_input import estimate_candidates
    from portfolio.models.moments import estimate_moments
    from portfolio.universe.screening import screen_candidates
    c=candidate(True); r=estimate_candidates(c,k=30)
    s=screen_candidates(c,k=30)
    classes=s.audit.set_index('asset_id').loc[list(s.eligible_asset_ids),'asset_class']
    independent=estimate_moments(s.matrix,classes,train_start='2020-02',train_end='2025-01')
    assert r.fingerprint == independent.fingerprint
    assert r.diagnostics['usable_for_optimization']
    assert r.summary.asset_class.value_counts().to_dict() == {'equity':50,'bond':50}
    pd.testing.assert_frame_equal(r.shrunk_cov_ann,independent.shrunk_cov_ann)


@pytest.mark.parametrize('options', [dict(k=30,excluded_asset_ids=['SYNTH_SCREEN_099']),dict(k=101),dict(k=True),dict(k=30,markets=())])
def test_rechecks_count_and_scope_instead_of_accepting_cached_pass(options):
    from portfolio.models.estimation_input import estimate_candidates
    with pytest.raises(ValueError,match='数量|候选产品池'):
        estimate_candidates(candidate(),**options)


def test_malformed_monthly_snapshot_rejected():
    from portfolio.models.estimation_input import estimate_candidates
    c=candidate();c.matrix=c.matrix.iloc[1:]
    with pytest.raises(ValueError): estimate_candidates(c,k=30)


def test_real_daily_input_remains_blocked_and_source_unmodified():
    from portfolio.models.estimation_input import estimate_candidates
    from portfolio.data.contracts import DataBundle
    from portfolio.data.alignment import TIMING_FIELDS
    import hashlib
    root=Path(__file__).resolve().parents[1]
    path=Path(json.loads((root/'outputs/acceptance/S02/import_summary.json').read_text())['real_bundle_path'])
    def hashes(): return {str(p.relative_to(path)):hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob('*') if p.is_file()}
    before=hashes();bundle=DataBundle.load(path)
    c=prepare_candidate_input(bundle,pd.DataFrame(columns=['date','currency','hkd_per_unit','source_name']),
                              pd.DataFrame(columns=TIMING_FIELDS),adjusted_price_assets=bundle.assets.asset_id.tolist(),**PARAMS)
    assert c.matrix.shape[1] == 0
    with pytest.raises(ValueError,match='候选产品池'):
        estimate_candidates(c,k=30)
    assert hashes() == before
