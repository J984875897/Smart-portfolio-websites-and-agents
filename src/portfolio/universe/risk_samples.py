"""Deterministic artificial monthly source data; never market performance."""
import numpy as np
from .screening_samples import sample_screening_inputs


def sample_risk_inputs():
    bundle,fx,timing,structures=sample_screening_inputs()
    rng=np.random.default_rng(5052)
    ids=sorted(bundle.assets.asset_id)
    n_months=int((bundle.observations.asset_id == ids[0]).sum())
    values=rng.normal(.005,.04,(n_months,len(ids)))
    values[:,0]=.01
    values[:,2]=values[:,1]
    values[:,3]=-values[:,1]
    for i,aid in enumerate(ids):
        rows=bundle.observations.loc[bundle.observations.asset_id == aid].sort_values('date').index
        bundle.observations.loc[rows,'value']=values[:,i]
    bundle.assets['name']=[f'人工风险 ETF {i+1:03d}' for i in range(len(ids))]
    return bundle,fx,timing,structures
