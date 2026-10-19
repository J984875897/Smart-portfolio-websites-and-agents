"""Offline S02 acceptance evidence; uses synthetic fixtures and frozen S01 CSVs."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from uuid import uuid4
import pandas as pd
from portfolio.data import ImportConfig, DataBundle, read_file, preview_import, commit_import

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'outputs/acceptance/S02')
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    fixtures = ROOT/'tests/fixtures/imports'
    fields = ['asset_id','ticker','name','date','value','tool_type','asset_class','exchange','currency','frequency']
    cfg = ImportConfig(mapping={k:k for k in fields}, source_name='SYNTHETIC',
                       value_kind='total_return', return_unit='percent')
    first = preview_import(fixtures/'ten_products.csv', cfg)
    bundle = commit_import(first)
    repeated = preview_import(fixtures/'repeated_two.csv', cfg, existing=bundle)
    after = commit_import(repeated, bundle)
    assert len(bundle.assets) == len(after.assets) == 10
    assert len(after.observations) == 10 and len(after.provenance) == 12
    assert set(after.observations.value) == {.02}
    assert set(after.assets.tool_type) == {'ETF'}
    dirty = preview_import(fixtures/'dirty_data.csv', cfg)
    assert pd.isna(dirty.rows.iloc[3]['value'])
    assert dirty.rows.iloc[4]['value'] == .7 and dirty.rows.iloc[4]['status'] == 'review'
    assert len(commit_import(dirty).observations) == 0
    assert len(commit_import(dirty, allow_review=True).observations) == 1
    first.rows.to_csv(out/'import_preview.csv', index=False)
    repeated.rows.to_csv(out/'repeat_preview.csv', index=False)
    dirty.rows.to_csv(out/'dirty_preview.csv', index=False)
    dirty.issues.to_csv(out/'quality_report.csv', index=False)
    pd.DataFrame([
        {'operation':'first_import','input_rows':10,'assets_before':0,'assets_after':10,'observations_after':10,'provenance_after':10},
        {'operation':'repeat_two','input_rows':2,'assets_before':10,'assets_after':10,'observations_after':10,'provenance_after':12},
    ]).to_csv(out/'before_after_counts.csv', index=False)
    version = 'synthetic-'+uuid4().hex
    location = out/'bundles'/version
    after.save(location)
    restored = DataBundle.load(location)
    assert restored.assets.asset_id.tolist() == after.assets.asset_id.tolist()
    assert restored.observations.value.tolist() == after.observations.value.tolist()
    assert restored.raw_sources == after.raw_sources
    real = DataBundle()
    real_audit = []
    s01 = ROOT/'outputs/acceptance/S01'
    derived_manifest = json.loads((s01/'derived_manifest.json').read_text())
    source_specs = {f['path']:f for f in derived_manifest['files']}
    for symbol,tool,currency,exchange in [('AAPL','stock','USD','NASDAQ'),('SPY','ETF','USD','NYSE_ARCA'),('2800.HK','ETF','HKD','HKEX')]:
        path = ROOT/'outputs/acceptance/S01'/f'{symbol}_daily.csv'
        source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        assert source_hash == source_specs[path.name]['sha256'], f'S01 source changed: {path.name}'
        config = ImportConfig(mapping={'date':'date','value':'adj_close'}, source_name='S01_Yahoo_frozen',
            defaults={'asset_id':f'{exchange}:{symbol}:{currency}','ticker':symbol,'name':symbol,
                      'tool_type':tool,'asset_class':'equity','currency':currency,'exchange':exchange,'frequency':'daily'},
            value_kind='adjusted_price')
        preview = preview_import(path,config,existing=real)
        real = commit_import(preview,real)
        real_audit.append({'symbol':symbol,'source_sha256':source_hash,'input_rows':len(preview.rows),**preview.counts})
        if symbol=='2800.HK':
            missing = preview.rows.loc[preview.rows.date.eq('2025-10-24')]
            assert len(missing)==1 and missing.iloc[0]['status']=='blocked' and pd.isna(missing.iloc[0]['value'])
            preview.issues.to_csv(out/'real_missing_price_report.csv', index=False)
    assert len(real.assets)==3 and len(real.observations)==8305
    pd.DataFrame(real_audit).fillna(0).to_csv(out/'real_import_counts.csv', index=False)
    real_location = out/'bundles'/('s01-prices-'+uuid4().hex)
    real.save(real_location)
    assert len(DataBundle.load(real_location).observations)==8305
    summary = {'stage':'S02','status':'passed','synthetic_assets':10,'repeated_upload_assets':10,
               'percent_input':2,'decimal_output':.02,'dirty_status_counts':dirty.counts,
               'bundle_path':str(location.resolve()),'offline_load_verified':True,
               'real_bundle_path':str(real_location.resolve()),
               's01_run_id':derived_manifest['run_id'], 's01_source_hashes_verified':True,
               'real_product_count':3,'real_accepted_observations':len(real.observations),
               'real_2800_missing_blocked':True,'no_network_requests':True,
               'candidate_eligibility_checked':False,'hkd_returns_computed':False}
    (out/'import_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(summary,indent=2,ensure_ascii=False))


if __name__ == '__main__':
    main()
