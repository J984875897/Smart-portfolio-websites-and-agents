import json
from pathlib import Path
import subprocess
import sys
import pandas as pd


def test_offline_acceptance_exports(tmp_path):
    script = Path(__file__).resolve().parents[1] / 'scripts/verify_candidate_screening.py'
    run = subprocess.run([sys.executable,str(script),'--output',str(tmp_path/'acceptance')],capture_output=True,text=True)
    assert run.returncode == 0, run.stdout+run.stderr
    out = tmp_path/'acceptance'
    summary = json.loads((out/'summary.json').read_text())
    assert summary['synthetic_n100_status'] == 'passed'
    assert summary['synthetic_n99_status'] == 'pool_too_small'
    assert summary['real_n'] == 0
    assert summary['source_files_unchanged'] is True
    assert summary['no_network'] is True
    audit = pd.read_csv(out/'universe_audit.csv')
    assert len(audit) == 100 and audit.asset_id.str.startswith('SYNTH_SCREEN_').all()
    assert audit.status.eq('eligible').all()
    cases = pd.read_csv(out/'cardinality_cases.csv')
    assert len(cases) == 17
    assert json.loads((out/'synthetic_evidence.json').read_text())['historical_universe_certified'] is False
    assert (out/'real_universe_audit.csv').is_file()
