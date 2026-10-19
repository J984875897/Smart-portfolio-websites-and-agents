"""Candidate scope and count gates over a structurally checked S05-A snapshot."""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import numpy as np
import pandas as pd
from portfolio.allocation.cardinality import check_cardinality
from portfolio.data.quality import ASSET_CLASSES
from .inputs import CandidateInput
from .classification import classify, TOOL_ORIGINS, EXCHANGE_IDENTITIES
from .listing_identity import listing_identity
from .input_evidence import frame_evidence

IDENTITY_CODES = {'missing_asset_metadata','conflicting_asset_metadata','duplicate_listing_identity',
                  'missing_ticker','missing_exchange','missing_currency','invalid_asset_currency',
                  'invalid_share_class','noncanonical_ticker','noncanonical_exchange','noncanonical_currency'}


@dataclass
class UniverseResult:
    eligible_asset_ids: tuple
    matrix: pd.DataFrame
    audit: pd.DataFrame
    counts: dict
    cardinality: object
    evidence: dict
    fingerprint: str


def _options(value, allowed, name):
    if value is None: return sorted(allowed)
    if isinstance(value, str): raise ValueError(name + ' must be a collection')
    try:
        items = set(value)
        if not items <= set(allowed): raise ValueError('unknown ' + name)
        return sorted(items)
    except TypeError as exc:
        raise ValueError('invalid ' + name) from exc


def _validate(candidate):
    if not isinstance(candidate, CandidateInput): raise ValueError('CandidateInput required')
    c = candidate
    for frame, columns in [(c.assets, {'asset_id','ticker','name','exchange','currency','share_class','tool_type','asset_class'}),
                           (c.data_eligibility, {'asset_id','status','reason','valid_months','missing_months'}),
                           (c.structures, {'asset_id','market','canonical_tool_type','structure','binding_status','review_status','source_name','source_reference','source_as_of'})]:
        if not frame.columns.is_unique or not columns <= set(frame.columns):
            raise ValueError('incomplete candidate table')
        if frame.asset_id.duplicated().any(): raise ValueError('duplicate candidate asset_id')
    if c.evidence.get('base_currency') != 'HKD' or c.evidence.get('window_months') != 60:
        raise ValueError('60-month HKD input required')
    if (c.evidence.get('research_mode') != 'current_universe_retrospective'
        or c.evidence.get('historical_universe_certified') is not False
        or c.evidence.get('timing_basis') != 'importer_declared'):
        raise ValueError('unsupported research evidence mode')
    periods = pd.period_range(end=c.evidence['window_end'], periods=60, freq='M')
    expected = [p.end_time.date().isoformat() for p in periods]
    if c.evidence['window_start'] != expected[0] or list(c.matrix.index) != expected:
        raise ValueError('inconsistent monthly window')
    report = c.data_eligibility
    if not set(report.status) <= {'eligible','excluded'}: raise ValueError('invalid eligibility status')
    eligible = report.loc[report.status == 'eligible']
    if not eligible.valid_months.eq(60).all() or not eligible.missing_months.eq(0).all():
        raise ValueError('inconsistent eligibility counts')
    if (not c.matrix.columns.is_unique or set(c.matrix) != set(eligible.asset_id)
        or not set(c.matrix) <= set(c.assets.asset_id)
        or set(c.structures.asset_id) != set(report.asset_id)
        or not set(c.assets.asset_id) <= set(report.asset_id)):
        raise ValueError('inconsistent asset/matrix/structure binding')
    try:
        values = c.matrix.to_numpy(dtype=float)
        if not np.isfinite(values).all() or (values < -1).any(): raise ValueError('invalid HKD returns')
    except (TypeError, ValueError) as exc:
        raise ValueError('invalid HKD returns') from exc


def _fingerprint(c, options, relations):
    payload = dict(input_fingerprint=c.input_fingerprint, evidence=c.evidence, options=options,
                   tables={name:frame_evidence(getattr(c,name)) for name in
                           ['assets','matrix','data_eligibility','structures','coverage','reconciliation']},
                   listing_relations=frame_evidence(relations))
    return hashlib.sha256(json.dumps(payload,sort_keys=True,allow_nan=False).encode()).hexdigest()


