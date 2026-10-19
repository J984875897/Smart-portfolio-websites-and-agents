"""S01 only: six product probes, public FX/factors, and verified offline replay.

This is a feasibility tool, not the S04 downloader or an investment universe.
No API keys are accepted. Authentication responses/headers are never recorded.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import sys
import uuid
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
# Support direct CLI execution as well as installed-package imports.
sys.path.insert(0, str(ROOT / "src"))
HKMA_URL = "https://api.hkma.gov.hk/public/market-data-and-statistics/monthly-statistical-bulletin/er-ir/er-eeri-daily"
FRENCH_BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FACTOR_URLS = {
    "US_FF3": FRENCH_BASE + "F-F_Research_Data_Factors_CSV.zip",
    "US_FF5": FRENCH_BASE + "F-F_Research_Data_5_Factors_2x3_CSV.zip",
    "AP_EX_JP_FF3": FRENCH_BASE + "Asia_Pacific_ex_Japan_3_Factors_CSV.zip",
    "AP_EX_JP_FF5": FRENCH_BASE + "Asia_Pacific_ex_Japan_5_Factors_CSV.zip",
}
SAMPLES = [
    {"symbol":"AAPL", "name":"Apple", "sample_category":"US stock", "tool_type":"individual_stock", "economic_exposure":"US equity", "market":"US", "currency":"USD", "provider_type":"EQUITY", "inception_or_listing":"1980-12-12", "date_kind":"IPO", "reference":"https://investor.apple.com/faq./default.aspx"},
    {"symbol":"0700.HK", "name":"Tencent", "sample_category":"HK stock", "tool_type":"individual_stock", "economic_exposure":"China/HK equity", "market":"HK", "currency":"HKD", "provider_type":"EQUITY", "inception_or_listing":"2004-06-16", "date_kind":"listing", "reference":"https://www.tencent.com/en-us/articles/1600069.html"},
    {"symbol":"SPY", "name":"SPDR S&P 500 ETF Trust", "sample_category":"US equity ETF", "tool_type":"equity_etf", "economic_exposure":"US equity", "market":"US", "currency":"USD", "provider_type":"ETF", "inception_or_listing":"1993-01-22", "date_kind":"fund inception", "reference":"https://www.ssga.com/us/en/institutional/etfs/state-street-spdr-sp-500-etf-trust-spy"},
    {"symbol":"2800.HK", "name":"Tracker Fund of Hong Kong", "sample_category":"HK equity ETF", "tool_type":"equity_etf", "economic_exposure":"Hang Seng equity (incl. China)", "market":"HK", "currency":"HKD", "provider_type":"ETF", "inception_or_listing":"1999-11-12", "date_kind":"listing; fund launched 1999-11", "reference":"https://www.hkex.com.hk/News/News-Release/1999-SEHK/991112news?sc_lang=en"},
    {"symbol":"AGG", "name":"iShares Core US Aggregate Bond ETF", "sample_category":"bond ETF", "tool_type":"bond_etf", "economic_exposure":"US investment grade bonds", "market":"US", "currency":"USD", "provider_type":"ETF", "inception_or_listing":"2003-09-22", "date_kind":"fund inception", "reference":"https://www.ishares.com/us/products/239458/ishares-core-total-us-bond-market-etf"},
    {"symbol":"GLD", "name":"SPDR Gold Shares", "sample_category":"gold product", "tool_type":"gold_trust", "economic_exposure":"physical gold", "market":"US", "currency":"USD", "provider_type":"ETF", "inception_or_listing":"2004-11-18", "date_kind":"trust inception", "reference":"https://www.ssga.com/us/en/individual/etfs/spdr-gold-shares-gld"},
]


def sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


from portfolio.data.providers.french import parse_french
from portfolio.data.providers.hkma import parse_hkma

from portfolio.data.providers.yahoo import parse_yahoo_chart, audit_price


def monthly_spot_preview(table: pd.DataFrame, start: str, end: str) -> tuple[pd.DataFrame, dict]:
    """Evidence of monthly FX availability; no daily fill or valuation alignment.

    Seven calendar days is a probe staleness limit, not the S03 FX convention.
    The actual observation date is always retained, including holidays/gaps.
    """
    source = table.loc[(table["date"] >= start) & (table["date"] < end), ["date","close"]].copy()
    valid = np.isfinite(source["close"]) & (source["close"] > 0)
    selected = source.loc[valid].sort_values("date")
    selected["month"] = pd.to_datetime(selected["date"]).dt.to_period("M").astype(str)
    selected = selected.groupby("month",sort=True).tail(1).rename(columns={"date":"observed_date","close":"hkd_per_usd"})
    month_end = pd.PeriodIndex(selected["month"],freq="M").to_timestamp(how="end").normalize()
    selected["calendar_month_end"] = month_end.strftime("%Y-%m-%d")
    selected["days_before_calendar_end"] = (month_end-pd.DatetimeIndex(selected["observed_date"])).days
    selected = selected[["month","observed_date","calendar_month_end","hkd_per_usd","days_before_calendar_end"]].reset_index(drop=True)
    expected = pd.period_range(pd.Period(start,freq="M"),pd.Period(pd.Timestamp(end)-pd.Timedelta(days=1),freq="M"),freq="M")
    missing = len(expected.difference(pd.PeriodIndex(selected["month"],freq="M")))
    stale = int((selected["days_before_calendar_end"] > 7).sum())
    passed = not missing and not stale and len(expected) > 1
    return selected, {"status":"success" if passed else "partial","reason":"complete_requested_monthly_spot_preview" if passed else "missing_or_stale_monthly_spot","rows":len(selected),"first_date":selected["month"].min() if len(selected) else "","last_date":selected["month"].max() if len(selected) else "","missing_months":missing,"stale_months":stale,"invalid_daily_rows":int((~valid).sum()),"max_observation_age_days":int(selected["days_before_calendar_end"].max()) if len(selected) else None,"quality_scope":"S01 availability preview; S03 alignment pending"}


def action_diagnostics(table: pd.DataFrame) -> pd.DataFrame:
    """Compare provider adjustments; no second split or extra dividend added."""
    rows = []
    for i in range(1, len(table)):
        current, previous = table.iloc[i], table.iloc[i-1]
        for action in ("dividend", "split"):
            if current["dividends" if action == "dividend" else "stock_splits"] == 0:
                continue
            close_return = current["close"] / previous["close"] - 1
            adjusted_return = current["adj_close"] / previous["adj_close"] - 1
            cash_return = (current["close"] + current["dividends"] + current["capital_gains"]) / previous["close"] - 1
            rows.append({"date":current["date"], "previous_date":previous["date"], "action":action, "previous_close":previous["close"], "close":current["close"], "previous_adj_close":previous["adj_close"], "adj_close":current["adj_close"], "dividend":current["dividends"], "split_ratio":current["stock_splits"], "close_return":close_return, "cash_reinvestment_return":cash_return, "adjusted_return":adjusted_return, "difference":adjusted_return-cash_return})
    return pd.DataFrame(rows)


def load_verified_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text())
    if manifest.get("schema_version") != 1 or not manifest.get("files"):
        raise ValueError("Unsupported/empty snapshot manifest")
    base = path.resolve().parent
    for entry in manifest["files"]:
        target = (base / entry["path"]).resolve()
        if not target.is_relative_to(base):
            raise ValueError("Snapshot path escapes its directory")
        body = target.read_bytes()
        if sha256(body) != entry["sha256"] or len(body) != entry["bytes"]:
            raise ValueError("Snapshot SHA-256/size mismatch: " + entry["path"])
    return manifest


def assess_gate(rows: list[dict]) -> bool:
    product = any(r["kind"] == "product" and r["status"] == "success" for r in rows)
    fx = any(r["kind"] == "fx" and r["status"] == "success" and r.get("reason") == "complete_requested_monthly_spot_preview" for r in rows)
    factors = {r.get("dataset") for r in rows if r["kind"] == "factor" and r["status"] == "success"}
    return product and fx and set(FACTOR_URLS).issubset(factors)


def online_snapshot(output: Path, start: str, end: str, timeout: float) -> Path:
    # Import yfinance first: its supported network stack handles platform setup.
    import requests
    import yfinance as yf
    from yfinance.data import YfData

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    folder = output / "snapshots" / stamp
    folder.mkdir(parents=True, exist_ok=False)
    manifest = {"schema_version":1, "run_id":stamp, "created_utc":datetime.now(timezone.utc).isoformat(), "start":start, "end_exclusive":end, "yfinance_version":yf.__version__, "files":[], "attempts":[]}

    def save(body, name, **metadata):
        with (folder / name).open("xb") as handle:
            handle.write(body)
        manifest["files"].append({"path":name, "sha256":sha256(body), "bytes":len(body), **metadata})

    yf.set_tz_cache_location(str(folder / "private_yfinance_cache"))
    # Capture only public chart bodies. Cookie/crumb endpoints are excluded.
    session = YfData()._session
    original_get = session.get
    chart_count = 0

    def captured_get(*args, **kwargs):
        nonlocal chart_count
        response = original_get(*args, **kwargs)
        url = kwargs.get("url", args[0] if args else "")
        parts = urlsplit(url)
        if parts.path.startswith("/v8/finance/chart/"):
            chart_count += 1
            symbol = parts.path.rsplit("/", 1)[-1]
            params = {k:v for k,v in (kwargs.get("params") or {}).items() if k in ("period1", "period2", "range", "interval", "events", "includePrePost")}
            save(response.content, f"yahoo_{chart_count:02d}.json", role="yahoo_chart", dataset=symbol, url=parts.scheme+"://"+parts.netloc+parts.path, parameters=params, http_status=response.status_code, retrieved_utc=datetime.now(timezone.utc).isoformat())
        return response

    session.get = captured_get
    try:
        for symbol in [s["symbol"] for s in SAMPLES] + ["HKD=X"]:
            print("Probing Yahoo:", symbol, flush=True)
            try:
                ticker = yf.Ticker(symbol, session=session)
                history = ticker.history(start=start, end=end, interval="1d", auto_adjust=False, back_adjust=False, actions=True, repair=False, keepna=True, rounding=False, timeout=timeout)
                if history.empty:
                    raise ValueError("Empty history")
                frame = history.reset_index()
                frame["Date"] = frame["Date"].astype(str)
                save(frame.to_csv(index=False, float_format="%.12f").encode(), f"yfinance_{symbol.replace('=','_')}.csv", role="yfinance_history", dataset=symbol)
                manifest["attempts"].append({"dataset":symbol, "result":"returned", "rows":len(history)})
            except Exception as error:
                # Do not log exception text: provider errors may include auth URLs.
                manifest["attempts"].append({"dataset":symbol, "result":"unavailable", "error_type":type(error).__name__})
    finally:
        session.get = original_get

    for dataset, url in [("HKMA_USDHKD", HKMA_URL), *FACTOR_URLS.items()]:
        print("Probing public endpoint:", dataset, flush=True)
        params = {"pagesize":8} if dataset == "HKMA_USDHKD" else {}
        try:
            response = requests.get(url, params=params, timeout=timeout)
            name = dataset + (".json" if dataset == "HKMA_USDHKD" else ".zip")
            save(response.content, name, role="hkma_json" if dataset == "HKMA_USDHKD" else "french_zip", dataset=dataset, url=url, parameters=params, http_status=response.status_code, retrieved_utc=datetime.now(timezone.utc).isoformat())
            response.raise_for_status()
            if dataset in FACTOR_URLS:
                with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                    members = [n for n in archive.namelist() if n.lower().endswith(".csv")]
                    if len(members) != 1:
                        raise ValueError("Unexpected French ZIP members")
                    save(archive.read(members[0]), dataset+".csv", role="french_text", dataset=dataset, zip_member=members[0])
            manifest["attempts"].append({"dataset":dataset, "result":"returned"})
        except Exception as error:
            entry = {"dataset":dataset, "result":"unavailable", "error_type":type(error).__name__}
            manifest["attempts"].append(entry)
            save(json.dumps(entry, indent=2).encode(), dataset+"_error.json", role="request_error", dataset=dataset, url=url, parameters=params)

    manifest_path = folder / "snapshot_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+"\n")
    # This cache can contain authentication state; never include it in evidence.
    import shutil
    shutil.rmtree(folder / "private_yfinance_cache", ignore_errors=True)
    return manifest_path


def generate_reports(manifest_path: Path, output: Path) -> bool:
    manifest = load_verified_manifest(manifest_path)
    output.mkdir(parents=True, exist_ok=True)
    import tempfile
    # Build before publishing; a corrupt snapshot leaves previous evidence intact.
    with tempfile.TemporaryDirectory(prefix=".s01-preview-",dir=output) as temporary:
        stage = Path(temporary)
        gate = _build_reports(manifest_path,manifest,stage)
        artifacts = [{"path":p.name,"sha256":sha256(p.read_bytes()),"bytes":p.stat().st_size} for p in sorted(stage.iterdir())]
        (stage / "derived_manifest.json").write_text(json.dumps({"schema_version":1,"run_id":manifest["run_id"],"source_manifest_sha256":sha256(manifest_path.read_bytes()),"files":artifacts},indent=2)+"\n")
        # Only these tool-owned exports are replaced; notes/checks/raw snapshots stay.
        owned = {s["symbol"]+"_daily.csv" for s in SAMPLES}
        owned |= {d+"_decimal.csv" for d in FACTOR_URLS}
        owned |= {"HKD_X_daily.csv","HKMA_USDHKD.csv","USDHKD_monthly_spot_preview.csv","corporate_actions.csv","source_probe.csv","provider_metadata.json","probe_summary.json","feasibility.md","derived_manifest.json"}
        new_names = {p.name for p in stage.iterdir()}
        for name in owned-new_names:
            (output / name).unlink(missing_ok=True)
        for artifact in stage.iterdir():
            artifact.replace(output / artifact.name)
    return gate


def _build_reports(manifest_path: Path, manifest: dict, output: Path) -> bool:
    base = manifest_path.parent
    prices, metadata, rows = {}, {}, []
    files = manifest["files"]
    for sample in [*SAMPLES, {"symbol":"HKD=X", "currency":"HKD", "provider_type":"CURRENCY"}]:
        symbol = sample["symbol"]
        candidates = []
        for entry in files:
            if entry.get("role") != "yahoo_chart" or entry.get("dataset") != symbol or entry.get("http_status") != 200:
                continue
            try:
                table, meta = parse_yahoo_chart(json.loads((base / entry["path"]).read_bytes()))
                table = table.loc[(table["date"] >= manifest["start"]) & (table["date"] < manifest["end_exclusive"])].reset_index(drop=True)
                candidates.append((len(table), table, meta, entry))
            except (ValueError, KeyError, TypeError, IndexError):
                continue
        row = {"kind":"fx" if symbol == "HKD=X" else "product", "dataset":symbol, **sample, "status":"unavailable", "reason":"no_valid_chart_response", "import_alternative":"CSV/XLSX with currency, product type, total-return convention and source"}
        if candidates:
            _, table, meta, entry = max(candidates, key=lambda item:item[0])
            row.update(audit_price(table, meta, sample["currency"], sample["provider_type"],symbol=symbol,start=manifest["start"],end=manifest["end_exclusive"]))
            row.update({"raw_path":entry["path"], "raw_sha256":entry["sha256"], "provider_currency":meta.get("currency"), "provider_instrument":meta.get("instrumentType"), "provider_first_trade_date":pd.Timestamp(meta["firstTradeDate"],unit="s",tz="UTC").tz_convert(meta["exchangeTimezoneName"]).strftime("%Y-%m-%d") if meta.get("firstTradeDate") else "unknown", "fields":"|".join(table.columns)})
            table.to_csv(output / (symbol.replace("=", "_")+"_daily.csv"), index=False, float_format="%.12f")
            prices[symbol], metadata[symbol] = table, meta
            history_files = [e for e in files if e.get("role") == "yfinance_history" and e.get("dataset") == symbol]
            if history_files:
                history = pd.read_csv(base / history_files[0]["path"])
                history_dates = pd.to_datetime(history["Date"],utc=True).dt.tz_convert(meta["exchangeTimezoneName"]).dt.strftime("%Y-%m-%d")
                matched = table.merge(history.assign(date=history_dates), on="date", how="inner")
                agrees = len(matched) == len(table) == len(history) and np.allclose(matched["close"],matched["Close"],equal_nan=True) and (symbol == "HKD=X" or np.allclose(matched["adj_close"], matched["Adj Close"],equal_nan=True))
                row["yfinance_raw_agreement"] = bool(agrees)
                if not agrees:
                    row.update(status="partial", reason="raw_vs_yfinance_disagreement")
            else:
                row.update(status="partial", reason="yfinance_history_not_verified")
        rows.append(row)

    if "HKD=X" in prices:
        fx_source = next(r for r in rows if r["dataset"] == "HKD=X")
        if fx_source.get("provider_currency") == "HKD" and fx_source.get("provider_instrument") == "CURRENCY" and metadata["HKD=X"].get("symbol") == "HKD=X" and fx_source.get("yfinance_raw_agreement"):
            preview, preview_audit = monthly_spot_preview(prices["HKD=X"],manifest["start"],manifest["end_exclusive"])
            preview.to_csv(output / "USDHKD_monthly_spot_preview.csv",index=False,float_format="%.12f")
            rows.append({"kind":"fx","dataset":"Yahoo_USDHKD_monthly_preview","currency":"HKD per USD",**preview_audit,"raw_path":fx_source["raw_path"],"raw_sha256":fx_source["raw_sha256"],"import_alternative":"Authorized monthly FX with actual observation dates"})

    hkma = {"kind":"fx", "dataset":"HKMA_USDHKD", "status":"unavailable", "reason":"request_or_format_failed", "import_alternative":"Authorized HKD-per-USD CSV/XLSX; Yahoo HKD=X separately assessed"}
    for entry in files:
        if entry.get("role") == "hkma_json" and entry.get("http_status") == 200:
            try:
                table = parse_hkma(json.loads((base / entry["path"]).read_bytes()))
                table.to_csv(output / "HKMA_USDHKD.csv",index=False,float_format="%.12f")
                hkma.update(status="success",reason="small_endpoint_sample_only",rows=len(table),first_date=table["date"].min(),last_date=table["date"].max(),raw_path=entry["path"],raw_sha256=entry["sha256"])
            except (ValueError, KeyError, TypeError):
                pass
    failure = next((a for a in manifest["attempts"] if a["dataset"] == "HKMA_USDHKD" and a["result"] == "unavailable"), {})
    hkma["error_type"] = failure.get("error_type", "")
    rows.append(hkma)

    for dataset in FACTOR_URLS:
        row = {"kind":"factor", "dataset":dataset, "currency":"USD", "status":"unavailable", "reason":"request_or_format_failed", "import_alternative":"French monthly factor CSV/TXT with matched RF and percent units"}
        entries = [e for e in files if e.get("role") == "french_text" and e.get("dataset") == dataset]
        if entries:
            try:
                entry = entries[0]
                table = parse_french((base / entry["path"]).read_text(encoding="utf-8-sig"))
                needed = ["Mkt-RF", "SMB", "HML", "RF"] + (["RMW", "CMA"] if dataset.endswith("FF5") else [])
                requested = pd.period_range(pd.Period(manifest["start"],freq="M"),pd.Period(pd.Timestamp(manifest["end_exclusive"])-pd.Timedelta(days=1),freq="M"),freq="M")
                coverage = not len(requested.difference(pd.PeriodIndex(table["month"],freq="M")))
                complete = set(needed).issubset(table.columns) and np.isfinite(table[needed]).all().all() and coverage
                table.to_csv(output / (dataset+"_decimal.csv"),index=False,float_format="%.12f")
                row.update(status="success" if complete else "partial", reason="monthly_percent_converted_to_decimal" if complete else "missing_factor_values_or_requested_months",rows=len(table),first_date=table["month"].min(),last_date=table["month"].max(),fields="|".join(table.columns),raw_path=entry["path"],raw_sha256=entry["sha256"])
            except (ValueError, KeyError, TypeError):
                pass
        rows.append(row)

    action_tables = []
    for symbol, table in prices.items():
        if symbol != "HKD=X":
            diagnostics = action_diagnostics(table)
            if not diagnostics.empty:
                diagnostics.insert(0,"symbol",symbol)
                action_tables.append(diagnostics)
    actions = pd.concat(action_tables,ignore_index=True) if action_tables else pd.DataFrame(columns=["symbol","date","action"])
    actions.to_csv(output / "corporate_actions.csv",index=False,float_format="%.12f")
    apple_split = actions.loc[(actions["symbol"] == "AAPL") & (actions["date"] == "2020-08-31") & (actions["action"] == "split")]
    action_verified = not apple_split.empty and bool((apple_split["split_ratio"] == 4).all()) and bool((apple_split["close_return"].abs() < 0.20).all())
    gate = assess_gate(rows) and action_verified
    pd.DataFrame(rows).to_csv(output / "source_probe.csv",index=False)
    (output / "provider_metadata.json").write_text(json.dumps(metadata,indent=2,ensure_ascii=False)+"\n")
    summary = {"gate_passed":gate,"corporate_action_verified":action_verified,"product_success":sum(r["kind"] == "product" and r["status"] == "success" for r in rows),"snapshot_manifest":str(manifest_path.resolve()),"run_id":manifest["run_id"],"start":manifest["start"],"end_exclusive":manifest["end_exclusive"],"verified_files":len(files),"notes":["Six identified samples are not a formal portfolio or a validated candidate universe.","Adjusted close is a provider total-return proxy; Close is already split-adjusted, not historical unadjusted tape.","Daily missing rows remain partial; monthly FX preview uses actual observed dates without filling. S03 valuation/calendar checks pending.","HKD=X is unofficial Yahoo FX; HKMA endpoint success does not prove full historical coverage.","AP ex Japan is a regional USD proxy, not a Hong Kong-only factor.","Short availability, fees, fund holdings, delisted assets and point-in-time universe not verified."]}
    (output / "probe_summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False)+"\n")
    lines = ["# S01 自动可行性结果", "", f"快照：`{manifest['run_id']}`；产品请求窗口 {manifest['start']} 至 {manifest['end_exclusive']}（不含末日）。", "", "本步数据门槛：" + ("通过" if gate else "未通过；不得将缺失分支显示为可用"), "", "| 数据集 | 状态 | 行数 | 首日／月 | 末日／月 | 原因 |", "| --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        lines.append(f"| {r['dataset']} | {r['status']} | {r.get('rows','')} | {r.get('first_date','')} | {r.get('last_date','')} | {r['reason']} {r.get('error_type','')} |")
    lines += ["",f"AAPL 2020-08-31 的 4:1 拆股与拆股调整后价格连续性核对：{'通过' if action_verified else '未通过／窗口不含事件'}。独立事件依据：[Apple 分红与拆股记录](https://investor.apple.com/dividend-history/default.aspx)。", "", "分红日的调整价收益与现金再投资收益仅作数值诊断，供应商调整算法可能产生小差异；不把此检查称为完整总收益审计。详见 corporate_actions.csv。", "", "status=success 只表示 S01 字段／来源检查成功，不代表 S03/S05 数据合格。2800.HK 和原始 FX 缺值仍为 partial；另列月度 FX 预览保留真实观察日，并以 7 个日历日作本步陈旧性筛查，不填充原始日线。交易日历和美港估值时点在 S03 验证。", "", "缺 key／付费来源不发送请求；来源条件与后续处理见项目 docs/data/source_matrix.md。CSV/XLSX 导入在 S02 实现。本步没有进行 HKD 收益换算、投资优化或候选池数量校验。"]
    (output / "feasibility.md").write_text("\n".join(lines)+"\n")
    print(pd.DataFrame(rows)[["dataset","status","reason"]].to_string(index=False))
    print("S01 gate:", "PASS" if gate else "FAIL", "| verified snapshot files:",len(files))
    return gate


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-size",type=int,choices=[6],default=6,help="S01 deliberately fixed to six product categories")
    parser.add_argument("--start",default="2014-12-01")
    parser.add_argument("--end",default="2026-01-01",help="exclusive end date")
    parser.add_argument("--timeout",type=float,default=20)
    parser.add_argument("--output",type=Path,default=ROOT / "outputs/acceptance/S01")
    parser.add_argument("--replay",type=Path,help="verify and replay a saved snapshot; performs no network requests")
    args = parser.parse_args(argv)
    try:
        if date.fromisoformat(args.start) >= date.fromisoformat(args.end):
            raise ValueError("start must precede end")
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            raise ValueError("timeout must be positive")
    except ValueError as error:
        parser.error(str(error))
    try:
        manifest_path = args.replay.resolve() if args.replay else online_snapshot(args.output,args.start,args.end,args.timeout)
        passed = generate_reports(manifest_path,args.output)
    except (ValueError, OSError, KeyError, TypeError) as error:
        print("Probe/replay failed:",type(error).__name__,file=sys.stderr)
        return 2
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
