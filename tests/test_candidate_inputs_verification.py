import json
from pathlib import Path
import subprocess
import sys
import pandas as pd
from portfolio.universe.samples import sample_candidate_inputs


def test_acceptance_exports_synthetic_and_real_failure_separately(tmp_path):
    bundle, _, _, _ = sample_candidate_inputs()
    bundle.assets['frequency'] = 'daily'
    bundle.observations['frequency'] = 'daily'
    saved = tmp_path / 'daily_input'
    bundle.save(saved)
    out = tmp_path / 'audit'
    script = Path(__file__).resolve().parents[1] / 'scripts/verify_candidate_inputs.py'
    run = subprocess.run([sys.executable, str(script), '--output', str(out), '--real-bundle', str(saved)],
                         text=True, capture_output=True, timeout=40)
    assert run.returncode == 0, run.stdout + run.stderr
    summary = json.loads((out / 'summary.json').read_text())
    assert summary['synthetic']['matrix_shape'] == [60, 2]
    assert summary['real_daily_input']['matrix_shape'] == [60, 0]
    assert summary['source_files_unchanged'] is True
    matrix = pd.read_csv(out / 'synthetic/hkd_matrix.csv', index_col=0)
    assert matrix.shape == (60, 2)
    assert json.loads((out / 'synthetic/input_evidence.json').read_text())['historical_universe_certified'] is False