def screen_candidates(candidate, *, k, markets=('US','HK'), tool_types=None, asset_classes=None,
                      include_stocks=False, excluded_asset_ids=(), listing_relations=None):
    """Does not authenticate suppliers, select members, or establish diversification."""
    _validate(candidate)
    c = candidate
    aids = sorted(c.data_eligibility.asset_id)
    if type(include_stocks) is not bool: raise ValueError('include_stocks must be boolean')
    options = dict(k=k, markets=_options(markets, {'US','HK'}, 'markets'),
                   tool_types=_options(tool_types, TOOL_ORIGINS, 'tool_types'),
                   asset_classes=_options(asset_classes, ASSET_CLASSES, 'asset_classes'),
                   include_stocks=include_stocks,
                   excluded_asset_ids=_options(excluded_asset_ids, aids, 'excluded_asset_ids'))
    relations, relation_reasons, relation_statuses = listing_identity(listing_relations, aids)
    assets = c.assets.set_index('asset_id').to_dict('index')
    structures = c.structures.set_index('asset_id').to_dict('index')
    # Recheck listing keys so an inconsistent in-memory snapshot cannot inflate N.
    keys = {}
    for aid, asset in assets.items():
        key = (EXCHANGE_IDENTITIES.get(asset['exchange'], asset['exchange']),
               asset['ticker'], asset['share_class'], asset['currency'])
        keys.setdefault(key, []).append(aid)
    duplicates = {a for ids in keys.values() if len(ids)>1 for a in ids}
    rows = []
    for report in c.data_eligibility.to_dict('records'):
        aid = report['asset_id']; asset = assets.get(aid)
        identity_reasons = [code for code in str(report['reason']).split(';') if code in IDENTITY_CODES]
        if asset is None and not identity_reasons: identity_reasons.append('missing_asset_metadata')
        if aid in duplicates: identity_reasons.append('duplicate_listing_identity')
        identity_reasons += relation_reasons[aid]
        scope_reasons = []
        market = tool = ''
        if asset is not None:
            market, tool, scope_reasons = classify(asset,structures[aid],include_stocks=include_stocks)
            if market not in options['markets']: scope_reasons.append('market_out_of_scope')
            if tool not in options['tool_types']: scope_reasons.append('tool_out_of_scope')
            if asset['asset_class'] not in options['asset_classes']: scope_reasons.append('asset_class_out_of_scope')
        if aid in options['excluded_asset_ids']: scope_reasons.append('manually_excluded')
        identity_ok = not identity_reasons
        in_scope = identity_ok and not scope_reasons
        data_ok = report['status'] == 'eligible'
        reasons = identity_reasons + scope_reasons
        if not data_ok: reasons += str(report['reason']).split(';')
        reasons = list(dict.fromkeys(code for code in reasons if code and code != 'ok'))
        rows.append(dict(asset or {}, **{key:report[key] for key in ['asset_id','valid_months','missing_months']},
                         market=market,canonical_tool_type=tool,structure=structures[aid]['structure'],
                         structure_status=structures[aid]['binding_status'],
                         structure_source_name=structures[aid]['source_name'],
                         structure_source_reference=structures[aid]['source_reference'],
                         structure_source_as_of=structures[aid]['source_as_of'],
                         listing_relationship_status=relation_statuses[aid],
                         identity_qualified=identity_ok,in_scope=in_scope,data_qualified=data_ok,
                         status='eligible' if in_scope and data_ok else 'excluded',
                         reason=';'.join(reasons) if reasons else 'ok',
                         window_start=c.evidence['window_start'],window_end=c.evidence['window_end']))
    audit = pd.DataFrame(rows).reindex(columns=list(rows[0]) if rows else
             ['asset_id','identity_qualified','in_scope','data_qualified','status','reason'])
    audit = audit.sort_values('asset_id',ignore_index=True)
    ids = tuple(audit.loc[audit.status == 'eligible','asset_id'])
    counts = dict(input_rows=c.evidence['bundle_tables']['assets']['rows'],
                  identity_qualified=int(audit.identity_qualified.sum()),
                  in_scope=int(audit.in_scope.sum()),data_qualified=len(ids))
    cardinality = check_cardinality(k,len(ids))
    # Invalid K values are permitted for user feedback; serialize a stable description.
    fingerprint_options = options | {'k':{'type':type(k).__name__,'value':repr(k)}}
    fingerprint = _fingerprint(c,fingerprint_options,relations)
    evidence = deepcopy(c.evidence)
    evidence.update(input_fingerprint=c.input_fingerprint,screening_options=fingerprint_options,
                    listing_relations=frame_evidence(relations),
                    listing_relation_records=relations.to_dict('records'),
                    classification_basis='importer_declared',portfolio_constructed=False)
    return UniverseResult(ids,c.matrix.reindex(columns=ids).copy(deep=True),audit,counts,
                          cardinality,evidence,fingerprint)


def universe_result_is_current(result, candidate, **params):
    try:
        return isinstance(result,UniverseResult) and screen_candidates(candidate,**params).fingerprint == result.fingerprint
    except (ValueError,TypeError,KeyError):
        return False
