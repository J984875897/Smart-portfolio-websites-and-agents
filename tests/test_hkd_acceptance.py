"""The offline command must produce independently checkable research evidence."""
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_offline_hkd_evidence_command(tmp_path):
    script = ROOT / 'scripts/verify_hkd.py'
    assert script.exists(), 'The S03A offline evidence command is not implemented'
    completed = subprocess.run(
        [sys.executable, str(script), '--output', str(tmp_path / 'evidence')],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    folder = tmp_path / 'evidence'
    result = pd.read_csv(folder / 'hkd_reconciliation.csv')
    indexed = result.set_index('asset_id')
    assert indexed.loc['SYNTH_USD', 'hkd_return'] == pytest.approx(0.02294871794871795)
    assert indexed.loc['SYNTH_HKD', 'hkd_return'] == pytest.approx(0.01)
    assert indexed.loc['SYNTH_ZERO', 'hkd_return'] == pytest.approx(0.01282051282051282)
    assert indexed.loc['SYNTH_LOSS', 'hkd_return'] == pytest.approx(-1.0)
    adjusted = indexed.loc['SYNTH_ADJ']
    assert adjusted.loc[adjusted['date'].eq('2025-01-31'), 'hkd_return'].iloc[0] == pytest.approx(0.02294871794871795)
    failures = pd.read_csv(folder / 'failure_cases.csv')
    foreign_missing = failures[failures['case'].eq('missing_fx') & failures['asset_id'].eq('SYNTH_USD')]
    assert foreign_missing['hkd_return'].isna().all()
    assert foreign_missing['status'].ne('valid').all()
    summary = json.loads((folder / 'summary.json').read_text())
    assert summary['synthetic'] is True
    assert summary['time_alignment_verified'] is False
    assert summary['qualified_candidate_count_computed'] is False
    assert len(summary['input_hashes']) == 4
    assert all(len(value) == 64 for value in summary['input_hashes'].values())
