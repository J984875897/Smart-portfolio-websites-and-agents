"""The acceptance auditor independently checks the claimed monthly coverage."""
import importlib.util
import io
import json
from pathlib import Path
import zipfile

import pytest
from portfolio.data.providers.base import RawResponse
from portfolio.data.reference_updates import run_reference_update


def test_auditor_rejects_success_with_missing_requested_month(tmp_path):
    spec = importlib.util.spec_from_file_location('reference_verification', Path(__file__).resolve().parents[1] / 'scripts/verify_reference_downloads.py')
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    body = io.BytesIO()
    with zipfile.ZipFile(body, 'w') as archive:
        archive.writestr('F-F_Research_Data_Factors.csv', ',Mkt-RF,SMB,HML,RF\n202501,2,3,4,.4\n202503,1,2,3,.3')
    run_id = run_reference_update(tmp_path, ['US_FF3'], '2025-01-01', '2025-04-01', fetch=lambda *a: RawResponse(body.getvalue(), 200))
    assert verifier.verify(tmp_path, run_id)['checks'][0]['status'] == 'partial'
    manifest_path = tmp_path / 'runs' / run_id / 'snapshot_manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    manifest['items'][0].update(status='success', reason='complete_requested_months', missing_months=[])
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(AssertionError, match='coverage'):
        verifier.verify(tmp_path, run_id)


def verifier_module():
    spec = importlib.util.spec_from_file_location('reference_verification', Path(__file__).resolve().parents[1] / 'scripts/verify_reference_downloads.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def hkma_page(records):
    return json.dumps({'header': {'success': True}, 'result': {'records': records}}).encode()


@pytest.mark.parametrize('rejected', [
    b'{', b'not JSON', b'\xff',
    hkma_page({}),
    json.dumps({'header': {'success': False}}).encode(),
    hkma_page([{'end_of_day': '2025-01-03', 'usd': 'bad'}]),
    hkma_page([{'end_of_day': 'bad', 'usd': 7.8}]),
])
@pytest.mark.parametrize('cancel_after_response', [False, True])
def test_auditor_checks_diagnostic_rows_after_rejected_page(tmp_path, rejected, cancel_after_response):
    calls = []
    def fetch(*args, **kwargs):
        calls.append(kwargs['offset'])
        return RawResponse(hkma_page([{'end_of_day': '2025-01-02', 'usd': 7.8}]) if len(calls) == 1 else rejected, 200)
    run_id = run_reference_update(
        tmp_path, ['HKMA_USDHKD'], '2025-01-01', '2025-02-01',
        page_size=1, fetch=fetch,
        cancelled=lambda: cancel_after_response and len(calls) == 2,
    )
    verifier = verifier_module()
    report = verifier.verify(tmp_path, run_id)
    item = report['checks'][0]
    assert (item['status'], item['reason']) == (('cancelled', 'cancelled') if cancel_after_response else ('unavailable', 'parse_error'))
    assert item['rows'] == 1 and len(item['raw_files']) == 2
    assert item['table_checked'] and item['numeric_cells_verified'] == 1
    assert not report['all_requested_sources_success']

    # A claimed success must never hide malformed evidence.
    manifest_path = tmp_path / 'runs' / run_id / 'snapshot_manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    manifest['items'][0].update(status='success', reason='complete_requested_months', pagination_complete=True)
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(AssertionError, match='HKMA'):
        verifier.verify(tmp_path, run_id)


def test_auditor_rejects_changed_diagnostic_value(tmp_path):
    import hashlib
    calls = []
    def fetch(*args, **kwargs):
        calls.append(1)
        return RawResponse(hkma_page([{'end_of_day': '2025-01-02', 'usd': 7.8}]) if len(calls) == 1 else b'{', 200)
    run_id = run_reference_update(tmp_path, ['HKMA_USDHKD'], '2025-01-01', '2025-02-01', page_size=1, fetch=fetch)
    manifest_path = tmp_path / 'runs' / run_id / 'snapshot_manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    table_path = manifest_path.parent / manifest['items'][0]['table_file']
    altered = table_path.read_bytes().replace(b'7.800000000000', b'7.900000000000')
    table_path.write_bytes(altered)
    for file in manifest['files']:
        if file['path'] == table_path.name:
            file.update(sha256=hashlib.sha256(altered).hexdigest(), bytes=len(altered))
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(AssertionError, match='HKMA value'):
        verifier_module().verify(tmp_path, run_id)


def test_auditor_propagates_raw_integrity_failure_after_initial_load(tmp_path, monkeypatch):
    calls = []
    def fetch(*args, **kwargs):
        calls.append(1)
        return RawResponse(hkma_page([{'end_of_day': '2025-01-02', 'usd': 7.8}]) if len(calls) == 1 else b'{', 200)
    run_id = run_reference_update(tmp_path, ['HKMA_USDHKD'], '2025-01-01', '2025-02-01', page_size=1, fetch=fetch)
    verifier = verifier_module()
    read_artifact = verifier.read_artifact
    def changed_raw(root, rid, path):
        if path.endswith('_raw_001.json'):
            raise ValueError('artifact integrity changed after load')
        return read_artifact(root, rid, path)
    monkeypatch.setattr(verifier, 'read_artifact', changed_raw)
    with pytest.raises(ValueError, match='integrity changed after load'):
        verifier.verify(tmp_path, run_id)
