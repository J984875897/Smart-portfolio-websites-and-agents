"""Explain selections and candidate comparisons without promising valid swaps."""
import pandas as pd
from .clustering import BOUNDARY_TOLERANCE


def selection_tables(audit, ranking, clusters, correlation, selected, decisions, excluded, threshold):
    table=audit.copy(deep=True).merge(ranking.reset_index(),on='asset_id',how='left',validate='one_to_one')
    table=table.merge(clusters.memberships,on='asset_id',how='left',validate='one_to_one')
    rows=[];pair_rows=[]
    for row in table.to_dict('records'):
        aid=row['asset_id'];chosen=aid in selected
        selection=decisions.get(aid,{})
        reason=selection.get('selection_reason','not_selected_by_rule')
        if row['status'] != 'eligible': reason='screening_excluded:'+row['reason']
        elif aid in excluded: reason='member_excluded'
        peers=[other for other in selected if other != aid]
        values=correlation.loc[aid,peers].dropna() if aid in correlation.index else pd.Series(dtype=float)
        nearest=sorted(values.index,key=lambda other:(-values.loc[other],other))[0] if len(values) else None
        rows.append(row | dict(selected=chosen,direction='long' if chosen else '',
                               selection_reason=reason,selection_step=selection.get('step'),
                               selection_phase=selection.get('phase',''),
                               new_known_cluster_at_selection=selection.get('new_known_cluster',False),
                               max_selected_correlation=None if nearest is None else float(values.loc[nearest]),
                               most_correlated_selected_id=nearest,
                               known_selected_pair_count=len(values),
                               unknown_selected_pair_count=len(peers)-len(values)))
    reasons=pd.DataFrame(rows).sort_values('asset_id',ignore_index=True)
    alternatives=[];lookup=reasons.set_index('asset_id')
    for aid in reasons.loc[~reasons.selected & reasons.status.eq('eligible'),'asset_id']:
        if aid in excluded: continue
        same_group=[b for b in selected if lookup.loc[aid,'correlation_status'] == 'available'
                    and lookup.loc[b,'cluster_id'] == lookup.loc[aid,'cluster_id']]
        same_class=[b for b in selected if lookup.loc[b,'asset_class'] == lookup.loc[aid,'asset_class']]
        comparable=same_group or same_class
        b=sorted(comparable)[0] if comparable else None
        rho=correlation.loc[aid,b] if b is not None else None
        alternatives.append(dict(asset_id=aid,comparison_selected_id=b,
                                 comparison_basis='same_cluster' if same_group else
                                                  ('same_asset_class' if same_class else 'none'),
                                 correlation=None if pd.isna(rho) else float(rho),
                                 replacement_feasibility='not_evaluated'))
    for i,a in enumerate(sorted(selected)):
        for b in sorted(selected)[i+1:]:
            rho=correlation.loc[a,b]
            if pd.notna(rho) and rho+BOUNDARY_TOLERANCE >= threshold:
                pair_rows.append(dict(asset_a=a,asset_b=b,correlation=float(rho),
                                      same_cluster=lookup.loc[a,'cluster_id'] == lookup.loc[b,'cluster_id']))
    return (reasons,pd.DataFrame(alternatives,columns=['asset_id','comparison_selected_id',
            'comparison_basis','correlation','replacement_feasibility']),
            pd.DataFrame(pair_rows,columns=['asset_a','asset_b','correlation','same_cluster']))
