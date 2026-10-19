"""Artificial source tables for the count boundary; not a real product universe."""
import pandas as pd
from .samples import sample_candidate_inputs


def sample_screening_inputs():
    bundle, fx, timing, structures = sample_candidate_inputs()
    assets = []; observations = []; times = []; classifications = []
    for i in range(100):
        aid = f'SYNTH_SCREEN_{i:03d}'
        a = bundle.assets.loc[bundle.assets.asset_id == 'HKD_COMPLETE'].copy()
        a['asset_id'] = aid; a['ticker'] = aid; a['name'] = f'人工权益 ETF {i+1:03d}'
        assets.append(a)
        for frame, destination in [(bundle.observations,observations),(timing,times),(structures,classifications)]:
            part = frame.loc[frame.asset_id == 'HKD_COMPLETE'].copy()
            part['asset_id'] = aid
            destination.append(part)
    bundle.assets = pd.concat(assets,ignore_index=True)
    bundle.observations = pd.concat(observations,ignore_index=True)
    return bundle, fx, pd.concat(times,ignore_index=True), pd.concat(classifications,ignore_index=True)
