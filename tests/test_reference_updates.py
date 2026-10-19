import io
import json
import zipfile
import pytest
from portfolio.data.providers.base import RawResponse
from portfolio.data.reference_updates import run_reference_update, validate_reference_plan
from portfolio.data.snapshots import load_snapshot, read_artifact


def french(text=',Mkt-RF,SMB,HML,RF\n202501,2,3,4,0.4\n202502,1,2,3,0.3\n\nAnnual Factors\n2025,99,99,99,99'):
    body=io.BytesIO()
    with zipfile.ZipFile(body,'w') as z: z.writestr('F-F_Research_Data_Factors.csv',text)
    return RawResponse(body.getvalue(),200)


def page(*days):
    return RawResponse(json.dumps({'header':{'success':True},'result':{'records':[{'end_of_day':d,'usd':7.8} for d in days]}}).encode(),200)


def run(tmp_path,fetch,dataset='US_FF3',**kwargs):
    rid=run_reference_update(tmp_path,[dataset],'2025-01-01','2025-03-01',fetch=fetch,**kwargs)
    return rid,load_snapshot(tmp_path,rid)


def test_french_evidence_and_revision(tmp_path):
    rid,m=run(tmp_path,lambda *a:french())
    i=m['items'][0]
    assert i['status']=='success' and i['rows']==2
    assert b'Annual Factors' in read_artifact(tmp_path,rid,i['source_file'])
    assert b'0.020000' in read_artifact(tmp_path,rid,i['table_file'])
    _,m2=run(tmp_path,lambda *a:RawResponse(b'bad',429))
    assert m2['items'][0]['status']=='unavailable'
    assert load_snapshot(tmp_path,rid)==m

def test_reference_capture_completion(tmp_path):
    from datetime import datetime, timezone
    received=[]
    def fetch(*args):
        received.append(datetime.now(timezone.utc))
        return french()
    rid,m=run(tmp_path,fetch)
    assert datetime.fromisoformat(m['completed_utc']) >= received[0] >= datetime.fromisoformat(m['created_utc'])
    path=tmp_path/'runs'/rid/'snapshot_manifest.json'
    m['completed_utc']='2000-01-01T00:00:00+00:00'
    path.write_text(json.dumps(m))
    with pytest.raises(ValueError): load_snapshot(tmp_path,rid)
    m.pop('completed_utc'); path.write_text(json.dumps(m))
    assert 'completed_utc' not in load_snapshot(tmp_path,rid)


@pytest.mark.parametrize('text,status', [(',Mkt-RF,SMB,HML,RF\n202501,1,2,-99.99,4','partial'),(',Mkt-RF,SMB,HML,RMW,CMA,RF\n202501,1,2,3,4,5,6','unavailable')])
def test_french_quality(tmp_path,text,status):
    _,m=run(tmp_path,lambda *a:french(text))
    assert m['items'][0]['status']==status


def test_hkma_exact_multiple_and_offsets(tmp_path):
    calls=[]
    def fetch(*a,offset=0,page_size=1000):
        calls.append(offset)
        return {0:page('2025-01-02'),1:page('2025-02-03'),2:page()}[offset]
    _,m=run(tmp_path,fetch,'HKMA_USDHKD',page_size=1)
    assert calls==[0,1,2]
    i=m['items'][0]
    assert i['status']=='success' and i['pagination_complete']
    assert len(i['raw_files'])==3 and i['quality_scope']=='observation_months_only'


@pytest.mark.parametrize('second,expected,reason',[(page('2025-01-02'),'unavailable','parse_error'),(page('2025-03-01'),'unavailable','parse_error'),(RawResponse(b'secret',429),'partial','rate_limited'),(RawResponse(b'{',200),'unavailable','parse_error')])
def test_hkma_failed_page_retained(tmp_path,second,expected,reason):
    _,m=run(tmp_path,lambda *a,offset=0,**k: page('2025-01-02') if offset==0 else second,'HKMA_USDHKD',page_size=1)
    i=m['items'][0]
    assert (i['status'],i['reason'])==(expected,reason)
    assert len(i['raw_files'])==2


