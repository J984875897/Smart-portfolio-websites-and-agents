from copy import deepcopy
from io import BytesIO
import pandas as pd
import pytest
from portfolio.data.contracts import DataBundle, TABLE_COLUMNS
from portfolio.data.importer import read_file


def inputs():
    from portfolio.universe.samples import sample_candidate_inputs
    return sample_candidate_inputs()


PARAMS = dict(end_month='2025-01', decision_at='2025-02-01T06:00:00+08:00')


def prepare(*args, **kwargs):
    from portfolio.universe.inputs import prepare_candidate_input
    return prepare_candidate_input(*args, **(PARAMS | kwargs))


def test_complete_window_expected_values_and_no_mutation():
    args = inputs(); before = deepcopy(args)
    result = prepare(*args)
    assert list(result.matrix) == ['HKD_COMPLETE', 'USD_COMPLETE']
    assert result.matrix.shape == (60, 2)
    assert ((result.matrix - .01).abs() < 1e-12).all().all()
    assert result.matrix.index[0] == '2020-02-29'
    assert result.matrix.index[-1] == '2025-01-31'
    report = result.data_eligibility.set_index('asset_id')
    for aid in ['MISSING_MIDDLE', 'SHORT_HISTORY', 'MISSING_END_FX']:
        assert report.loc[aid, 'valid_months'] == 59
        assert report.loc[aid, 'status'] == 'excluded'
    assert 'missing_fx_end' in report.loc['MISSING_END_FX', 'reason']
    for name in TABLE_COLUMNS:
        pd.testing.assert_frame_equal(getattr(args[0], name), getattr(before[0], name))
    for frame, saved in zip(args[1:], before[1:]): pd.testing.assert_frame_equal(frame, saved)
    args[0].assets.loc[0, 'name'] = 'changed'
    assert result.assets.iloc[0]['name'] != 'changed'
    assert result.evidence['base_currency'] == 'HKD'
    assert result.evidence['window_months'] == 60
    assert result.evidence['historical_universe_certified'] is False
    assert result.evidence['timing_basis'] == 'importer_declared'
    assert not hasattr(result, 'N')


def test_early_and_missing_timing():
    bundle, fx, timing, structures = inputs()
    early = prepare(bundle, fx, timing, structures, decision_at='2025-01-31T17:00:00+08:00')
    assert list(early.matrix) == ['HKD_COMPLETE']
    missing = prepare(bundle, fx, timing.iloc[:0], structures)
    assert missing.matrix.shape == (60, 0)
    assert missing.data_eligibility.reason.str.contains('missing_timing').all()


@pytest.mark.parametrize('target', ['observation', 'asset', 'fx', 'timing', 'structure', 'provenance', 'config', 'raw', 'decision', 'confirmation'])
def test_every_input_change_invalidates(target):
    from portfolio.universe.inputs import candidate_input_is_current
    bundle, fx, timing, structures = inputs()
    result = prepare(bundle, fx, timing, structures)
    assert candidate_input_is_current(result, bundle, fx, timing, structures, **PARAMS)
    params = dict(PARAMS)
    if target == 'observation': bundle.observations.loc[0, 'value'] += 1e-13
    elif target == 'asset': bundle.assets.loc[0, 'name'] = 'changed'
    elif target == 'fx': fx.loc[0, 'hkd_per_unit'] = 7.9
    elif target == 'timing': timing.loc[0, 'available_at'] = '2025-03-01T00:00:00Z'
    elif target == 'structure': structures.loc[0, 'source_reference'] = 'new declaration'
    elif target == 'provenance': bundle.provenance = pd.DataFrame([dict(source_name='changed')])
    elif target == 'config': bundle.configs.append({'source_name': 'new'})
    elif target == 'raw':
        import hashlib
        payload = b'new raw file'; bundle.raw_sources[hashlib.sha256(payload).hexdigest()] = payload
    elif target == 'decision': params['decision_at'] = '2025-02-02T00:00:00Z'
    elif target == 'confirmation': params['adjusted_price_assets'] = ['HKD_COMPLETE']
    assert not candidate_input_is_current(result, bundle, fx, timing, structures, **params)


def test_missing_structures_does_not_invent_review_or_filter_data():
    bundle, fx, timing, _ = inputs()
    result = prepare(bundle, fx, timing)
    assert result.structures.binding_status.eq('missing').all()
    assert list(result.matrix) == ['HKD_COMPLETE', 'USD_COMPLETE']


