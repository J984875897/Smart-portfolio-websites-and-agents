"""Annual HKD moments and explicit long-only weights; no optimization or normalization."""
from dataclasses import dataclass
import hashlib
import json
from numbers import Real

import numpy as np
import pandas as pd
from portfolio.models.validation import covariance_diagnostics


@dataclass
class RiskResult:
    metrics: dict
    contributions: pd.DataFrame
    diagnostics: dict
    fingerprint: str


def _numeric(values, label):
    if any(isinstance(v,(bool,np.bool_)) or not isinstance(v,Real) for v in values.flat):
        raise ValueError(label+' must be real numeric values, not booleans')
    a=np.asarray(values,dtype=float)
    if not np.isfinite(a).all(): raise ValueError(label+' must be finite')
    return a


def portfolio_risk(mean_ann, covariance_ann, weights, *, covariance_method):
    if not isinstance(covariance_method,str) or covariance_method not in {'sample','ledoit_wolf','specified'}:
        raise ValueError('unknown covariance method')
    if (not isinstance(mean_ann,pd.Series) or mean_ann.empty or not mean_ann.index.is_unique
        or any(not isinstance(a,str) or not a.strip() or a != a.strip() for a in mean_ann.index)):
        raise ValueError('unique canonical asset IDs required')
    ids=sorted(mean_ann.index)
    if (not isinstance(weights,pd.Series) or not weights.index.is_unique or set(weights.index) != set(ids)):
        raise ValueError('weights must explicitly match all asset IDs')
    if (not isinstance(covariance_ann,pd.DataFrame) or not covariance_ann.index.is_unique
        or not covariance_ann.columns.is_unique or set(covariance_ann.index) != set(ids)
        or set(covariance_ann.columns) != set(ids)):
        raise ValueError('covariance row and column IDs must match')
    mu=_numeric(mean_ann.reindex(ids).to_numpy(),'mean')
    w=_numeric(weights.reindex(ids).to_numpy(),'weights')
    cov=_numeric(covariance_ann.loc[ids,ids].to_numpy(),'covariance')
    if (w < 0).any() or not np.isclose(w.sum(),1.,rtol=0,atol=1e-10):
        raise ValueError('long-only weights must be nonnegative and sum to one; not normalized')
    info=covariance_diagnostics(cov)
    if (np.diag(cov) < 0).any(): raise ValueError('negative asset variance')
    with np.errstate(over='ignore',invalid='ignore'):
        marginal_variance=cov@w
        variance=float(w@marginal_variance)
        mean=float(w@mu)
    if not np.isfinite(variance) or variance < 0 or not np.isfinite(mean):
        raise ValueError('invalid portfolio variance or return')
    sigma=float(np.sqrt(variance));asset_sigma=np.sqrt(np.diag(cov))
    marginal=np.full(len(ids),np.nan);contributions=marginal.copy();shares=marginal.copy()
    dr=None
    if sigma > 0:
        marginal=marginal_variance/sigma
        contributions=w*marginal
        shares=contributions/sigma
        dr=float((w@asset_sigma)/sigma)
        if not np.isfinite(np.r_[marginal,contributions,shares,dr]).all():
            raise ValueError('nonfinite portfolio risk indicators')
    metrics=dict(mean_ann=mean,variance_ann=variance,volatility_ann=sigma,
                 effective_holdings=float(1/(w@w)),diversification_ratio=dr,
                 positive_weight_count=int((w > 0).sum()),weight_sum=float(w.sum()))
    table=pd.DataFrame(dict(weight=w,asset_volatility_ann=asset_sigma,marginal_volatility_ann=marginal,
                            volatility_contribution_ann=contributions,risk_share=shares),index=ids)
    payload=dict(mean_ann=mu.tolist(),covariance_ann=cov.tolist(),weights=w.tolist(),asset_ids=ids,
                 covariance_method=covariance_method,base_currency='HKD',frequency='annual')
    fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True,allow_nan=False).encode()).hexdigest()
    diagnostics=dict(base_currency='HKD',frequency='annual',covariance_method=covariance_method,
                     covariance=info,risk_status='available' if sigma > 0 else 'unavailable_zero_portfolio_volatility',
                     weights_normalized=False,long_only=True,formal_portfolio=False,
                     weight_sum_tolerance=1e-10,contribution_sum=float(contributions.sum()) if sigma > 0 else None,
                     contribution_sum_error=float(contributions.sum()-sigma) if sigma > 0 else None,
                     warnings=['specified_weights_research_preview','effective_holdings_measures_weight_concentration_only',
                               'historical_risk_not_future_protection','input_moments_caller_declared_HKD_annual'])
    return RiskResult(metrics,table,diagnostics,fingerprint)
