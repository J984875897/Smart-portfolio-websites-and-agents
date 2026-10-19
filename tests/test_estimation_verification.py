"""Exercise the offline acceptance command and inspect its durable artifacts."""
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'scripts/verify_estimation.py'


def run(*args):
    return subprocess.run([sys.executable,str(SCRIPT),*map(str,args)],capture_output=True,text=True,timeout=90)


def test_offline_acceptance_outputs_are_independently_inspectable(tmp_path):
    out=tmp_path/'acceptance'; r=run('--output',out)
    assert r.returncode == 0,r.stdout+r.stderr
    hand=pd.read_csv(out/'hand_calculation.csv').set_index('asset_id')
    np.testing.assert_allclose(hand.estimated_mean_ann,[.30,.42,.12])
    np.testing.assert_allclose(hand.estimated_mean_ann,hand.expected_estimated_mean_ann)
    sample=pd.read_csv(out/'sample_covariance_month.csv',index_col=0)
    assert sample.loc['A','C'] == .00005
    diagnostics=json.loads((out/'estimation_diagnostics.json').read_text())
    assert diagnostics['high_dimensional']['sample_covariance']['rank'] <= 59
    assert diagnostics['high_dimensional']['shrunk_covariance']['min_eigenvalue'] > 0
    summary=json.loads((out/'summary.json').read_text())
    assert summary['no_network'] and summary['source_files_unchanged']
    assert summary['n99_blocked'] and summary['real_n'] == 0
    assert summary['synthetic_n100_degenerate'] and summary['nonconstant_n100_usable']
    assert summary['historical_universe_certified'] is False
    assert summary['portfolio_constructed'] is False
    assert len(pd.read_csv(out/'qualified_nonconstant_summary.csv')) == 100
    json.loads((out/'qualified_nonconstant_evidence.json').read_text())


def test_source_and_output_directories_cannot_overlap(tmp_path):
    source=tmp_path/'source';source.mkdir();sentinel=source/'keep.txt';sentinel.write_text('preserve')
    for out in [source,source/'child',tmp_path]:
        r=run('--real-bundle',source,'--output',out)
        assert r.returncode != 0
        assert 'separate directories' in r.stderr
        assert sentinel.read_text() == 'preserve'
    assert list(source.iterdir()) == [sentinel]


def test_file_aliases_cannot_overwrite_source_and_leave_false_success(tmp_path):
    import hashlib
    import os
    import shutil
    real=Path(json.loads((ROOT/'outputs/acceptance/S02/import_summary.json').read_text())['real_bundle_path'])
    source=tmp_path/'source';shutil.copytree(real,source)
    def hashes():
        return {str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest()
                for p in source.rglob('*') if p.is_file()}
    before=hashes()
    for kind in ['symlink','hardlink']:
        out=tmp_path/kind;out.mkdir()
        target=out/'hand_calculation.csv'
        if kind == 'symlink': target.symlink_to(source/'factors.csv')
        else: os.link(source/'factors.csv',target)
        r=run('--real-bundle',source,'--output',out)
        assert hashes() == before, r.stdout+r.stderr
        assert r.returncode != 0
        assert 'output file alias' in r.stderr
        assert not (out/'summary.json').exists()
        target.unlink()
