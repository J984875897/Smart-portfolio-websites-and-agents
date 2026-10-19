"""Validate a complete HKD monthly training matrix without filling observations."""
from numbers import Real
import re

import numpy as np
import pandas as pd
from portfolio.data.quality import ASSET_CLASSES


def month(value):
    if not isinstance(value,str) or re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',value) is None:
        raise ValueError('training month must be YYYY-MM')
    try:
        return pd.Period(value,freq='M')
    except (ValueError,OverflowError) as exc:
        raise ValueError('invalid training month') from exc


def training_returns(returns, train_start, train_end):
    start,end=month(train_start),month(train_end)
    if end < start or end.ordinal-start.ordinal < 1:
        raise ValueError('training window requires at least two months')
    if not isinstance(returns,pd.DataFrame) or returns.shape[1] == 0 or not returns.columns.is_unique:
        raise ValueError('unique nonempty asset columns required')
    ids=list(returns.columns)
    if any(not isinstance(a,str) or not a.strip() or a != a.strip() for a in ids):
        raise ValueError('nonempty canonical asset IDs required')
    if any(not isinstance(d,str) or re.fullmatch(r'\d{4}-\d{2}-\d{2}',d) is None for d in returns.index):
        raise ValueError('monthly dates must be ISO date strings')
    try:
        dates=pd.to_datetime(returns.index,format='%Y-%m-%d',errors='raise')
    except (ValueError,TypeError,OverflowError) as exc:
        raise ValueError('invalid monthly dates') from exc
    periods=dates.to_period('M')
    mask=(periods >= start) & (periods <= end)
    x=returns.loc[mask,sorted(ids)].copy(deep=True).sort_index()
    expected=[p.end_time.date().isoformat() for p in pd.period_range(start,end,freq='M')]
    if list(x.index) != expected:
        raise ValueError('training data must have unique, continuous month-end dates')
    # Validate values only after slicing: future values and their induced dtype are irrelevant.
    if any(isinstance(v,(bool,np.bool_)) or not isinstance(v,Real) for v in x.to_numpy().flat):
        raise ValueError('training returns must be real numeric values, not booleans')
    values=x.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < -1).any():
        raise ValueError('training returns must be finite and at least -1')
    x=pd.DataFrame(values,index=expected,columns=sorted(ids))
    return x


def training_input(returns, asset_classes, train_start, train_end):
    x=training_returns(returns,train_start,train_end)
    if (not isinstance(asset_classes,pd.Series) or not asset_classes.index.is_unique
        or set(asset_classes.index) != set(x.columns)):
        raise ValueError('asset class binding must match unique asset IDs')
    if any(not isinstance(c,str) or c not in ASSET_CLASSES for c in asset_classes):
        raise ValueError('missing or unknown asset class')
    return x,asset_classes.reindex(x.columns).copy(deep=True)


def covariance_diagnostics(covariance):
    """Reject numerical failures, report singularity, and never repair matrices."""
    a=np.asarray(covariance,dtype=float)
    if a.ndim != 2 or a.shape[0] != a.shape[1] or not np.isfinite(a).all():
        raise ValueError('invalid covariance dimensions or finite values')
    scale=max(1.,float(np.linalg.norm(a,ord=2)))
    if not np.isfinite(scale):
        raise ValueError('nonfinite covariance spectral norm')
    tolerance=1e-12*scale
    if not np.allclose(a,a.T,atol=tolerance,rtol=0):
        raise ValueError('covariance must be symmetric')
    eig=np.linalg.eigvalsh(a)
    if not np.isfinite(eig).all():
        raise ValueError('nonfinite covariance eigenvalues')
    if eig[0] < -tolerance:
        raise ValueError('covariance is not positive semidefinite')
    rank=int(np.linalg.matrix_rank(a))
    return dict(rank=rank,min_eigenvalue=float(eig[0]),max_eigenvalue=float(eig[-1]),
                psd_tolerance=tolerance,positive_semidefinite=True,
                negative_eigenvalues_within_tolerance=int((eig < 0).sum()),
                condition_number=float(eig[-1]/eig[0]) if eig[0] > tolerance else None,
                singular=rank < len(a),matrix_repaired=False)