def test_exact_metadata_duplicate_folded_but_conflicts_excluded():
    bundle, fx, timing, structures = inputs()
    bundle.assets = pd.concat([bundle.assets, bundle.assets.iloc[[0]]], ignore_index=True)
    assert list(prepare(bundle, fx, timing, structures).matrix) == ['HKD_COMPLETE', 'USD_COMPLETE']
    bundle.assets.loc[len(bundle.assets)-1, 'currency'] = 'USD'
    result = prepare(bundle, fx, timing, structures)
    assert 'HKD_COMPLETE' not in result.matrix
    assert 'conflicting_asset_metadata' in result.data_eligibility.set_index('asset_id').loc['HKD_COMPLETE', 'reason']


def test_two_ids_one_listing_excluded_and_unknown_observation_reported():
    bundle, fx, timing, structures = inputs()
    duplicate = bundle.assets.iloc[[0]].copy(); duplicate['asset_id'] = 'SAME_LISTING'
    bundle.assets = pd.concat([bundle.assets, duplicate], ignore_index=True)
    orphan = bundle.observations.iloc[[0]].copy(); orphan['asset_id'] = 'ORPHAN'
    bundle.observations = pd.concat([bundle.observations, orphan], ignore_index=True)
    result = prepare(bundle, fx, timing, structures)
    report = result.data_eligibility.set_index('asset_id')
    assert 'duplicate_listing_identity' in report.loc['HKD_COMPLETE', 'reason']
    assert 'duplicate_listing_identity' in report.loc['SAME_LISTING', 'reason']
    assert 'missing_asset_metadata' in report.loc['ORPHAN', 'reason']
    assert not {'SAME_LISTING', 'ORPHAN', 'HKD_COMPLETE'} & set(result.matrix)


@pytest.mark.parametrize('which', ['fx', 'timing', 'structures'])
def test_file_backed_edits_rejected_and_physical_sources_retained(which):
    args = list(inputs()); i = {'fx': 1, 'timing': 2, 'structures': 3}[which]
    payload = args[i].to_csv(index=False).encode()
    args[i] = read_file(payload, filename=which+'.csv')
    result = prepare(*args)
    assert result.evidence['inputs'][which]['source_file'] == which+'.csv'
    if which == 'structures':
        assert result.structures.source_file.eq('structures.csv').all()
        assert result.structures.source_row.min() == 2
    args[i].iloc[0, 1] = 'changed'
    with pytest.raises(ValueError, match='unchanged'): prepare(*args)


def test_xlsx_structure_provenance_and_conflicting_rows():
    bundle, fx, timing, structures = inputs()
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        structures.to_excel(writer, sheet_name='products', index=False)
    frame = read_file(buffer.getvalue(), filename='review.xlsx', sheet_name='products')
    result = prepare(bundle, fx, timing, frame)
    assert result.structures.source_sheet.eq('products').all()
    duplicate = structures.iloc[[0]].copy(); duplicate['structure'] = 'inverse'
    with pytest.raises(ValueError, match='conflicting structure'):
        prepare(bundle, fx, timing, pd.concat([structures, duplicate], ignore_index=True))


@pytest.mark.parametrize('problem', ['duplicate_columns', 'invalid_id', 'unknown_structure_id', 'invalid_structure_date', 'raw_hash'])
def test_invalid_inputs_fail_explicitly(problem):
    bundle, fx, timing, structures = inputs()
    if problem == 'duplicate_columns': fx.columns = ['date', 'currency', 'currency', 'source_name']
    elif problem == 'invalid_id': bundle.assets.loc[0, 'asset_id'] = ''
    elif problem == 'unknown_structure_id': structures.loc[0, 'asset_id'] = 'TYPO'
    elif problem == 'invalid_structure_date': structures.loc[0, 'source_as_of'] = '2025-13-40'
    elif problem == 'raw_hash': bundle.raw_sources['0'*64] = b'not matching'
    with pytest.raises(ValueError): prepare(bundle, fx, timing, structures)


def test_empty_bundle_stable_schema_and_no_network(monkeypatch):
    import socket
    monkeypatch.setattr(socket, 'create_connection', lambda *a, **k: pytest.fail('network'))
    _, fx, timing, _ = inputs()
    result = prepare(DataBundle(), fx.iloc[:0], timing.iloc[:0])
    assert result.matrix.shape == (60, 0)
    assert result.data_eligibility.empty and 'asset_id' in result.data_eligibility


@pytest.mark.parametrize('bad_quote', [float('nan'), float('inf'), float('-inf')])
def test_bad_fx_retains_json_safe_evidence_and_never_reuses_values(bad_quote):
    import json
    bundle, fx, timing, structures = inputs()
    fx.loc[(fx.currency == 'USD') & (fx.date == '2025-01-31'), 'hkd_per_unit'] = bad_quote
    result = prepare(bundle, fx, timing, structures)
    assert 'USD_COMPLETE' not in result.matrix
    assert result.evidence['fx_issues']
    assert result.evidence['fx_issues'][0]['hkd_per_unit'] is None
    json.dumps(result.evidence, allow_nan=False)


