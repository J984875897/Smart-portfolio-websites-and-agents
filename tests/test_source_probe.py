"""S01 boundary checks use synthetic provider responses and no network."""

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/source_responses"


@pytest.fixture
def probe():
    spec = importlib.util.spec_from_file_location("source_probe", ROOT / "scripts/probe_sources.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def chart():
    return json.loads((FIXTURES / "yahoo_chart.json").read_text())


def test_french_units_missing_and_annual_block(probe):
    table = probe.parse_french((FIXTURES / "french_monthly.csv").read_text())
    assert table["month"].tolist() == ["2025-01", "2025-02"]
    assert table.iloc[0]["Mkt-RF"] == pytest.approx(0.02)
    assert table.iloc[0]["RF"] == pytest.approx(0.004)
    assert np.isnan(table.iloc[1]["HML"])


@pytest.mark.parametrize("text", ["<html>rate limited</html>", ",Mkt-RF,SMB,HML,RF\n202513,1,2,3,4", ",Mkt-RF,SMB,HML,RF\n202501,1,2,3,4\n202501,1,2,3,4"])
def test_french_rejects_wrong_format_month_or_duplicates(probe, text):
    with pytest.raises(ValueError):
        probe.parse_french(text)


def test_hkma_direction_and_sort(probe):
    table = probe.parse_hkma(json.loads((FIXTURES / "hkma.json").read_text()))
    assert table["date"].tolist() == ["2025-01-02", "2025-01-03"]
    assert table["hkd_per_usd"].tolist() == [7.79, 7.80]


@pytest.mark.parametrize("payload", [{"header":{"success":False},"result":{"records":[]}}, {"header":{"success":True},"result":{"records":[{"end_of_day":"2025-01-01","usd":0}]}}, {"header":{"success":True},"result":{"records":[{"end_of_day":"2025-01-01"}]}}])
def test_hkma_rejects_error_missing_or_nonpositive_fx(probe, payload):
    with pytest.raises(ValueError):
        probe.parse_hkma(payload)


def test_yahoo_fields_actions_and_local_dates(probe, chart):
    table, meta = probe.parse_yahoo_chart(chart)
    assert meta["currency"] == "USD"
    assert table["date"].tolist() == ["2025-01-02", "2025-01-03", "2025-01-06"]
    assert table["close"].tolist() == [100,99,100]
    assert table["adj_close"].tolist() == [99,99,100]
    assert table["dividends"].tolist() == [0,1,0]
    assert table["stock_splits"].tolist() == [0,0,4]


def test_null_price_remains_missing_and_is_partial(probe, chart):
    chart["chart"]["result"][0]["indicators"]["quote"][0]["close"][1] = None
    table, meta = probe.parse_yahoo_chart(chart)
    assert np.isnan(table["close"].iloc[1])
    assert probe.audit_price(table, meta, "USD", "ETF")["status"] == "partial"


@pytest.mark.parametrize("currency,kind", [("HKD", "ETF"), ("USD", "EQUITY")])
def test_wrong_currency_or_instrument_is_not_success(probe, chart, currency, kind):
    table, meta = probe.parse_yahoo_chart(chart)
    assert probe.audit_price(table, meta, currency, kind)["status"] == "unavailable"


def test_missing_adjustment_not_substituted_with_close(probe, chart):
    del chart["chart"]["result"][0]["indicators"]["adjclose"]
    table, meta = probe.parse_yahoo_chart(chart)
    assert table["adj_close"].isna().all()
    assert probe.audit_price(table, meta, "USD", "ETF")["status"] == "partial"


def test_yahoo_error_and_inconsistent_lengths_rejected(probe, chart):
    with pytest.raises(ValueError):
        probe.parse_yahoo_chart({"chart":{"error":{"code":"Not Found"},"result":None}})
    broken = copy.deepcopy(chart)
    broken["chart"]["result"][0]["indicators"]["quote"][0]["close"].pop()
    with pytest.raises(ValueError):
        probe.parse_yahoo_chart(broken)


def test_corporate_action_does_not_resplit_adjusted_prices(probe, chart):
    table, _ = probe.parse_yahoo_chart(chart)
    rows = probe.action_diagnostics(table)
    dividend = rows.loc[rows["action"] == "dividend"].iloc[0]
    assert dividend["cash_reinvestment_return"] == pytest.approx(0)
    assert dividend["adjusted_return"] == pytest.approx(0)
    split = rows.loc[rows["action"] == "split"].iloc[0]
    assert split["close_return"] == pytest.approx(100/99-1)
    assert split["split_ratio"] == 4


def test_snapshot_integrity_detects_corruption(probe, tmp_path):
    manifest_path = tmp_path / "manifest.json"
    (tmp_path / "raw.json").write_bytes(b"data")
    entry = {"path":"raw.json", "sha256":probe.sha256(b"data"), "bytes":4}
    manifest_path.write_text(json.dumps({"schema_version":1,"files":[entry]}))
    assert probe.load_verified_manifest(manifest_path)["files"] == [entry]
    (tmp_path / "raw.json").write_bytes(b"oops")
    with pytest.raises(ValueError, match="SHA-256"):
        probe.load_verified_manifest(manifest_path)


def test_manifest_cannot_read_outside_snapshot(probe, tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"schema_version":1,"files":[{"path":"../secret", "sha256":"x","bytes":1}]}))
    with pytest.raises(ValueError, match="path"):
        probe.load_verified_manifest(manifest)


def test_gate_requires_real_price_fx_and_four_factor_sets(probe):
    rows = [{"kind":"product","status":"success"}, {"kind":"fx","status":"success","reason":"complete_requested_monthly_spot_preview"}]
    for dataset in probe.FACTOR_URLS:
        rows.append({"kind":"factor","dataset":dataset,"status":"success"})
    assert probe.assess_gate(rows)
    rows[-1]["status"] = "unavailable"
    assert not probe.assess_gate(rows)


