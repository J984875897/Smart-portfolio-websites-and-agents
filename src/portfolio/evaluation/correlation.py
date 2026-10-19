"""Pearson correlations over a complete, explicitly bounded HKD monthly sample."""
from dataclasses import dataclass
import hashlib
import json

import numpy as np
import pandas as pd
from portfolio.models.validation import training_returns


@dataclass
class CorrelationResult:
    matrix: pd.DataFrame
    asset_status: pd.DataFrame
    diagnostics: dict
    fingerprint: str


def pearson_correlation(returns, *, train_start, train_end):
    x=training_returns(returns,train_start,train_end)
    values=x.to_numpy(); ids=list(x.columns)
    relative=values-values[0]
    centered=relative-relative.mean(axis=0)
    if not np.isfinite(centered).all():
        raise ValueError('nonfinite centered training returns')
    constant=np.all(values == values[0],axis=0)
    valid=np.flatnonzero(~constant)
    matrix=np.full((len(ids),len(ids)),np.nan)
    clipped=0
    if len(valid):
        z=centered[:,valid]
        z=z/np.max(np.abs(z),axis=0)
        unit=z/np.sqrt(np.square(z).sum(axis=0))
        rho=unit.T@unit
        if not np.isfinite(rho).all() or (np.abs(rho) > 1+1e-12).any():
            raise ValueError('invalid Pearson calculation')
        clipped=int((np.abs(rho) > 1).sum())
        rho=np.clip(rho,-1,1)
        np.fill_diagonal(rho,1.)
        matrix[np.ix_(valid,valid)]=rho
    payload=dict(training_returns=x.to_csv(),train_start=train_start,train_end=train_end,
                 method='raw_training_Pearson',base_currency='HKD')
    fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True,allow_nan=False).encode()).hexdigest()
    constants=[aid for aid,flag in zip(ids,constant) if flag]
    status=pd.DataFrame({'status':['unavailable_constant' if flag else 'available' for flag in constant],
                         'reason':['constant_series_correlation_undefined' if flag else 'ok' for flag in constant]},index=ids)
    diagnostics=dict(method='raw_training_Pearson',base_currency='HKD',frequency='monthly',
                     train_start=train_start,train_end=train_end,n_observations=len(x),n_assets=len(ids),
                     constant_assets=constants,available_pairs=len(valid)*(len(valid)-1)//2,
                     pair_count_basis='distinct_unordered_pairs_excluding_diagonal',
                     roundoff_clipped_entries=clipped,missing_values_filled=False,
                     fingerprint=fingerprint,warnings=['historical_correlation_not_future_protection',
                                                       'constant_series_not_risk_free'])
    return CorrelationResult(pd.DataFrame(matrix,index=ids,columns=ids),status,diagnostics,fingerprint)
