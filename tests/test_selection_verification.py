"""S07-A evidence is inspectable, strict JSON and separate from source bundles."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pandas as pd
import pytest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'scripts/verify_selection.py'


def run(*args):
    return subprocess.run([sys.executable,str(SCRIPT),*map(str,args)],capture_output=True,text=True,timeout=120)


def test_acceptance_files_and_blocked_real_input(tmp_path):
    out=tmp_path/'out';result=run('--output',out)
    assert result.returncode == 0,result.stdout+result.stderr
    summary=json.loads((out/'summary.json').read_text())
    assert summary['stage'] == 'S07-A'
    assert summary['synthetic_n'] == 100 and summary['selected_count'] == 30
    assert summary['n99_blocked'] and summary['real_n'] == 0
    assert summary['source_files_unchanged'] and summary['no_network']
    assert not summary['portfolio_constructed'] and not summary['ui_implemented']
    reasons=pd.read_csv(out/'selection_reasons.csv')
    assert reasons.selected.sum() == 30 and reasons.asset_id.is_unique
    assert len(pd.read_csv(out/'candidate_alternatives.csv')) == 70
    rho=pd.read_csv(out/'selected_correlation.csv',index_col=0)
    assert rho.shape == (30,30)
    assert len(pd.read_csv(out/'identical_high_correlation_pairs.csv')) == 435
    hand=pd.read_csv(out/'hand_cluster_memberships.csv').set_index('asset_id')
    assert hand.loc['A','cluster_id'] == hand.loc['B','cluster_id']
    assert hand.loc['A','cluster_id'] != hand.loc['C','cluster_id']
    assert hand.loc['NEG','cluster_id'] != hand.loc['A','cluster_id']
    assert hand.loc['CONST','correlation_status'] == 'unavailable'
    for path in out.glob('*.json'):
        def invalid(value): raise AssertionError('nonstandard JSON number '+value)
        json.loads(path.read_text(),parse_constant=invalid)


@pytest.mark.parametrize('kind',['symlink','hardlink'])
def test_output_alias_does_not_change_source(tmp_path,kind):
    real=Path(json.loads((ROOT/'outputs/acceptance/S02/import_summary.json').read_text())['real_bundle_path'])
    source=tmp_path/'source';shutil.copytree(real,source)
    out=tmp_path/'out';out.mkdir()
    src=source/'factors.csv';target=out/'selection_reasons.csv'
    if kind == 'symlink': target.symlink_to(src)
    else: os.link(src,target)
    before=hashlib.sha256(src.read_bytes()).hexdigest()
    result=run('--real-bundle',source,'--output',out)
    assert result.returncode != 0 and 'output file alias' in result.stderr
    assert hashlib.sha256(src.read_bytes()).hexdigest() == before
    assert not (out/'summary.json').exists()


def test_source_and_output_cannot_overlap(tmp_path):
    source=tmp_path/'source';source.mkdir()
    result=run('--real-bundle',source,'--output',source/'out')
    assert result.returncode != 0 and 'separate directories' in result.stderr
    assert not (source/'out').exists()
