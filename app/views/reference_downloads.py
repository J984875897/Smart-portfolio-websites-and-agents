"""Explicit reference updates and fully verified offline evidence inspection."""
from datetime import date
from io import BytesIO
import json
import os
from pathlib import Path
import pandas as pd
import streamlit as st
from portfolio.data.reference_updates import REFERENCE_CATALOG, run_reference_update, validate_reference_plan
from portfolio.data.snapshots import list_runs, load_snapshot, read_artifact, update_log

ROOT = Path(__file__).resolve().parents[2]
ERRORS = (ValueError, OSError, KeyError, TypeError)
STATUS = {'success':'成功（请求月份完整）','partial':'部分可用（仅诊断）','unavailable':'不可用','cancelled':'已取消'}
REASONS = {'tls_error':'TLS 安全连接失败','transport_error':'连接失败','timeout':'请求超时','rate_limited':'来源限流','http_error':'来源 HTTP 错误','parse_error':'来源解析失败','page_limit':'达到分页上限','empty_data':'无数据','complete_requested_months':'请求月份完整且数值有效','missing_or_invalid_values_or_months':'月份缺失或数值无效','cancelled':'已取消','not_requested':'未请求'}


def reference_root():
    return Path(os.environ.get('PORTFOLIO_REFERENCE_DOWNLOADS_ROOT',str(ROOT/'data/reference_downloads'))).resolve()


def _metadata(dataset):
    m=REFERENCE_CATALOG[dataset]
    return {'数据集':dataset,'名称':('美国' if m['region']=='US' else '亚太（日本除外）')+' '+m['model']+' 因子' if m['kind']=='factor' else '香港金管局官方美元兑港币','来源':m['provider'],'地区':{'US':'美国','Asia Pacific ex Japan':'亚太（日本除外）','Hong Kong':'香港'}[m['region']],'模型':m['model'] or '官方汇率','币种':m['currency'],'频率':'月度' if m['frequency']=='monthly' else '日度实际观察','单位':'小数' if m['unit']=='decimal' else '每 1 USD 对应 HKD'}


def _bound(root,run_id,manifest):
    return dict(root=str(root),run_id=run_id,manifest=manifest)


def _verified(binding,root):
    if binding['root']!=str(root):
        raise ValueError('different root')
    manifest=load_snapshot(root,binding['run_id'])
    if manifest.get('schema_version')!=2 or manifest!=binding['manifest']:
        raise ValueError('changed snapshot')
    return manifest


def _items(manifest):
    st.caption(f"版本编号：{manifest['run_id']} · UTC：{manifest['created_utc']} · 原请求 {manifest['start']}（含）至 {manifest['end_exclusive']}（不含）")
    st.dataframe(pd.DataFrame([{'数据集':i['dataset'],'状态':STATUS[i['status']],'原因':REASONS.get(i['reason'],'来源检查未通过'),'行数':i['rows'],'实际首日':i['first_date'],'实际末日':i['last_date']} for i in manifest['items']]),hide_index=True,width='stretch')


