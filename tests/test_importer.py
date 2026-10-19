from io import BytesIO
import pandas as pd
import pytest
from portfolio.data import ImportConfig, preview_import, commit_import, read_file, DataBundle


def config(**kw):
    return ImportConfig(mapping={x:x for x in ['asset_id','ticker','name','date','value','tool_type','asset_class','exchange','currency','frequency']}, source_name='synthetic', value_kind='total_return', return_unit='percent', **kw)


def raw(n=10):
    return pd.DataFrame([dict(asset_id=f'p{i}',ticker=f'{i:04}',name=f'Product {i}',date='2025-01-31',value='2',tool_type='ETF',asset_class='equity',exchange='HKEX',currency='HKD',frequency='monthly') for i in range(n)])


def test_repeat_preserves_ten_products_and_percent():
    p=preview_import(raw(), config(), filename='ten_products.csv')
    b=commit_import(p)
    assert len(b.assets)==10 and len(b.observations)==10
    assert set(b.observations.value)=={.02}
    b2=commit_import(preview_import(raw(2),config(),existing=b,filename='repeated_two.csv'),b)
    assert len(b2.assets)==10 and len(b2.observations)==10
    assert len(b2.provenance)==12
    assert set(b2.assets.tool_type)=={'ETF'}


def test_csv_identifiers_xlsx_percent_equivalence():
    df=raw(1); df['ticker']='0700'
    csv=read_file(df.to_csv(index=False).encode(),filename='sample.csv')
    assert csv.ticker[0]=='0700'
    stream=BytesIO(); df.to_excel(stream,index=False)
    xp=preview_import(stream.getvalue(),config(),filename='sample.xlsx')
    cp=preview_import(csv,config(),filename='sample.csv')
    assert xp.rows.value[0]==cp.rows.value[0]==.02
    assert xp.rows.source_row[0]==2


def test_persistence_hash_and_no_overwrite(tmp_path):
    b=commit_import(preview_import(raw(1),config(),filename='sample.csv'))
    path=tmp_path/'bundle'; b.save(path)
    loaded=DataBundle.load(path)
    assert loaded.assets.asset_id.tolist()==['p0']
    assert loaded.observations.value.tolist()==[.02]
    with pytest.raises(FileExistsError): b.save(path)
    with (path/'assets.csv').open('a') as f: f.write('corrupt')
    with pytest.raises(ValueError,match='hash'): DataBundle.load(path)


def test_prior_conflict_does_not_mutate():
    b=commit_import(preview_import(raw(1),config(),filename='old.csv'))
    df=raw(1); df['value']='3'
    p=preview_import(df,config(),existing=b,filename='new.csv')
    assert p.rows.status.tolist()==['blocked']
    assert 'conflict' in p.issues.code.tolist()
    assert commit_import(p,b).observations.value.tolist()==[.02]
    assert len(b.provenance)==1


def test_alias_and_classification_override_history():
    b=commit_import(preview_import(raw(1),config(),filename='old.csv'))
    df=raw(1); df['date']='2025-02-28'; df['asset_class']='bond'
    p=preview_import(df,config(),existing=b,filename='new.csv')
    assert p.rows.status.tolist()==['blocked']
    cfg=config(classification_overrides={'p0':{'asset_class':'bond'}})
    b2=commit_import(preview_import(df,cfg,existing=b,filename='new.csv'),b)
    assert b2.assets.asset_class.tolist()==['bond']
    assert b2.classification_history.iloc[0].old_value=='equity'
    assert b.assets.asset_class.tolist()==['equity']
    df=raw(1).drop(columns='asset_id'); df['date']='2025-03-31'
    assert preview_import(df,config(),existing=b,filename='alias.csv').rows.asset_id.tolist()==['p0']
    df['currency']='USD'
    assert preview_import(df,config(),existing=b,filename='alias.csv').rows.status.tolist()==['blocked']


