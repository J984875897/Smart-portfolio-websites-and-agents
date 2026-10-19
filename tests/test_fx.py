import pandas as pd
import pytest
from test_returns import bundle


def fx(records=None):
    return pd.DataFrame(records or [dict(date='2023-12-31',currency='USD',hkd_per_unit=7.8,source_name='manual'),dict(date='2024-01-31',currency='USD',hkd_per_unit=7.9,source_name='manual')])


def validate(f):
    from portfolio.data.fx import validate_fx
    return validate_fx(f)


def reconcile(b,f,**kwargs):
    from portfolio.data.fx import reconcile_hkd
    return reconcile_hkd(b,f,**kwargs)


def test_hand_calculation_and_native_no_fx():
    r=reconcile(bundle([dict(date='2024-01-31',value=.01)]),fx()).reconciliation.iloc[0]
    assert r.hkd_return==pytest.approx(.02294871794871795)
    assert r.hkd_return==pytest.approx(r.local_return+r.fx_return+r.cross_term)
    assert r.fx_start_source_row==2 and r.fx_end_source_row==3
    assert reconcile(bundle([dict(date='2024-01-31',value=.01)],currency='HKD'),pd.DataFrame()).reconciliation.iloc[0].hkd_return==.01


def test_missing_and_loss():
    b=bundle([dict(date='2024-01-31',value=-1)])
    assert reconcile(b,fx()).reconciliation.iloc[0].hkd_return==-1
    r=reconcile(b,fx().iloc[:1]).reconciliation.iloc[0]
    assert r.reason=='missing_fx_end' and pd.isna(r.hkd_return)


@pytest.mark.parametrize('value',[0,-1,float('inf'),'bad'])
def test_invalid_duplicate_blocks_entire_key(value):
    f=fx(); extra=f.iloc[[0]].copy(); extra['hkd_per_unit']=value
    r=validate(pd.concat([f,extra],ignore_index=True))
    assert r.values.date.tolist()==['2024-01-31']
    assert len(r.issues)==2


def test_conflict_and_identical_source_evidence():
    f=fx(); extra=f.iloc[[0]].copy(); extra['source_name']='other'
    r=validate(pd.concat([f,extra],ignore_index=True))
    assert len(r.values)==2 and len(r.values.iloc[0].sources)==2
    extra['hkd_per_unit']=8
    assert len(validate(pd.concat([f,extra])).values)==1


@pytest.mark.parametrize('field,value',[('date','2024-1-31'),('currency','XXX'),('source_name','')])
def test_fx_invalid(field,value):
    f=fx().iloc[:1].copy(); f.loc[0,field]=value
    assert validate(f).values.empty
    assert not validate(f).issues.empty


def test_empty_schema_and_input_unchanged():
    f=fx(); old=f.copy(deep=True); validate(f)
    pd.testing.assert_frame_equal(old,f)
    r=reconcile(bundle([]),pd.DataFrame())
    assert 'hkd_return' in r.reconciliation.columns
    assert 'code' in r.fx_issues.columns


def test_read_file_evidence_preserved():
    from portfolio.data.importer import read_file
    f=read_file(b'date,currency,hkd_per_unit,source_name\n2023-12-31,USD,7.8,manual\n2024-01-31,USD,7.9,manual\n', filename='fx.csv')
    result=reconcile(bundle([dict(date='2024-01-31',value=.01)]),f).reconciliation.iloc[0]
    assert result.fx_end_source_file=='fx.csv'
    assert result.fx_end_source_row==3
    assert len(result.fx_end_source_hash)==64


def test_invalid_local_never_obtains_hkd_return():
    b=bundle([dict(date='2024-01-31',value=100)])
    b.observations['value_kind']='price'
    r=reconcile(b,fx()).reconciliation.iloc[0]
    assert r.status=='blocked' and r.reason=='not_total_return'
    assert pd.isna(r.hkd_return)


@pytest.mark.parametrize('extension', ['csv', 'xlsx'])
def test_file_metadata_overrides_submitted_provenance(tmp_path, extension):
    import hashlib
    from portfolio.data.importer import read_file
    records = fx()
    records['source_file'] = 'old.csv'
    records['source_sheet'] = 'old-sheet'
    records['source_row'] = 999
    records['source_hash'] = 'old-hash'
    path = tmp_path / ('actual.' + extension)
    if extension == 'csv':
        lines = records.to_csv(index=False).splitlines()
        path.write_text(lines[0] + '\n\n' + '\n\n'.join(lines[1:]) + '\n')
        frame = read_file(path)
        expected_rows, expected_sheet = [3, 5], ''
    else:
        records.to_excel(path, index=False, sheet_name='Quotes')
        frame = read_file(path, sheet_name='Quotes')
        expected_rows, expected_sheet = [2, 3], 'Quotes'
    expected_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    old = frame.copy(deep=True)
    result = validate(frame)
    assert result.issues.empty
    for row, source_row in zip(result.values.to_dict('records'), expected_rows):
        expected = dict(source_name='manual', source_file=path.name,
                        source_sheet=expected_sheet, source_row=source_row,
                        source_hash=expected_hash)
        assert {field: row[field] for field in expected} == expected
        assert row['sources'] == [expected]
    reconciled = reconcile(bundle([dict(date='2024-01-31', value=.01)]), frame).reconciliation.iloc[0]
    assert reconciled.fx_end_source_file == path.name
    assert reconciled.fx_end_source_sheet == expected_sheet
    assert reconciled.fx_end_source_row == expected_rows[1]
    assert reconciled.fx_end_source_hash == expected_hash
    pd.testing.assert_frame_equal(frame, old)


def test_in_memory_manual_provenance_preserved():
    frame = fx().iloc[:1].copy()
    evidence = dict(source_file='manual.csv', source_sheet='Manual',
                    source_row=42, source_hash='manual-hash')
    for field, value in evidence.items():
        frame[field] = value
    row = validate(frame).values.iloc[0]
    assert {field: row[field] for field in evidence} == evidence
