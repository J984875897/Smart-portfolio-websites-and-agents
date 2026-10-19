"""Recompute candidate eligibility and moments before explicit-weight risk previews."""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json

from portfolio.models.estimation_input import estimate_candidates
from portfolio.models.moments import EstimateResult
from .correlation import CorrelationResult, pearson_correlation
from .diversification import RiskResult, portfolio_risk


@dataclass
class RiskPreview:
    estimate: EstimateResult
    correlation: CorrelationResult
    sample_risk: RiskResult
    model_risk: RiskResult
    evidence: dict
    fingerprint: str


def preview_candidate_risk(candidate, weights, **screening_options):
    estimate=estimate_candidates(candidate,**screening_options)
    correlation=pearson_correlation(candidate.matrix.loc[:,list(estimate.asset_ids)],
                                    train_start=estimate.diagnostics['train_start'],
                                    train_end=estimate.diagnostics['train_end'])
    mean=estimate.summary.estimated_mean_ann
    sample=portfolio_risk(mean,estimate.sample_cov_ann,weights,covariance_method='sample')
    model=portfolio_risk(mean,estimate.shrunk_cov_ann,weights,covariance_method='ledoit_wolf')
    payload=dict(screening=estimate.evidence['screening_fingerprint'],training=estimate.fingerprint,
                 correlation=correlation.fingerprint,sample_risk=sample.fingerprint,model_risk=model.fingerprint)
    fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True,allow_nan=False).encode()).hexdigest()
    evidence=deepcopy(estimate.evidence)
    evidence.update(preview_kind='specified_long_only_weights_not_selected_members',
                    target_k=evidence['cardinality']['k'],positive_weight_count=sample.metrics['positive_weight_count'],
                    weights=sample.contributions.weight.to_dict(),preview_fingerprint=fingerprint,
                    correlation_fingerprint=correlation.fingerprint,mean_basis='estimated_class_shrunk_arithmetic_annual',
                    portfolio_constructed=False)
    return RiskPreview(estimate,correlation,sample,model,evidence,fingerprint)