def test_timeout_cap_cancel_and_invalid(tmp_path):
    def fetch(*a,offset=0,**k):
        if offset: raise TimeoutError('secret')
        return page('2025-01-02')
    _,m=run(tmp_path,fetch,'HKMA_USDHKD',page_size=1)
    assert m['items'][0]['reason']=='timeout'
    _,m=run(tmp_path,fetch,'HKMA_USDHKD',page_size=1,max_pages=1)
    assert m['items'][0]['reason']=='page_limit'
    _,m=run(tmp_path,lambda *a:pytest.fail('fetch'),cancelled=lambda:True)
    assert m['items'][0]['status']=='cancelled'
    root=tmp_path/'absent'
    with pytest.raises(ValueError): run_reference_update(root,['US_FF3'],'2025-01-02','2025-03-01')
    assert not root.exists()


def test_snapshot_corrupt_and_symlink(tmp_path):
    rid,m=run(tmp_path,lambda *a:french())
    path=tmp_path/'runs'/rid/m['items'][0]['table_file']
    path.write_bytes(b'corrupt')
    with pytest.raises(ValueError): load_snapshot(tmp_path,rid)
    path.unlink(); path.symlink_to(tmp_path/'secret')
    with pytest.raises(ValueError): load_snapshot(tmp_path,rid)


@pytest.mark.parametrize('kwargs',[{'timeout':True},{'timeout':float('nan')},{'page_size':True},{'page_size':1001},{'max_pages':0},{'max_pages':101}])
def test_invalid_plan_no_io(tmp_path,kwargs):
    root=tmp_path/'missing'
    with pytest.raises(ValueError): run_reference_update(root,['US_FF3'],'2025-01-01','2025-03-01',fetch=lambda *a:pytest.fail('network'),**kwargs)
    assert not root.exists()


def test_post_response_cancel_preserves_raw(tmp_path):
    state={'cancel':False}
    def fetch(*a):
        state['cancel']=True
        return french()
    _,m=run(tmp_path,fetch,cancelled=lambda:state['cancel'])
    i=m['items'][0]
    assert i['status']=='cancelled' and len(i['raw_files'])==1 and i['table_file'] is None


def test_transport_exception_does_not_leak_and_programming_errors_propagate(tmp_path):
    def timeout(*a): raise TimeoutError('secret token')
    rid,m=run(tmp_path,timeout)
    assert m['items'][0]['reason']=='timeout'
    assert b'secret' not in (tmp_path/'runs'/rid/'snapshot_manifest.json').read_bytes()
    def broken(*a): raise OSError('disk issue')
    with pytest.raises(OSError): run(tmp_path,broken)


def test_ff5_separate_model_and_missing_month(tmp_path):
    def fetch(dataset,*a):
        text=',Mkt-RF,SMB,HML,RMW,CMA,RF\n202501,1,9,3,4,5,6\n202503,1,9,3,4,5,6'
        body=io.BytesIO()
        with zipfile.ZipFile(body,'w') as z: z.writestr('F-F_Research_Data_5_Factors_2x3.csv',text)
        return RawResponse(body.getvalue(),200)
    rid,m=run(tmp_path,fetch,'US_FF5')
    i=m['items'][0]
    assert i['status']=='partial' and i['missing_months']==['2025-02']
    import pandas as pd
    table=pd.read_csv(io.BytesIO(read_artifact(tmp_path,rid,i['table_file'])))
    assert table.SMB.iloc[0]==pytest.approx(.09)
    assert table.columns.tolist()==['month','Mkt-RF','SMB','HML','RMW','CMA','RF']


@pytest.mark.parametrize('body',[b'not zip',b'PK\x03\x04'])
def test_bad_archive_retained(tmp_path,body):
    _,m=run(tmp_path,lambda *a:RawResponse(body,200))
    assert m['items'][0]['reason']=='parse_error' and len(m['items'][0]['raw_files'])==1


def test_wrong_region_archive_rejected(tmp_path):
    _,m=run(tmp_path,lambda *a:french(),'AP_EX_JP_FF3')
    assert m['items'][0]['reason']=='parse_error'


@pytest.mark.parametrize('records',[[{'end_of_day':'2025-01-03','usd':7.8},{'end_of_day':'2025-01-02','usd':7.8}],[{'end_of_day':'2025-01-02','usd':0}],[{'end_of_day':'2025-01-02','usd':None}]])
def test_invalid_hkma_values_order(tmp_path,records):
    response=RawResponse(json.dumps({'header':{'success':True},'result':{'records':records}}).encode(),200)
    _,m=run(tmp_path,lambda *a,**k:response,'HKMA_USDHKD')
    assert m['items'][0]['status']=='unavailable' and m['items'][0]['reason']=='parse_error'


