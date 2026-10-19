"""S07 deterministic, long-only member drafts; no utility or weight optimization."""
from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json
from numbers import Integral

import pandas as pd
from portfolio.data.quality import ASSET_CLASSES
from portfolio.evaluation.correlation import pearson_correlation
from .clustering import ClusterResult, cluster_correlations
from .reasons import selection_tables
from .screening import _validate, screen_candidates
from .selection_ranking import prepare_ranking, ranking_key

RULE_VERSION='category_cluster_cost_liquidity_id_v1'


@dataclass
class SelectionResult:
    selected_asset_ids: tuple
    reasons: pd.DataFrame
    alternatives: pd.DataFrame
    clusters: ClusterResult
    selected_correlation: pd.DataFrame
    high_correlation_pairs: pd.DataFrame
    evidence: dict
    fingerprint: str


def _ids(value,label):
    if isinstance(value,str): raise ValueError(label+'必须为资产 ID 集合')
    try: items=list(value)
    except TypeError as exc: raise ValueError(label+'必须为资产 ID 集合') from exc
    if any(not isinstance(a,str) or not a.strip() or a != a.strip() for a in items):
        raise ValueError(label+'必须使用有效资产 ID')
    if len(items) != len(set(items)): raise ValueError(label+'不能含重复项')
    return sorted(items)


def _minimums(value,k):
    if value is None: return {}
    if not isinstance(value,dict) or any(not isinstance(c,str) or c not in ASSET_CLASSES for c in value):
        raise ValueError('类别最低数必须使用已知资产类别')
    if any(isinstance(n,bool) or not isinstance(n,Integral) or n < 0 for n in value.values()):
        raise ValueError('类别最低数必须为非负整数')
    result={c:int(value[c]) for c in sorted(value)}
    if sum(result.values()) > k: raise ValueError('类别最低数合计超过 K')
    return result


def _canonical_candidate(candidate):
    """Row order is not economic content; keep source evidence while binding values."""
    c=deepcopy(candidate)
    for name in ['assets','data_eligibility','structures','coverage','reconciliation']:
        frame=getattr(c,name)
        keys=[key for key in ['asset_id','date','source_hash','source_row'] if key in frame]
        setattr(c,name,frame.sort_values(keys,na_position='last').reset_index(drop=True))
    c.matrix=c.matrix.sort_index().reindex(columns=sorted(c.matrix.columns))
    return c


