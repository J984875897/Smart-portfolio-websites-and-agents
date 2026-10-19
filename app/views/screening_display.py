"""Chinese result presentation and complete exports; display filters never change N."""
from dataclasses import asdict
import json
import math
import pandas as pd
import streamlit as st

REASONS = {
    'ok':'通过本步筛选', 'direct_equity_excluded':'当前剔除直接个股／单只权益产品',
    'unsupported_structure':'杠杆／反向／复杂或未知结构不支持',
    'structure_missing':'缺少结构资料，请上传按资产标识填写的结构表',
    'structure_pending':'结构尚待核验', 'missing_structure_evidence':'结构声明缺少来源',
    'invalid_structure_date':'结构来源日期无效', 'unknown_exchange':'交易所未识别，请回导入页核对',
    'market_exchange_conflict':'声明市场与交易所不一致', 'unknown_tool_type':'工具类型未识别',
    'tool_classification_conflict':'补充工具分类与导入资料冲突',
    'unknown_asset_class':'缺少或无法识别经济类别', 'asset_class_conflict':'工具与经济类别矛盾',
    'non_investment_product':'指数／外汇报价／现金收益代理不计入产品',
    'unsupported_tool_type':'此版本不支持该工具', 'market_out_of_scope':'不在所选市场',
    'tool_out_of_scope':'不在所选工具类别', 'asset_class_out_of_scope':'不在所选经济类别',
    'manually_excluded':'已手动排除', 'duplicate_listing_identity':'上市身份重复，请回导入页修正映射',
    'duplicate_product_listing':'同产品另一上市条目，保留已声明代表',
    'listing_relationship_pending':'跨上市关系／代表缺少完整声明',
    'monthly_preparation_required':'日线等频率需要先完成月度数据准备',
    'missing_timing':'缺少逐月时间证据', 'missing_return':'共同窗口内缺少月收益',
    'missing_fx_start':'缺少起点汇率', 'missing_fx_end':'缺少期末汇率',
    'invalid_hkd_return':'该月港币收益未通过', 'ambiguous_return':'同月收益口径不唯一',
    'not_available_at_decision':'决策时点尚不可得',
    'period_not_complete_at_decision':'决策时点月度期间尚未结束',
    'window_start_history_insufficient':'窗口起始历史不足',
    'missing_asset_metadata':'缺少产品资料', 'conflicting_asset_metadata':'产品资料冲突',
}


def reason_text(value):
    return '；'.join(REASONS.get(code,f'其他资格问题：{code}') for code in str(value).split(';'))


def result_downloads(result):
    evidence = result.evidence | dict(screening_fingerprint=result.fingerprint,
                                     counts=result.counts,cardinality=asdict(result.cardinality),
                                     eligible_asset_ids=list(result.eligible_asset_ids))
    st.download_button('下载筛选产品与原因 CSV',result.audit.to_csv(index=False).encode('utf-8-sig'),
                       file_name='candidate_audit.csv',mime='text/csv',key='cs_export_audit',on_click='ignore')
    st.download_button('下载筛选港币矩阵 CSV',result.matrix.to_csv(index=True).encode('utf-8-sig'),
                       file_name='candidate_hkd_matrix.csv',mime='text/csv',key='cs_export_matrix',on_click='ignore')
    st.download_button('下载筛选证据 JSON',json.dumps(evidence,ensure_ascii=False,indent=2,allow_nan=False),
                       file_name='candidate_evidence.json',mime='application/json',key='cs_export_evidence',on_click='ignore')


def render_result(result):
    gate = result.cardinality
    st.subheader('筛选结果与下一步')
    if gate.status == 'passed': st.success('数量条件通过；尚未生成组合')
    elif gate.status == 'invalid_k': st.error(gate.message)
    else: st.warning('候选产品池过小')
    ratio = '不可计算（N=0）' if gate.ratio is None else f'{100*gate.ratio:.3f}%'
    st.write(f'目标 K = {gate.k} · 合格 N = {gate.n} · K/N = {ratio} · 上限 30%（含等号）')
    st.caption(f'最低需要 N = {gate.minimum_n} · 尚缺 {gate.shortfall} 项。数量通过只表示候选规模足够；相关性、风险、实际成员和权重尚未评估。')
    counts = result.counts
    for column,(key,label) in zip(st.columns(4), [('input_rows','输入资料行数'),('identity_qualified','身份合格且去重'),('in_scope','当前范围内'),('data_qualified','数据合格 N')]):
        with column: st.metric(label,counts[key])
    st.caption(f"共同窗口 {result.evidence['window_start']} 至 {result.evidence['window_end']} · 港币月收益60期 · 决策时点 {result.evidence['decision_utc']}")
    st.subheader('产品与排除原因')
    search = st.text_input('搜索名称、代码或资产标识（只改变展示）',key='cs_search',persist_state='session')
    status = st.selectbox('展示状态（不改变 N）',['全部','仅合格','仅排除'],key='cs_status',persist_state='session')
    audit = result.audit.copy(deep=True)
    if search:
        mask = pd.Series(False,index=audit.index)
        for field in ['asset_id','ticker','name']:
            if field in audit: mask |= audit[field].fillna('').astype(str).str.contains(search,case=False,regex=False)
        audit = audit.loc[mask]
    if status != '全部': audit = audit.loc[audit.status == ('eligible' if status == '仅合格' else 'excluded')]
    max_page = max(1,math.ceil(len(audit)/25))
    if st.session_state.get('cs_page',1) > max_page: st.session_state['cs_page'] = 1
    page = st.number_input('页码（每页25项，只改变展示）',min_value=1,max_value=max_page,value=1,step=1,key='cs_page',persist_state='session')
    display = audit.iloc[(page-1)*25:page*25].copy()
    columns = {'asset_id':'资产标识','ticker':'代码','name':'产品名称','market':'上市市场',
               'currency':'交易币种','canonical_tool_type':'工具类型','asset_class':'经济类别',
               'structure':'结构','structure_status':'结构声明状态','valid_months':'有效月数',
               'missing_months':'缺失／阻止月数','window_start':'窗口开始','window_end':'窗口结束',
               'listing_relationship_status':'跨上市关系状态','reason':'规则代码'}
    shown = display.reindex(columns=list(columns)).rename(columns=columns)
    shown.insert(0,'筛选状态',display.status.map({'eligible':'合格','excluded':'排除'}))
    shown['说明'] = display.reason.map(reason_text)
    shown['流动性／费率'] = '未提供'
    shown['产品名称'] = shown['产品名称'].fillna(shown['资产标识'])
    front = ['筛选状态','产品名称','说明','资产标识','代码']
    shown = shown.reindex(columns=front+[column for column in shown if column not in front])
    st.dataframe(shown,hide_index=True,width='stretch')
    st.caption(f'当前展示 {len(display)} / {len(audit)} 项；导出始终包含完整查验结果。多项排除原因不相加计算漏斗。数量通过后进入“04 收益与风险”计算；alpha／beta尚未接入。')
    st.subheader('导出本次结果')
    st.caption('CSV保留英文规则与稳定资产标识。港币矩阵只含本次合格列，小数0.01表示1%；没有合格产品时矩阵仍保留60个月份。')
    result_downloads(result)
    with st.expander('来源证据与研究限制'):
        st.write('时间、结构和跨上市关系由输入者声明；软件验证逻辑与一致性，未独立认证供应商历史发布时间或历史候选池完整性。跨上市关系未提供时标记not_verified，不按名称或相似收益猜测。')
        st.json(result.evidence)
