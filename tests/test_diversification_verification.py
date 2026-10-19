"""Offline S06-B results remain inspectable and cannot overwrite source files."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'scripts/verify_diversification.py'


def run(*args):
    return subprocess.run([sys.executable,str(SCRIPT),*map(str,args)],capture_output=True,text=True,timeout=120)


def test_acceptance_hand_values_and_strict_json(tmp_path):
    out=tmp_path/'acceptance';r=run('--output',out)
    assert r.returncode == 0,r.stdout+r.stderr
    summary=json.loads((out/'summary.json').read_text())
    assert summary['real_n'] == 0 and summary['source_files_unchanged']
    assert summary['n99_blocked'] and summary['no_network']
    assert summary['historical_universe_certified'] is False
    assert summary['portfolio_constructed'] is False and summary['ui_implemented'] is False
    hand=pd.read_csv(out/'hand_calculation.csv').set_index('scenario')
    assert hand.loc['two_asset_diagonal','mean_ann'] == pytest.approx(.08)
    assert hand.loc['two_asset_diagonal','variance_ann'] == pytest.approx(.0325)
    assert hand.loc['twenty_identical','effective_holdings'] == pytest.approx(20)
    assert hand.loc['twenty_identical','diversification_ratio'] == pytest.approx(1)
    assert pd.isna(hand.loc['zero_volatility','diversification_ratio'])
    rho=pd.read_csv(out/'correlation.csv',index_col=0)
    assert rho.loc['A','NEG'] == pytest.approx(-1)
    assert rho['CONST'].isna().all()
    contrib=pd.read_csv(out/'risk_contributions.csv')
    selected=contrib.loc[contrib.scenario == 'two_asset_diagonal']
    assert selected.volatility_contribution_ann.sum() == pytest.approx(np.sqrt(.0325))
    assert contrib.loc[(contrib.scenario == 'negative_contribution') & (contrib.asset_id == 'B'),'risk_share'].iloc[0] < 0
    for path in out.glob('*.json'):
        def invalid(value): raise AssertionError(f'nonstandard JSON number {value} in {path}')
        json.loads(path.read_text(),parse_constant=invalid)
    matrix_json=json.loads((out/'correlation.json').read_text())
    const_idx=matrix_json['asset_ids'].index('CONST')
    assert all(row[const_idx] is None for row in matrix_json['values'])
    diagnostics=json.loads((out/'estimation_diagnostics.json').read_text())
    assert diagnostics['constant_preview']['sample']['risk_status'].startswith('unavailable')


@pytest.mark.parametrize('kind',['symlink','hardlink'])
def test_existing_output_alias_cannot_modify_source(tmp_path,kind):
    real=Path(json.loads((ROOT/'outputs/acceptance/S02/import_summary.json').read_text())['real_bundle_path'])
    source=tmp_path/'source';shutil.copytree(real,source)
    out=tmp_path/'out';out.mkdir()
    target=out/'correlation.csv';src=source/'factors.csv'
    if kind=='symlink':target.symlink_to(src)
    else:os.link(src,target)
    before=hashlib.sha256(src.read_bytes()).hexdigest()
    r=run('--real-bundle',source,'--output',out)
    assert r.returncode != 0 and 'output file alias' in r.stderr
    assert hashlib.sha256(src.read_bytes()).hexdigest() == before
    assert not (out/'summary.json').exists()


def test_overlapping_directories_rejected_before_loading_source(tmp_path):
    source=tmp_path/'source';source.mkdir()
    r=run('--real-bundle',source,'--output',source/'output')
    assert r.returncode != 0 and 'separate directories' in r.stderr
    assert not (source/'output').exists()