def _evidence(root,manifest,prefix,usable=False):
    """Call only after the entire bound snapshot passed verification."""
    rid=manifest['run_id']
    st.download_button('导出快照清单', (json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode(),'snapshot_manifest.json',key=prefix+'_manifest')
    if usable:
        datasets=[i['dataset'] for i in manifest['items'] if i['status']=='success']
        dataset=st.selectbox('成功缓存数据集',datasets,key='ref_dataset',persist_state='session')
        item=next(i for i in manifest['items'] if i['dataset']==dataset)
        st.dataframe(pd.DataFrame([_metadata(dataset)]),hide_index=True,width='stretch')
        st.caption(f"实际范围：{item['first_date']} 至 {item['last_date']} · {item['rows']} 行")
        payload=read_artifact(root,rid,item['table_file'])
        st.dataframe(pd.read_csv(BytesIO(payload)),hide_index=True,width='stretch')
        st.download_button('导出已验证数据 CSV',payload,item['table_file'],key='ref_table')
    raw=[name for i in manifest['items'] for name in [*i['raw_files'],i['source_file']] if name]
    if raw:
        name=st.selectbox('原始响应 / French 原始 CSV',raw,key=prefix+'_raw_file',persist_state='session')
        st.download_button('导出原始证据',read_artifact(root,rid,name),name,key=prefix+'_raw')
    partial=[i for i in manifest['items'] if i['status']=='partial' and i['table_file']]
    if partial:
        with st.expander('部分可用数据 · 仅诊断'):
            st.warning('缺失值保留，仅供诊断，不可作为正式输入或送入产品导入。')
            for item in partial:
                payload=read_artifact(root,rid,item['table_file'])
                st.caption(item['dataset'])
                st.dataframe(pd.read_csv(BytesIO(payload)),hide_index=True,width='stretch')
                st.download_button('导出诊断 CSV · '+item['dataset'],payload,item['table_file'],key=prefix+'_diag_table_'+item['dataset'])


def render():
    s=st.session_state
    root=reference_root()
    for key in ('ref_plan','ref_active','ref_result'):
        s.setdefault(key,None)
    from .page_chrome import tool_header
    with tool_header('因子与官方汇率', '生成因子和 HKMA 汇率下载计划，按需更新并校验本地缓存。', 'ref_active',
                [('返回利率与因子', 'rates_factors'), ('市场数据与缓存', 'downloads')]):
        st.info('French 每项下载完整 ZIP 后筛选请求月份；四套模型的 SMB 各自独立。亚太（日本除外）不是香港专属因子；USD RF 不是港币无风险利率。')
        st.caption('因子单位为小数；HKMA 汇率为 HKD per USD（每 1 USD 对应 HKD）。HKMA 仅检查请求月份存在实际日度观察，不认证逐日交易日历完整性，不自动聚合月度。无自动重试；缓存打开和导出均不联网。')
        datasets=st.multiselect('数据集',list(REFERENCE_CATALOG),default=list(REFERENCE_CATALOG),key='ref_datasets',persist_state='session')
        cols=st.columns(4)
        start=cols[0].date_input('起始月初（包含）',value=date(2025,1,1),key='ref_start_date',persist_state='session')
        end=cols[1].date_input('结束月初（不包含）',value=date(2026,1,1),key='ref_end',persist_state='session')
        timeout=cols[2].number_input('单请求超时（秒）',min_value=1,max_value=30,value=15,key='ref_timeout',persist_state='session')
        max_pages=cols[3].number_input('HKMA 最大页数',min_value=1,max_value=100,value=20,key='ref_max_pages',persist_state='session')
        st.caption('HKMA 每页固定 1000 条；短页或空页提前停止。')
        fingerprint=(str(root),tuple(datasets),start.isoformat(),end.isoformat(),timeout,max_pages)
        if s.get('ref_fingerprint')!=fingerprint:
            s['ref_plan']=None
            s['ref_fingerprint']=fingerprint
        if st.button('生成下载计划',key='ref_prepare'):
            try:
                selected=validate_reference_plan(datasets,start.isoformat(),end.isoformat(),timeout,1000,max_pages)
                s['ref_plan']=dict(datasets=selected,start=start.isoformat(),end=end.isoformat(),timeout=timeout,page_size=1000,max_pages=max_pages)
            except ERRORS:
                st.error('请选择不重复的允许数据集；日期必须为月初且起日早于止日，超时与页数须在允许范围内。')
        plan=s['ref_plan']
        if plan:
            french=sum(d!='HKMA_USDHKD' for d in plan['datasets'])
            hkma='HKMA_USDHKD' in plan['datasets']
            st.subheader('计划预览')
            st.write(f"请求数：最少 {french+int(hkma)}，最多 {french+(max_pages if hkma else 0)}；{plan['start']}（含）至 {plan['end']}（不含）")
            st.dataframe(pd.DataFrame([_metadata(d) for d in plan['datasets']]),hide_index=True,width='stretch')
            st.warning(f'仅支持开始前取消；同步下载过程中无法通过页面中断。超时为每个请求 {timeout} 秒；请求上限可能使总等待时间很长。')
            if st.button('取消下载计划',key='ref_cancel'):
                s['ref_plan']=None
                st.rerun()
            if st.button('开始下载',key='ref_start',type='primary'):
                try:
                    with st.spinner('正在下载并保存来源证据…'):
                        rid=run_reference_update(root,**plan)
                        manifest=load_snapshot(root,rid)
                        if manifest.get('schema_version')!=2: raise ValueError('wrong schema')
                    s['ref_result']=_bound(root,rid,manifest)
                    s['ref_plan']=None
                    st.success('本次尝试结束。请核对结果并显式打开所需缓存。')
                except ERRORS:
                    st.error('更新未完成；先前已打开缓存保留。请检查本地目录或稍后手动重试。')
        st.subheader('本地缓存')
        try:
            runs=list_runs(root)
        except ERRORS:
            runs=[]
            st.error('缓存目录无法读取。')
        if runs:
            selected=st.selectbox('下载记录（最新在前）',runs,key='ref_run',persist_state='session')
            if st.button('校验并打开缓存',key='ref_open'):
                try:
                    manifest=load_snapshot(root,selected)
                    if manifest.get('schema_version')!=2: raise ValueError('wrong schema')
                    binding=_bound(root,selected,manifest)
                    if any(i['status']=='success' for i in manifest['items']):
                        s['ref_active']=binding
                    else:
                        s['ref_result']=binding
                        st.warning('此记录没有成功项；保留先前成功缓存，仅提供审计与诊断。')
                except ERRORS:
                    st.error('缓存校验失败或不是参考数据 schema 2；先前缓存身份保留。')
            try:
                for rid in runs:
                    if load_snapshot(root,rid).get('schema_version')!=2: raise ValueError('wrong schema')
                log=update_log(root)
                st.download_button('导出更新日志 CSV',log.to_csv(index=False).encode(),'update_log.csv',key='ref_log')
            except ERRORS:
                st.warning('缓存完整性检查失败，停止完整日志导出。')
        else:
            st.caption('暂无下载记录。生成计划不会写入缓存。')
        result=s['ref_result']
        active=s['ref_active']
        if result:
            st.subheader('上次尝试结果（原请求范围）')
            try:
                manifest=_verified(result,root)
                _items(manifest)
                if not active or (active['root'],active['run_id'])!=(result['root'],result['run_id']):
                    with st.expander('本次尝试 · 审计与诊断导出'):
                        _evidence(root,manifest,'ref_result')
            except ERRORS:
                st.error('尝试记录校验失败或缓存目录已改变，停止该记录所有导出。')
        if active:
            st.subheader('已打开缓存')
            try:
                manifest=_verified(active,root)
                _items(manifest)
                _evidence(root,manifest,'ref',usable=True)
            except ERRORS:
                st.error('已打开缓存校验失败或缓存目录已改变；保留原身份，停止所有缓存使用与导出。')
