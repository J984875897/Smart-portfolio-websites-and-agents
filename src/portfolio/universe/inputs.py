"""Recompute monthly HKD candidate inputs; never trusts a cached eligibility flag."""
from copy import deepcopy
from dataclasses import dataclass
import json
import pandas as pd
from portfolio.data.contracts import TABLE_COLUMNS
from portfolio.data.fx import reconcile_hkd
from portfolio.data.alignment import align_monthly, TIMING_FIELDS
from portfolio.data.quality import CURRENCIES
from .input_evidence import input_evidence
from .structures import bind_structures


@dataclass
class CandidateInput:
    assets: pd.DataFrame
    matrix: pd.DataFrame
    data_eligibility: pd.DataFrame
    coverage: pd.DataFrame
    structures: pd.DataFrame
    reconciliation: pd.DataFrame
    evidence: dict
    input_fingerprint: str


def _identity(bundle, timing):
    for name in ['assets', 'observations']:
        frame = getattr(bundle, name)
        if not set(TABLE_COLUMNS[name]) <= set(frame.columns):
            raise ValueError(f'missing {name} columns')
    if not set(TIMING_FIELDS) <= set(timing.columns):
        raise ValueError('missing timing columns')
    aids = set()
    for frame in [bundle.assets, bundle.observations, timing]:
        for aid in frame.asset_id:
            if not isinstance(aid, str) or not aid.strip() or aid != aid.strip():
                raise ValueError('invalid asset_id')
            aids.add(aid)
    groups = {}
    for row in bundle.assets.to_dict('records'):
        groups.setdefault(row['asset_id'], []).append(row)
    problems = {aid: [] for aid in aids}
    unique = []
    listings = {}
    for aid in sorted(aids):
        rows = groups.get(aid, [])
        if not rows:
            problems[aid].append('missing_asset_metadata')
            continue
        # Comparing complete serialized rows avoids choosing an arbitrary winner.
        if len({json.dumps(r, sort_keys=True, default=str) for r in rows}) != 1:
            problems[aid].append('conflicting_asset_metadata')
            continue
        row = rows[0]
        for field in ['ticker', 'exchange', 'currency']:
            if not isinstance(row[field], str) or not row[field].strip():
                problems[aid].append('missing_' + field)
            elif row[field] != row[field].strip():
                problems[aid].append('noncanonical_' + field)
        if row['currency'] not in CURRENCIES:
            problems[aid].append('invalid_asset_currency')
        if not isinstance(row['share_class'], str) or row['share_class'] != row['share_class'].strip():
            problems[aid].append('invalid_share_class')
        if problems[aid]:
            continue
        key = tuple(row[k] for k in ['exchange', 'ticker', 'share_class', 'currency'])
        listings.setdefault(key, []).append(aid)
        unique.append(row)
    for ids in listings.values():
        if len(ids) > 1:
            for aid in ids: problems[aid].append('duplicate_listing_identity')
    clean = pd.DataFrame([r for r in unique if not problems[r['asset_id']]], columns=bundle.assets.columns)
    return sorted(aids), problems, clean


def prepare_candidate_input(bundle, fx, timing, structures=None, *, end_month,
                            decision_at, adjusted_price_assets=()):
    """Fixed 60-month result with independent identity and declared-time reports."""
    structures = pd.DataFrame() if structures is None else structures
    confirmed = tuple(adjusted_price_assets)
    evidence, fingerprint, checked = input_evidence(
        bundle, fx, timing, structures, end_month=end_month, decision_at=decision_at,
        adjusted_price_assets=confirmed)
    aids, problems, assets = _identity(bundle, checked['timing'])
    for frame in [bundle.assets, bundle.observations]:
        for aid in frame.loc[frame.frequency != 'monthly', 'asset_id'].unique():
            if 'monthly_preparation_required' not in problems[aid]:
                problems[aid].append('monthly_preparation_required')
    bound = bind_structures(checked['structures'], aids)
    clean_bundle = deepcopy(bundle)
    clean_bundle.assets = assets
    hkd = reconcile_hkd(clean_bundle, checked['fx'], adjusted_price_assets=confirmed)
    aligned = align_monthly(hkd.reconciliation, checked['timing'], asset_ids=aids,
                            end_month=end_month, decision_at=decision_at, months=60)
    report = aligned.report.copy(deep=True)
    for i, row in report.iterrows():
        errors = problems[row.asset_id]
        if errors:
            codes = errors + ([row.reason] if row.reason != 'ok' else [])
            report.loc[i, ['status', 'reason']] = ['excluded', ';'.join(codes)]
    eligible = report.loc[report.status == 'eligible', 'asset_id'].tolist()
    matrix = aligned.matrix.reindex(columns=eligible).copy(deep=True)
    evidence.update(window_start=aligned.window_start, window_end=aligned.window_end,
                    decision_utc=aligned.decision_at,
                    fx_issues=json.loads(hkd.fx_issues.to_json(orient='records', double_precision=15, default_handler=str)),
                    diagnostic_nonfinite_values='null; original values remain in source tables')
    return CandidateInput(assets.copy(deep=True), matrix, report, aligned.coverage.copy(deep=True),
                          bound, hkd.reconciliation.copy(deep=True), evidence, fingerprint)


def candidate_input_is_current(result, bundle, fx, timing, structures=None, *,
                               end_month, decision_at, adjusted_price_assets=()):
    """A changed or unreadable source invalidates a prior result; no data is changed."""
    try:
        _, fingerprint, _ = input_evidence(
            bundle, fx, timing, pd.DataFrame() if structures is None else structures,
            end_month=end_month, decision_at=decision_at, adjusted_price_assets=adjusted_price_assets)
    except (ValueError, TypeError, KeyError, OSError):
        return False
    return isinstance(result, CandidateInput) and result.input_fingerprint == fingerprint