def select_members(candidate, *, k, included_asset_ids=(), member_excluded_asset_ids=(),
                   category_minimums=None, ranking_data=None, rho_threshold=0.85, **screening_options):
    """Re-enter S05, then include manual items, category minima and group coverage.

    Member exclusions keep a product in N for comparison. Scope exclusions use
    S05's separate excluded_asset_ids and reduce N. Neither can bypass availability.
    """
    # Validate the original object before canonicalization; no caller-built gates.
    _validate(candidate)
    screened=screen_candidates(_canonical_candidate(candidate),k=k,**screening_options)
    if screened.cardinality.status != 'passed':
        raise ValueError('数量条件未通过：'+screened.cardinality.message)
    k=int(k);eligible=set(screened.eligible_asset_ids)
    included=_ids(included_asset_ids,'手动纳入');excluded=_ids(member_excluded_asset_ids,'成员排除')
    if set(included)-eligible: raise ValueError('手动纳入项不在合格候选中：'+', '.join(sorted(set(included)-eligible)))
    if set(excluded)-eligible: raise ValueError('成员排除项不在合格候选中：'+', '.join(sorted(set(excluded)-eligible)))
    if set(included) & set(excluded): raise ValueError('手动纳入与成员排除冲突')
    if len(included) > k: raise ValueError('手动纳入项超过 K')
    available=eligible-set(excluded)
    if len(available) < k: raise ValueError(f'成员排除后可选产品不足 K：{len(available)} < {k}')
    minima=_minimums(category_minimums,k)
    audit=screened.audit.set_index('asset_id')
    counts={c:sum(audit.loc[a,'asset_class'] == c for a in included) for c in minima}
    required=sum(max(0,minima[c]-counts[c]) for c in minima)
    if len(included)+required > k: raise ValueError('手动纳入后剩余名额不足以满足类别最低数')
    for category,minimum in minima.items():
        possible=sum(audit.loc[a,'asset_class'] == category for a in available)
        if possible < minimum:
            raise ValueError(f'类别 {category} 可选 {possible}，最低需要 {minimum}，缺口 {minimum-possible}')
    correlation=pearson_correlation(screened.matrix,train_start=screened.evidence['window_start'][:7],
                                    train_end=screened.evidence['window_end'][:7])
    clusters=cluster_correlations(correlation.matrix,rho_threshold=rho_threshold)
    ranking,ranking_evidence=prepare_ranking(ranking_data,asset_ids=set(candidate.data_eligibility.asset_id),
                                            decision_at=screened.evidence['decision_utc'])
    ranked=screened.audit.merge(ranking.reset_index(),on='asset_id',validate='one_to_one')
    rows=ranked.set_index('asset_id').to_dict('index')
    groups=clusters.memberships.set_index('asset_id').to_dict('index')
    selected=[];decisions={};covered=set()

    def add(aid,reason,phase):
        group=groups[aid];known=group['correlation_status'] == 'available'
        new=known and group['cluster_id'] not in covered
        decisions[aid]=dict(step=len(selected)+1,selection_reason=reason,phase=phase,new_known_cluster=new)
        selected.append(aid)
        if known: covered.add(group['cluster_id'])

    def choose(pool):
        def key(aid):
            group=groups[aid]
            new=group['correlation_status'] == 'available' and group['cluster_id'] not in covered
            return (not new,)+ranking_key(rows[aid] | {'asset_id':aid})
        return min(pool,key=key)

    for aid in included: add(aid,'manual_inclusion','manual')
    for category,minimum in minima.items():
        while sum(audit.loc[a,'asset_class'] == category for a in selected) < minimum:
            pool=[a for a in available-set(selected) if audit.loc[a,'asset_class'] == category]
            add(choose(pool),'category_minimum','category:'+category)
    while len(selected) < k:
        aid=choose(available-set(selected));group=groups[aid]
        new=group['correlation_status'] == 'available' and group['cluster_id'] not in covered
        add(aid,'new_known_cluster' if new else 'ranked_fill','fill')
    reasons,alternatives,pairs=selection_tables(screened.audit,ranking,clusters,correlation.matrix,
                                               selected,decisions,set(excluded),float(rho_threshold))
    selected_ids=tuple(selected)
    options=dict(k=k,included_asset_ids=included,member_excluded_asset_ids=excluded,
                 category_minimums=minima,rho_threshold=float(rho_threshold))
    payload=dict(rule_version=RULE_VERSION,screening_fingerprint=screened.fingerprint,
                 correlation_fingerprint=correlation.fingerprint,cluster_fingerprint=clusters.fingerprint,
                 options=options,ranking=ranking_evidence,selected_asset_ids=selected)
    fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True,allow_nan=False).encode()).hexdigest()
    warnings=['heuristic_not_global_optimum','current_universe_retrospective',
              'data_quality_60_months_tied','ranking_freshness_not_certified',
              'correlation_not_underlying_holdings_overlap']
    if ranking.loc[list(eligible),'fee_status'].eq('unknown').any(): warnings.append('missing_fee_data')
    if ranking.loc[list(eligible),'liquidity_status'].eq('unknown').any(): warnings.append('missing_liquidity_data')
    unknown=sum(groups[a]['correlation_status'] == 'unavailable' for a in selected)
    if unknown: warnings.append('selected_unknown_correlations')
    if not pairs.empty: warnings.append('selected_high_correlation_pairs')
    evidence=deepcopy(screened.evidence)
    evidence.update(rule_version=RULE_VERSION,screening_fingerprint=screened.fingerprint,
                    correlation_fingerprint=correlation.fingerprint,clustering=clusters.diagnostics,
                    selection_options=options,ranking=ranking_evidence,cardinality=asdict(screened.cardinality),
                    selected_asset_ids=list(selected_ids),selected_known_cluster_count=len(covered),
                    selected_unknown_correlation_count=unknown,high_correlation_pair_count=len(pairs),
                    selection_status='draft',portfolio_constructed=False,weights_generated=False,
                    diversification_certified=False,selection_fingerprint=fingerprint,warnings=warnings,
                    member_exclusions_change_n=False)
    selected_matrix=correlation.matrix.loc[sorted(selected),sorted(selected)].copy(deep=True)
    return SelectionResult(selected_ids,reasons,alternatives,clusters,selected_matrix,pairs,evidence,fingerprint)