def test_manual_alias_cross_supplier_and_literal_na_identifiers():
    df=raw(1); df['asset_id']='NA'; df['ticker']='NULL'
    data=df.to_csv(index=False).encode()
    b=commit_import(preview_import(data,config(),filename='a.csv'))
    assert b.assets.asset_id.tolist()==['NA'] and b.assets.ticker.tolist()==['NULL']
    alt=raw(1); alt['asset_id']=''; alt['ticker']='ALT'; alt['date']='2025-02-28'
    cfg=ImportConfig(mapping=config().mapping,source_name='supplier2',value_kind='total_return',return_unit='percent',alias_mappings={('supplier2','HKEX','ALT','','HKD'):'NA'})
    b2=commit_import(preview_import(alt,cfg,b,filename='b.csv'),b)
    assert len(b2.assets)==1 and len(b2.observations)==2


def test_missing_alias_target_blocked():
    cfg=config(alias_mappings={('synthetic','HKEX','0000','','HKD'):'unknown'})
    assert preview_import(raw(1),cfg,filename='a.csv').rows.status.tolist()==['blocked']


def test_xlsx_sheet_trace_and_roundtrip_every_table(tmp_path):
    stream=BytesIO()
    with pd.ExcelWriter(stream,engine='openpyxl') as writer: raw(1).to_excel(writer,index=False,sheet_name='Prices')
    cfg=config(sheet_name='Prices')
    p=preview_import(stream.getvalue(),cfg,filename='book.xlsx')
    assert p.rows.source_sheet.tolist()==['Prices']
    b=commit_import(p); b.save(tmp_path/'b'); loaded=DataBundle.load(tmp_path/'b')
    assert loaded.raw_sources==b.raw_sources
    for name in ['assets','observations','aliases','provenance','issues','classification_history','returns','fx','factors']:
        assert getattr(loaded,name).shape==getattr(b,name).shape


def test_load_manifest_rejects_path_traversal_and_missing_table(tmp_path):
    import json
    b=commit_import(preview_import(raw(1),config(),filename='a.csv')); path=tmp_path/'b'; b.save(path)
    manifest=json.loads((path/'manifest.json').read_text()); manifest['tables']['assets']['file']='../outside.csv'
    (path/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='path'): DataBundle.load(path)
    del manifest['tables']['assets']; (path/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='table'): DataBundle.load(path)


def test_alias_cannot_merge_different_currency_exchange_or_share_class():
    b=commit_import(preview_import(raw(1),config(),filename='a.csv'))
    for field,value in [('currency','USD'),('exchange','NYSE'),('share_class','B')]:
        df=raw(1); df['date']='2025-02-28'; df['ticker']='ALT'; df[field]=value
        identity=('synthetic',df.exchange[0],'ALT',df.get('share_class',[''])[0],df.currency[0])
        cfg=config(alias_mappings={identity:'p0'}); cfg.mapping['share_class']='share_class'
        assert preview_import(df,cfg,b,filename='b.csv').rows.status.tolist()==['blocked']


def test_explicit_mapping_does_not_guess_unmapped_fields():
    cfg=ImportConfig(mapping={'date':'date','value':'value'},source_name='test')
    assert preview_import(raw(1),cfg,filename='a.csv').rows.status.tolist()==['blocked']


def test_same_listing_distinct_explicit_ids_within_file_blocked():
    df=raw(1); df=df.loc[df.index.repeat(2)].reset_index(drop=True); df.loc[1,'asset_id']='different'
    assert preview_import(df,config(),filename='a.csv').rows.status.tolist()==['blocked','blocked']


def test_duplicate_observation_can_record_explicit_classification_correction():
    b=commit_import(preview_import(raw(1),config(),filename='a.csv'))
    cfg=config(classification_overrides={'p0':{'asset_class':'bond'}})
    result=commit_import(preview_import(raw(1),cfg,b,filename='correction.csv'),b)
    assert len(result.observations)==1
    assert result.assets.asset_class.tolist()==['bond']
    assert result.classification_history.new_value.tolist()==['bond']


def test_new_product_classification_override_retains_original_history():
    cfg=config(classification_overrides={'p0':{'asset_class':'bond'}})
    b=commit_import(preview_import(raw(1),cfg,filename='new.csv'))
    assert b.classification_history.old_value.tolist()==['equity']
    assert b.classification_history.new_value.tolist()==['bond']
    assert b.classification_history.source_row.tolist()==[2]


