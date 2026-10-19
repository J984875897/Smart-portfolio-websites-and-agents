"""HKD monthly arithmetic estimates using only an explicitly bounded training sample."""
from dataclasses import dataclass, field
import hashlib
import json

import numpy as np
import pandas as pd
import sklearn
from sklearn.covariance import LedoitWolf
from .validation import training_input, covariance_diagnostics


@dataclass
class EstimateResult:
    asset_ids: tuple
    summary: pd.DataFrame
    sample_cov_month: pd.DataFrame
    sample_cov_ann: pd.DataFrame
    shrunk_cov_month: pd.DataFrame
    shrunk_cov_ann: pd.DataFrame
    diagnostics: dict
    fingerprint: str
    evidence: dict = field(default_factory=dict)


def estimate_moments(returns, asset_classes, *, train_start, train_end):
    """Caller supplies HKD decimal total returns; this does not certify their sources."""
    x,classes=training_input(returns,asset_classes,train_start,train_end)
    ids=tuple(x.columns); values=x.to_numpy(); n,p=values.shape
    historical=x.mean()
    category=historical.groupby(classes).transform('mean')
    sizes=classes.groupby(classes).transform('size')
    estimated=.5*historical+.5*category
    # Difference first: identical decimal observations center to exactly zero.
    relative=values-values[0]
    centered=relative-relative.mean(axis=0)
    constant=np.all(values == values[0],axis=0)
    with np.errstate(over='ignore',invalid='ignore'):
        sample=centered.T @ centered/(n-1)
    sample_info=covariance_diagnostics(sample)
    lw=LedoitWolf(store_precision=False,assume_centered=False).fit(centered)
    shrunk=np.atleast_2d(lw.covariance_)
    shrunk_info=covariance_diagnostics(shrunk)
    # Check annual scaling too, including finite results, rather than trusting monthly checks.
    covariance_diagnostics(12*sample); covariance_diagnostics(12*shrunk)
    summary=pd.DataFrame(dict(asset_class=classes,class_members=sizes,
                              historical_mean_month=historical,class_mean_month=category,
                              estimated_mean_month=estimated,historical_mean_ann=12*historical,
                              estimated_mean_ann=12*estimated,sample_vol_ann=np.sqrt(12*np.diag(sample)),
                              shrunk_vol_ann=np.sqrt(12*np.diag(shrunk)),is_constant=constant))
    if not np.isfinite(summary.select_dtypes(include='number').to_numpy()).all():
        raise ValueError('nonfinite estimated return statistics')
    payload=dict(training_returns=x.to_csv(index=True),asset_classes=classes.to_dict(),
                 train_start=train_start,train_end=train_end,base_currency='HKD',
                 individual_mean_weight=.5,annualization=12,covariance_method='LedoitWolf',
                 estimator_version=sklearn.__version__)
    fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True,allow_nan=False).encode()).hexdigest()
    warnings=['arithmetic_annualization_assumes_monthly_scaling','historical_estimates_not_forecasts',
              'source_currency_and_total_return_basis_caller_declared']
    constants=[aid for aid,flag in zip(ids,constant) if flag]
    if constants: warnings.append('constant_series_not_risk_free')
    if any(shrunk[i,i] > 0 for i in np.flatnonzero(constant)):
        warnings.append('constant_series_model_variance')
    if sample_info['singular']: warnings.append('sample_covariance_singular')
    if shrunk_info['singular']: warnings.append('shrunk_covariance_singular')
    if bool(constant.all()): warnings.append('all_series_constant')
    singletons=sorted(classes.value_counts().loc[lambda s:s == 1].index.tolist())
    if singletons: warnings.append('singleton_class_shrinkage_adds_no_information')
    diagnostics=dict(base_currency='HKD',frequency='monthly',return_unit='decimal',
                     return_basis='caller_declared_total_return',train_start=train_start,train_end=train_end,
                     first_observation=x.index[0],last_observation=x.index[-1],n_observations=n,n_assets=p,
                     mean_method='0.5_individual_plus_0.5_equal_weight_class_including_self',
                     sample_covariance_ddof=1,shrinkage_empirical_ddof=0,
                     covariance_method='LedoitWolf',estimator_version=sklearn.__version__,
                     shrinkage_coefficient=float(lw.shrinkage_),
                     shrinkage_target='mean_empirical_variance_times_identity',
                     shrinkage_target_variance_month=float(np.square(centered).sum()/(n*p)),
                     annualization_factor=12,sample_covariance=sample_info,shrunk_covariance=shrunk_info,
                     constant_assets=constants,singleton_classes=singletons,
                     usable_for_optimization=not bool(constant.all()) and not shrunk_info['singular'],
                     usability_scope='numerical_only_not_portfolio_or_data_qualification',
                     warnings=warnings,training_fingerprint=fingerprint)
    def frame(a): return pd.DataFrame(a,index=ids,columns=ids)
    return EstimateResult(ids,summary,frame(sample),frame(12*sample),frame(shrunk),frame(12*shrunk),
                          diagnostics,fingerprint)