def test_small_recent_hkma_sample_cannot_satisfy_historical_fx_gate(probe):
    rows = [{"kind":"product","status":"success"}, {"kind":"fx","status":"success","reason":"small_endpoint_sample_only"}]
    rows += [{"kind":"factor","dataset":d,"status":"success"} for d in probe.FACTOR_URLS]
    assert not probe.assess_gate(rows)


def test_wrong_symbol_is_not_success(probe, chart):
    table, meta = probe.parse_yahoo_chart(chart)
    assert probe.audit_price(table, meta, "USD", "ETF", symbol="OTHER")["status"] == "unavailable"


def test_french_missing_whole_month_rejected(probe):
    with pytest.raises(ValueError, match="month"):
        probe.parse_french(",Mkt-RF,SMB,HML,RF\n202501,1,2,3,4\n202503,1,2,3,4")


def test_monthly_spot_preview_uses_observation_dates_without_filling(probe):
    import pandas as pd
    table = pd.DataFrame({"date":["2025-01-30","2025-01-31","2025-02-28"],"close":[7.8,np.nan,7.9]})
    preview, audit = probe.monthly_spot_preview(table,"2025-01-01","2025-03-01")
    assert preview["observed_date"].tolist() == ["2025-01-30","2025-02-28"]
    assert preview["hkd_per_usd"].tolist() == [7.8,7.9]
    assert audit["status"] == "success"
    assert audit["invalid_daily_rows"] == 1
    assert table["close"].isna().sum() == 1
    _, incomplete = probe.monthly_spot_preview(table,"2024-12-01","2025-03-01")
    assert incomplete["status"] == "partial"
    assert incomplete["missing_months"] == 1


def test_stale_monthly_spot_is_not_success(probe):
    import pandas as pd
    table = pd.DataFrame({"date":["2025-01-10","2025-02-28"],"close":[7.8,7.9]})
    _, audit = probe.monthly_spot_preview(table,"2025-01-01","2025-03-01")
    assert audit["status"] == "partial"


def test_missing_requested_boundary_months_are_partial(probe, chart):
    table, meta = probe.parse_yahoo_chart(chart)
    assert probe.audit_price(table,meta,"USD","ETF",start="2024-12-01",end="2025-02-01")["status"] == "partial"


def test_missing_volume_is_partial(probe, chart):
    del chart["chart"]["result"][0]["indicators"]["quote"][0]["volume"]
    table, meta = probe.parse_yahoo_chart(chart)
    assert probe.audit_price(table,meta,"USD","ETF")["status"] == "partial"


def test_failed_replay_removes_old_derived_prices_but_keeps_user_files(probe, tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    (output / "AAPL_daily.csv").write_text("old price output")
    (output / "US_FF5_decimal.csv").write_text("old factor output")
    (output / "user_notes.txt").write_text("keep")
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    body = b'{"result":"unavailable"}'
    (snapshot / "error.json").write_bytes(body)
    manifest = {"schema_version":1,"run_id":"synthetic-failure","start":"2014-12-01","end_exclusive":"2026-01-01","attempts":[],"files":[{"path":"error.json","sha256":probe.sha256(body),"bytes":len(body),"role":"request_error","dataset":"AAPL"}]}
    path = snapshot / "snapshot_manifest.json"
    path.write_text(json.dumps(manifest))
    assert not probe.generate_reports(path,output)
    assert not (output / "AAPL_daily.csv").exists()
    assert not (output / "US_FF5_decimal.csv").exists()
    assert (output / "user_notes.txt").read_text() == "keep"
    derived = json.loads((output / "derived_manifest.json").read_text())
    assert derived["run_id"] == "synthetic-failure"
    assert "source_probe.csv" in [e["path"] for e in derived["files"]]


def test_corrupt_replay_does_not_change_existing_output(probe, tmp_path):
    output = tmp_path / "out"
    output.mkdir()
    (output / "source_probe.csv").write_text("unchanged")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"schema_version":1,"files":[{"path":"absent","sha256":"wrong","bytes":1}]}))
    with pytest.raises(OSError):
        probe.generate_reports(manifest,output)
    assert (output / "source_probe.csv").read_text() == "unchanged"


def test_replay_cli_cannot_call_online_downloader(probe, tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("offline replay attempted network downloader")
    monkeypatch.setattr(probe,"online_snapshot",forbidden)
    body = b'{"result":"unavailable"}'
    (tmp_path / "error.json").write_bytes(body)
    manifest = {"schema_version":1,"run_id":"synthetic-offline","start":"2014-12-01","end_exclusive":"2026-01-01","attempts":[],"files":[{"path":"error.json","sha256":probe.sha256(body),"bytes":len(body),"role":"request_error","dataset":"AAPL"}]}
    path = tmp_path / "snapshot_manifest.json"
    path.write_text(json.dumps(manifest))
    assert probe.main(["--replay",str(path),"--output",str(tmp_path / "out")]) == 1
    assert json.loads((tmp_path / "out/probe_summary.json").read_text())["run_id"] == "synthetic-offline"


@pytest.mark.parametrize("arguments", [["--sample-size","0"], ["--sample-size","7"], ["--start","2026-01-01","--end","2025-01-01"]])
def test_cli_rejects_invalid_scope_without_download(arguments):
    result = subprocess.run([sys.executable,str(ROOT / "scripts/probe_sources.py"),*arguments],capture_output=True,text=True)
    assert result.returncode == 2
    assert "usage:" in result.stderr