def test_native_excel_date_cell_accepted_but_csv_timestamp_strict():
    from datetime import datetime
    df=raw(1); df['date']=datetime(2025,1,31)
    stream=BytesIO(); df.to_excel(stream,index=False)
    assert preview_import(stream.getvalue(),config(),filename='native.xlsx').rows.status.tolist()==['valid']
    df['date']='2025-01-31 00:00:00'
    assert preview_import(df.to_csv(index=False).encode(),config(),filename='timestamp.csv').rows.status.tolist()==['blocked']


@pytest.mark.parametrize('field,value', [('currency','USD'),('exchange','NYSE'),('share_class','B'),('ticker','ALT')])
def test_listing_disagreement_blocks_every_row_in_both_orders(field, value):
    df=pd.concat([raw(1),raw(1)],ignore_index=True)
    df['share_class']=''; df.loc[1,'date']='2025-02-28'; df.loc[1,field]=value
    cfg=config(); cfg.mapping['share_class']='share_class'
    for incoming in [df,df.iloc[::-1]]:
        p=preview_import(incoming,cfg,filename='clash.csv')
        assert p.rows.status.tolist()==['blocked','blocked']
        assert commit_import(p).assets.empty


def test_csv_physical_start_lines_survive_blank_and_multiline_records():
    df=raw(3); df.loc[1,'name']='Product\nsecond line'; df.loc[2,'value']='oops'
    lines=df.to_csv(index=False).splitlines(keepends=True)
    payload=(lines[0]+lines[1]+'\n'+''.join(lines[2:])).encode()
    frame=read_file(payload,filename='lines.csv')
    assert len(frame)==3
    p=preview_import(frame,config())
    assert p.rows.source_row.tolist()==[2,4,6]
    assert p.issues.source_row.tolist()==[6]
    b=commit_import(p)
    assert b.observations.source_row.tolist()==[2,4]
    assert b.provenance.source_row.tolist()==[2,4,6]


@pytest.mark.parametrize('format',['csv','xlsx','dataframe'])
def test_duplicate_column_names_rejected_before_mapping(format):
    df=raw(1); df.insert(5,'extra_value','9'); df=df.rename(columns={'extra_value':'value'})
    if format=='dataframe': data=df
    elif format=='csv': data=df.to_csv(index=False).encode()
    else:
        stream=BytesIO(); df.to_excel(stream,index=False); data=stream.getvalue()
    with pytest.raises(ValueError,match='[Uu]nique|[Dd]uplicate'):
        preview_import(data,config(),filename='ambiguous.'+('csv' if format=='dataframe' else format))


def test_distinct_stable_ids_without_tickers_same_file_and_sequential_uploads():
    df=raw(2); df['ticker']=''; df['asset_id']=['ISIN_A','ISIN_B']
    p=preview_import(df,config(),filename='stable.csv')
    assert p.rows.status.tolist()==['valid','valid']
    same=commit_import(p)
    assert same.assets.asset_id.tolist()==['ISIN_A','ISIN_B']
    assert same.aliases.empty
    sequential=DataBundle()
    for i in [0,1]:
        piece=df.iloc[[i]]
        p=preview_import(piece,config(),sequential,filename=f'stable{i}.csv')
        assert p.rows.status.tolist()==['valid']
        sequential=commit_import(p,sequential)
    assert sequential.assets.asset_id.tolist()==['ISIN_A','ISIN_B']
    assert sequential.aliases.empty
    for bundle in [same,sequential]:
        for i in [0,1]:
            p=preview_import(df.iloc[[i]],config(),bundle,filename=f'repeat{i}.csv')
            assert p.rows.asset_id.tolist()==[df.asset_id.iloc[i]]
            assert p.rows.status.tolist()==['duplicate']
            bundle=commit_import(p,bundle)
        assert len(bundle.assets)==len(bundle.observations)==2
        assert bundle.aliases.empty
        assert bundle.provenance.asset_id.tolist()==['ISIN_A','ISIN_B','ISIN_A','ISIN_B']
    missing=df.iloc[[0]].copy(); missing['asset_id']=''
    assert preview_import(missing,config(),filename='missing.csv').rows.status.tolist()==['blocked']