def test_reordering_keeps_id_values_matched_and_small_value_change_detected():
    bundle, fx, timing, structures = inputs()
    bundle.observations.loc[bundle.observations.asset_id == 'HKD_COMPLETE', 'value'] = .02
    bundle.assets = bundle.assets.iloc[::-1].copy()
    bundle.observations = bundle.observations.iloc[::-1].copy()
    result = prepare(bundle, fx, timing.iloc[::-1].copy(), structures.iloc[::-1].copy())
    assert result.matrix.HKD_COMPLETE.eq(.02).all()
    assert ((result.matrix.USD_COMPLETE - .01).abs() < 1e-12).all()


def test_input_file_name_and_sheet_changes_invalidate():
    from portfolio.universe.inputs import candidate_input_is_current
    bundle, fx, timing, structures = inputs()
    raw = timing.to_csv(index=False).encode()
    first = read_file(raw, filename='first.csv')
    result = prepare(bundle, fx, first, structures)
    renamed = read_file(raw, filename='renamed.csv')
    assert not candidate_input_is_current(result, bundle, fx, renamed, structures, **PARAMS)


def test_empty_timing_header_rejected_and_structure_pending_stays_separate():
    bundle, fx, timing, structures = inputs()
    with pytest.raises(ValueError, match='timing columns'):
        prepare(bundle, fx, pd.DataFrame(), structures)
    structures.loc[0, 'review_status'] = 'pending'
    result = prepare(bundle, fx, timing, structures)
    assert result.structures.set_index('asset_id').loc['HKD_COMPLETE', 'binding_status'] == 'pending'
    assert 'HKD_COMPLETE' in result.matrix


@pytest.mark.parametrize('which', [1, 2, 3])
def test_unverified_in_memory_row_attrs_cannot_change_provenance(which):
    from portfolio.universe.inputs import candidate_input_is_current
    args = list(inputs())
    result = prepare(*args)
    args[which].attrs['source_rows'] = [999] * len(args[which])
    again = prepare(*args)
    assert candidate_input_is_current(result, *args, **PARAMS)
    pd.testing.assert_frame_equal(result.coverage, again.coverage)
    pd.testing.assert_frame_equal(result.structures, again.structures)
    pd.testing.assert_frame_equal(result.reconciliation, again.reconciliation)


@pytest.mark.parametrize('field', ['ticker', 'exchange', 'share_class'])
def test_noncanonical_listing_fields_cannot_bypass_identity(field):
    bundle, fx, timing, structures = inputs()
    duplicate = bundle.assets.iloc[[0]].copy()
    duplicate['asset_id'] = 'DUP'
    duplicate[field] = duplicate[field] + ' '
    obs = bundle.observations[bundle.observations.asset_id == 'HKD_COMPLETE'].copy()
    obs['asset_id'] = 'DUP'
    times = timing[timing.asset_id == 'HKD_COMPLETE'].copy(); times['asset_id'] = 'DUP'
    bundle.assets = pd.concat([bundle.assets, duplicate], ignore_index=True)
    bundle.observations = pd.concat([bundle.observations, obs], ignore_index=True)
    result = prepare(bundle, fx, pd.concat([timing, times], ignore_index=True), structures)
    assert 'DUP' not in result.matrix
    assert result.data_eligibility.set_index('asset_id').loc['DUP', 'status'] == 'excluded'


def test_corrupt_xlsx_invalidates_without_raising():
    from portfolio.universe.inputs import candidate_input_is_current
    bundle, fx, timing, structures = inputs()
    result = prepare(bundle, fx, timing, structures)
    timing.attrs.update(source_file='bad.xlsx', raw_bytes=b'broken spreadsheet')
    assert not candidate_input_is_current(result, bundle, fx, timing, structures, **PARAMS)


def test_daily_input_explicitly_requires_monthly_preparation():
    bundle, fx, timing, structures = inputs()
    # Multiple daily observations within one month can also produce ambiguity;
    # the adapter must still explain the upstream frequency problem.
    bundle.assets['frequency'] = 'daily'
    bundle.observations['frequency'] = 'daily'
    extra = bundle.observations.iloc[[0]].copy()
    extra['date'] = '2020-01-30'
    bundle.observations = pd.concat([bundle.observations, extra], ignore_index=True)
    result = prepare(bundle, fx, timing, structures)
    assert result.matrix.shape == (60, 0)
    assert result.data_eligibility.reason.str.contains('monthly_preparation_required').all()
    assert len(result.assets) == len(bundle.assets)