def test_short_hkma_page_ignores_datasize(tmp_path):
    response=page('2025-01-02','2025-02-02')
    payload=json.loads(response.body); payload['result']['datasize']=20000
    _,m=run(tmp_path,lambda *a,**k:RawResponse(json.dumps(payload).encode(),200),'HKMA_USDHKD')
    assert m['items'][0]['status']=='success' and len(m['items'][0]['pages'])==1


@pytest.mark.parametrize('mutation',[lambda m:m['items'][0].update(symbol='OTHER'),lambda m:m['items'][0].update(currency='HKD'),lambda m:m['items'][0].update(status='invented'),lambda m:m['items'][0].update(raw_files=[]),lambda m:m['files'][0].update(path='../secret'),lambda m:m.update(page_size=True)])
def test_manifest_rejects_invalid_fields(tmp_path,mutation):
    rid,m=run(tmp_path,lambda *a:french())
    mutation(m)
    (tmp_path/'runs'/rid/'snapshot_manifest.json').write_text(json.dumps(m))
    with pytest.raises(ValueError): load_snapshot(tmp_path,rid)


def test_unlisted_disk_file_rejected(tmp_path):
    rid,m=run(tmp_path,lambda *a:french())
    (tmp_path/'runs'/rid/'extra').write_bytes(b'bad')
    with pytest.raises(ValueError): load_snapshot(tmp_path,rid)


def test_oversized_hkma_page_rejected(tmp_path):
    _,m=run(tmp_path,lambda *a,**k:page('2025-01-02','2025-02-03'),'HKMA_USDHKD',page_size=1)
    assert m['items'][0]['reason']=='parse_error'


def test_wrong_model_full_history_never_publishes_outside_plan_table(tmp_path):
    text=',Mkt-RF,SMB,HML,RMW,CMA,RF\n202001,1,2,3,4,5,6\n202501,1,2,3,4,5,6'
    _,m=run(tmp_path,lambda *a:french(text))
    i=m['items'][0]
    assert i['status']=='unavailable' and i['reason']=='parse_error'
    assert i['table_file'] is None and i['rows']==0


@pytest.mark.parametrize('code,reason',[(35,'tls_error'),(60,'tls_error'),(7,'transport_error'),(28,'timeout')])
def test_reference_transport_safe_classification(tmp_path,code,reason):
    import yfinance
    from curl_cffi.requests.exceptions import RequestException
    def fetch(*args):
        raise RequestException('private secret',code=code)
    rid,m=run(tmp_path,fetch)
    assert m['items'][0]['reason']==reason
    assert b'private secret' not in (tmp_path/'runs'/rid/'snapshot_manifest.json').read_bytes()


@pytest.mark.parametrize('field',['created_utc','retrieved_utc'])
@pytest.mark.parametrize('timestamp',['2025-01-01T00:00:00','2025-01-01T00:00:00+08:00'])
def test_schema2_rejects_non_utc_timestamps(tmp_path,field,timestamp):
    rid,m=run(tmp_path,lambda *a:french())
    if field=='created_utc': m[field]=timestamp
    else: m['items'][0]['pages'][0][field]=timestamp
    (tmp_path/'runs'/rid/'snapshot_manifest.json').write_text(json.dumps(m))
    with pytest.raises(ValueError): load_snapshot(tmp_path,rid)


def test_ssl_error_class_without_code_and_legacy_adapter_read(tmp_path):
    import yfinance
    from curl_cffi.requests.exceptions import SSLError
    def fetch(*a): raise SSLError('private secret')
    _,m=run(tmp_path,fetch)
    assert m['items'][0]['reason']=='tls_error'
    rid,m=run(tmp_path,lambda *a:french())
    assert m['adapter_version']=='reference-v2'
    m['adapter_version']='reference-v1'
    (tmp_path/'runs'/rid/'snapshot_manifest.json').write_text(json.dumps(m))
    assert load_snapshot(tmp_path,rid)['adapter_version']=='reference-v1'
