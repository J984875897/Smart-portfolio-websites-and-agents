"""Deterministic complete linkage; unavailable correlations never become zero."""
from dataclasses import dataclass
import hashlib
import heapq
import json
from numbers import Real

import numpy as np
import pandas as pd

RULE_VERSION = 'complete_linkage_id_ties_v1'
BOUNDARY_TOLERANCE = 1e-12


@dataclass
class ClusterResult:
    memberships: pd.DataFrame
    merges: pd.DataFrame
    diagnostics: dict
    fingerprint: str


def _checked(matrix, threshold):
    if (isinstance(threshold,(bool,np.bool_)) or not isinstance(threshold,Real)
        or not np.isfinite(threshold) or not 0 <= threshold <= 1):
        raise ValueError('rho_threshold must be a real number in [0,1]')
    if (not isinstance(matrix,pd.DataFrame) or matrix.empty
        or not matrix.index.is_unique or not matrix.columns.is_unique
        or set(matrix.index) != set(matrix.columns)):
        raise ValueError('correlation requires unique matching asset IDs')
    ids=list(matrix.index)
    if any(not isinstance(a,str) or not a.strip() or a != a.strip() for a in ids):
        raise ValueError('canonical asset IDs required')
    x=matrix.loc[sorted(ids),sorted(ids)].copy(deep=True)
    if any(isinstance(v,(bool,np.bool_)) or not isinstance(v,Real) for v in x.to_numpy().flat):
        raise ValueError('correlation must be real numeric values, not booleans')
    a=x.to_numpy(dtype=float)
    if np.isinf(a).any() or (np.abs(a[np.isfinite(a)]) > 1).any():
        raise ValueError('correlation outside [-1,1]')
    if not np.array_equal(a,a.T,equal_nan=True):
        raise ValueError('correlation must be symmetric')
    unknown=np.isnan(a).all(axis=1)
    expected=unknown[:,None] | unknown[None,:]
    if not np.array_equal(np.isnan(a),expected):
        raise ValueError('partial correlation missingness is not supported')
    if not np.equal(np.diag(a)[~unknown],1.).all():
        raise ValueError('available correlation diagonal must be one')
    return x,unknown


def cluster_correlations(matrix, *, rho_threshold=0.85):
    """Merge nearest clusters by their maximum pair distance, with stable ID ties.

    A heap avoids a cubic rescan. Equal distances are resolved using the two
    sorted member tuples. Undefined rows are never fed to the distance routine.
    """
    x,unknown=_checked(matrix,rho_threshold)
    ids=list(x.index);known=[aid for aid,flag in zip(ids,unknown) if not flag]
    clusters={i:(aid,) for i,aid in enumerate(known)}
    distances={};heap=[]

    def push(i,j,d):
        if clusters[j] < clusters[i]: i,j=j,i
        distances[min(i,j),max(i,j)]=d
        heapq.heappush(heap,(d,clusters[i],clusters[j],i,j))

    for i,a in enumerate(known):
        for j in range(i+1,len(known)):
            push(i,j,1.-float(x.loc[a,known[j]]))
    merges=[];next_id=len(known)
    while heap:
        d,left,right,i,j=heapq.heappop(heap)
        if i not in clusters or j not in clusters: continue
        if d > 1.-float(rho_threshold)+BOUNDARY_TOLERANCE: break
        remaining=[c for c in clusters if c not in {i,j}]
        updated={c:max(distances[min(i,c),max(i,c)],distances[min(j,c),max(j,c)])
                 for c in remaining}
        members=tuple(sorted(left+right))
        merges.append(dict(left_members=json.dumps(left),right_members=json.dumps(right),
                           maximum_distance=d,minimum_correlation=1.-d,size=len(members)))
        del clusters[i];del clusters[j]
        clusters[next_id]=members
        for c,distance in updated.items(): push(next_id,c,distance)
        next_id+=1
    groups=sorted(clusters.values());rows=[]
    for number,members in enumerate(groups,1):
        for aid in members:
            rows.append(dict(asset_id=aid,cluster_id=f'C{number:03d}',
                             correlation_status='available',cluster_size=len(members)))
    unavailable=[aid for aid,flag in zip(ids,unknown) if flag]
    for number,aid in enumerate(unavailable,1):
        rows.append(dict(asset_id=aid,cluster_id=f'U{number:03d}',
                         correlation_status='unavailable',cluster_size=1))
    memberships=pd.DataFrame(rows).sort_values('asset_id',ignore_index=True)
    payload=dict(rule_version=RULE_VERSION,rho_threshold=float(rho_threshold),
                 boundary_tolerance=BOUNDARY_TOLERANCE,
                 asset_ids=ids,correlation=[[None if np.isnan(v) else float(v) for v in row]
                                            for row in x.to_numpy()])
    fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True,allow_nan=False).encode()).hexdigest()
    diagnostics=dict(rule_version=RULE_VERSION,method='complete_linkage_1_minus_rho',
                     rho_threshold=float(rho_threshold),boundary_tolerance=BOUNDARY_TOLERANCE,
                     tie_break='sorted_member_asset_id_tuples',known_cluster_count=len(groups),
                     unknown_assets=unavailable,unknown_correlations_filled=False,
                     warnings=['between_clusters_may_still_have_high_correlation',
                               'correlation_groups_are_not_underlying_holdings_overlap'])
    return ClusterResult(memberships,pd.DataFrame(merges,columns=[
        'left_members','right_members','maximum_distance','minimum_correlation','size']),
        diagnostics,fingerprint)
