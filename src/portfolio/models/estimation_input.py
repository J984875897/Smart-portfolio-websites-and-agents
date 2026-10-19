"""Bridge S05 qualification to S06 estimates without selecting holdings."""
from copy import deepcopy
from dataclasses import asdict

from portfolio.universe.screening import screen_candidates
from .moments import estimate_moments


def estimate_candidates(candidate, **screening_options):
    """Re-run S05 gates; a numerical estimate never upgrades source qualification."""
    screened=screen_candidates(candidate,**screening_options)
    if screened.cardinality.status != 'passed':
        raise ValueError('数量条件未通过：'+screened.cardinality.message)
    if len(screened.matrix) != 60:
        raise ValueError('正式估计需要完整60个月')
    classes=screened.audit.set_index('asset_id').loc[list(screened.eligible_asset_ids),'asset_class']
    result=estimate_moments(screened.matrix,classes,
                            train_start=screened.evidence['window_start'][:7],
                            train_end=screened.evidence['window_end'][:7])
    result.evidence=deepcopy(screened.evidence)
    result.evidence.update(screening_fingerprint=screened.fingerprint,
                           cardinality=asdict(screened.cardinality),screening_counts=deepcopy(screened.counts),
                           training_fingerprint=result.fingerprint)
    return result
