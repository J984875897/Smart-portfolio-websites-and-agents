import numpy as np
from test_importer import raw, config
from portfolio.data import preview_import, commit_import


def test_dirty_rows_traceable_and_review_requires_ack():
    df=raw(6)
    df.loc[0,'date']='2025-02-30'
    df.loc[1,'asset_class']=''
    df.loc[2,'value']='oops'
    df.loc[3,'value']=''
    df.loc[4,'value']='70'
    df.loc[5,'value']='-100'
    p=preview_import(df,config(),filename='dirty_data.csv')
    assert p.rows.status.tolist()==['blocked']*4+['review','review']
    assert np.isnan(p.rows.value[3])
    assert set(p.issues.source_file)=={'dirty_data.csv'}
    assert set(p.issues.source_row)=={2,3,4,5,6,7}
    assert len(commit_import(p).observations)==0
    assert len(commit_import(p,allow_review=True).observations)==2


def test_missing_and_invalid_types_do_not_become_stock():
    df=raw(3); df.loc[0,'tool_type']=''; df.loc[1,'tool_type']='nonsense'; df.loc[2,'exchange']=''
    assert preview_import(df,config(),filename='bad.csv').rows.status.tolist()==['blocked']*3
    cfg=config(defaults={'tool_type':'ETF'})
    assert preview_import(df,cfg,filename='bad.csv').rows.status.tolist()==['valid','blocked','blocked']


def test_within_file_conflicts_and_monthly_period_finding():
    df=raw(1); df=df.loc[df.index.repeat(3)].reset_index(drop=True)
    df.loc[1,'value']='3'; df.loc[2,'date']='2025-01-15'
    p=preview_import(df,config(),filename='conflict.csv')
    assert p.rows.status.tolist()[:2]==['blocked','blocked']
    assert 'monthly_period_collision' in p.issues.code.tolist()


def test_name_only_identity_blocked():
    df=raw(1).drop(columns=['asset_id','ticker'])
    assert preview_import(df,config(),filename='name.csv').rows.status.tolist()==['blocked']


def test_numeric_boundaries_and_negative_extreme():
    df=raw(5); df['value']=['inf','nan','-101','-100','-60']
    p=preview_import(df,config(),filename='boundaries.csv')
    assert p.rows.status.tolist()==['blocked','blocked','blocked','review','review']
    assert p.rows.value.tolist()[3:]==[-1,-.6]
    cfg=config(); from dataclasses import replace
    df=raw(3); df['value']=['0','-1','10']
    assert preview_import(df,replace(cfg,value_kind='price'),filename='prices.csv').rows.status.tolist()==['blocked','blocked','valid']


def test_within_file_metadata_disagreement_blocks_all_records():
    df=raw(1); df=df.loc[df.index.repeat(2)].reset_index(drop=True)
    df.loc[1,'date']='2025-02-28'; df.loc[1,'asset_class']='bond'
    assert preview_import(df,config(),filename='clash.csv').rows.status.tolist()==['blocked','blocked']


def test_dataframe_zero_preserved_and_nullable_missing_blocked():
    import pandas as pd
    df=raw(3); df['value']=pd.Series([0,pd.NA,2],dtype='Int64')
    p=preview_import(df,config(),filename='nullable.csv')
    assert p.rows.status.tolist()==['valid','blocked','valid']
    assert p.rows.value.iloc[0]==0.0
    assert np.isnan(p.rows.value.iloc[1])
    assert p.rows.value.iloc[2]==.02
    csv=preview_import(df.to_csv(index=False).encode(),config(),filename='zero.csv')
    assert csv.rows.status.tolist()==['valid','blocked','valid']
    assert csv.rows.value.iloc[0]==0.0


def test_duplicate_extreme_rows_require_ack_before_any_metadata_acceptance():
    import pandas as pd
    df=pd.concat([raw(1),raw(1)],ignore_index=True); df['value']='70'
    p=preview_import(df,config(),filename='extreme.csv')
    pending=commit_import(p)
    assert pending.assets.empty and pending.aliases.empty
    assert pending.observations.empty and pending.classification_history.empty
    assert pending.provenance.status.tolist()==['review_pending','review_pending']
    assert p.rows.status.tolist()==['review','review']
    assert p.rows.is_duplicate.tolist()==[False,True]
    accepted=commit_import(p,allow_review=True)
    assert len(accepted.assets)==len(accepted.observations)==1
    assert accepted.observations.value.tolist()==[.7]
    assert len(accepted.provenance)==2
    cfg=config(classification_overrides={'p0':{'asset_class':'bond'}})
    correction=preview_import(df,cfg,accepted,filename='correction.csv')
    unchanged=commit_import(correction,accepted)
    assert unchanged.assets.asset_class.tolist()==['equity']
    assert unchanged.classification_history.empty
    assert unchanged.provenance.status.tolist()[-2:]==['review_pending','review_pending']
    corrected=commit_import(correction,accepted,allow_review=True)
    assert corrected.assets.asset_class.tolist()==['bond']
    assert corrected.classification_history.new_value.tolist()==['bond']
    assert len(corrected.observations)==1


def test_duplicate_monthly_collision_rows_all_require_ack():
    import pandas as pd
    prior=commit_import(preview_import(raw(1),config(),filename='old.csv'))
    df=pd.concat([raw(1),raw(1)],ignore_index=True); df['date']='2025-01-15'
    p=preview_import(df,config(),prior,filename='collision.csv')
    assert p.rows.status.tolist()==['review','review']
    assert p.rows.is_duplicate.tolist()==[False,True]
    pending=commit_import(p,prior)
    assert len(pending.observations)==1
    assert pending.provenance.status.tolist()[-2:]==['review_pending','review_pending']
    assert len(commit_import(p,prior,allow_review=True).observations)==2
