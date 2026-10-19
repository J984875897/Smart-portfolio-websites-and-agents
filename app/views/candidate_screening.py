"""S05-C local screening; recomputes A and B, never changes the imported version."""
from io import BytesIO
import hashlib
import json
import pandas as pd
import streamlit as st
from portfolio.data.contracts import DataBundle
from portfolio.data.importer import read_file
from portfolio.data.alignment import TIMING_FIELDS
from portfolio.data.quality import ASSET_CLASSES
from portfolio.universe.inputs import prepare_candidate_input
from portfolio.universe.input_evidence import input_evidence, frame_evidence
from portfolio.universe.samples import sample_candidate_inputs
from portfolio.universe.screening_samples import sample_screening_inputs
from portfolio.universe.risk_samples import sample_risk_inputs
from app.views.risk_analysis import clear_risk, render_risk
from portfolio.universe.screening import screen_candidates
from portfolio.universe.structures import STRUCTURE_COLUMNS
from portfolio.universe.listing_identity import RELATION_COLUMNS
from portfolio.universe.classification import TOOL_ORIGINS
from app.views.hkd_returns import READ_ERRORS, FX_FIELDS
from app.views.data_center import label
from app.views.screening_display import render_result
from app.views.page_chrome import page_header
from app.views.workspace_shell import route_button
from app.views.workspace_state import workspace_snapshot
from app.views.upload_state import research_upload

SOURCES = ['SYNTH 100项边界演示','SYNTH 缺月与时间案例','当前已打开导入版本','SYNTH 相关性与风险演示']


def upload_frame(title, fields, key):
    # New source/version gets fresh upload widgets; prior evidence cannot carry over.
    upload = research_upload(title+'（CSV／XLSX）',type=['csv','xlsx'], slot=key,
                              key=f'{key}_upload_{st.session_state.get("cs_upload_epoch",0)}')
    if upload is None: return pd.DataFrame(columns=fields)
    payload = upload.getvalue(); filename = upload.name; sheet = 0
    if filename.lower().endswith('.xlsx'):
        sheets = pd.ExcelFile(BytesIO(payload),engine='openpyxl').sheet_names
        if st.session_state.get(key+'_sheet') not in sheets: st.session_state.pop(key+'_sheet',None)
        sheet = st.selectbox(title+'工作表',sheets,key=key+'_sheet',persist_state='session')
    frame = read_file(payload,filename=filename,sheet_name=sheet)
    st.caption(f'{title}：{filename} · 工作表 {sheet} · {len(frame)} 行')
    return frame


def templates():
    with st.expander('证据格式与空白模板'):
        st.write('先在数据导入页保存／打开产品与原币数据，再回本页选择“当前已打开导入版本”。上传的asset_id须与导入资料一致。所有时间须含时区；日线数据不能只改成monthly便进入本页。')
        st.write('结构表：market填US/HK；canonical_tool_type与导入工具兼容（ADR／preferred_stock基于stock）；structure填ordinary／leveraged／inverse／complex；review_status填declared／pending。declared须完整填写来源名称、引用和YYYY-MM-DD日期。ETF也需要结构依据。')
        st.write('汇率单位为每1单位原币兑港币，月末日期须精确匹配；HKD无需汇率。跨上市关系可选：同product_group所有条目声明一致representative_asset_id，仅保留组内代表。未提供关系不宣称已认证。')
        st.markdown('时间资料的估值端点、可得时间填写方法见项目 `docs/data/alignment_format.md`。模板仅规定字段，不提供历史可得真实性证明。')
        for name,fields,key in [('月末汇率',FX_FIELDS,'fx'),('逐月时间证据',TIMING_FIELDS,'timing'),
                                ('结构资料',STRUCTURE_COLUMNS,'structures'),('跨上市关系',RELATION_COLUMNS,'relations')]:
            st.download_button('下载'+name+'模板',pd.DataFrame(columns=fields).to_csv(index=False).encode('utf-8-sig'),
                               file_name=key+'_template.csv',key='cs_template_'+key,on_click='ignore')


def render(render_mode='screen_candidates'):
    s = st.session_state
    s.setdefault('bundle',DataBundle()); s.setdefault('bundle_version','empty'); s.setdefault('cs_result',None)
    risk_mode = render_mode == 'risk_preview'
    page_header('完成研究 / '+('04' if risk_mode else '03'), '收益与风险' if risk_mode else '筛选候选',
                '核对当前候选与权重，计算收益、相关性和分散化效果。' if risk_mode else '先定义产品范围和目标持仓数，再检查产品资格与候选规模。')
    st.caption('港币计价 · 固定60月 · 当前资产池回溯研究 · 输入者声明时间证据 · 历史候选池未认证')
    # Keep the same controls in both routes, collapsed in risk mode. Their keys
    # and invalidation tokens remain identical, so a scope change clears risk.
    settings = st.expander('研究输入与产品范围' + ('（修改后需重新筛选）' if risk_mode else ''), expanded=not risk_mode)
    with settings:
        _render_inputs(risk_mode)
    from app.views.page_chrome import status_band
    status_slot = st.empty()
    if s.get('cs_result') is not None and s.get('cs_result_token') == s.get('cs_token'):
        if risk_mode:
            st.write(f'当前候选 N = {s["cs_result"].cardinality.n} · 目标 K = {s["cs_result"].cardinality.k}')
            route_button('返回筛选结果与排除原因', 'screen_candidates', 'risk_back_screen')
            render_risk(s['cs_candidate'],s['_cs_view_options'],s['cs_result'],s['cs_token'])
            with st.expander('候选明细与筛选证据'):
                render_result(s['cs_result'])
        else:
            render_result(s['cs_result'])
            route_button('前往收益与风险', 'risk_preview', 'cs_to_risk',
                         disabled=s['cs_result'].cardinality.status != 'passed')
    elif risk_mode:
        st.info('先完成候选筛选与数量条件，再计算收益与风险。可展开上方研究输入重新筛选。')
        route_button('前往筛选候选', 'screen_candidates', 'risk_need_screen')
    with status_slot.container():
        snapshot = workspace_snapshot(s)
        status_band(snapshot.risk if risk_mode else snapshot.candidates)


def _render_inputs(risk_mode):
    s = st.session_state
    st.subheader('1 · 数据来源与窗口')
    mode = st.radio('数据来源',SOURCES,key='cs_source',persist_state='session')
    try:
        if mode == SOURCES[0]:
            bundle,fx,timing,structures = sample_screening_inputs()
            st.info('SYNTH人工100项案例，仅测试筛选规则。默认K30、N100为30%；在下方“手动排除”选最后一项，重新筛选后N99应被阻止。这不是100项真实产品，收益刻意固定，不能据此判断分散化或投资表现。')
        elif mode == SOURCES[1]:
            bundle,fx,timing,structures = sample_candidate_inputs()
            st.info('SYNTH人工五资产：2项完整、3项因缺月／汇率等阻止；决策时点改为2025-01-31T17:00:00+08:00后只剩1项完整。不会写入已保存版本。')
        elif mode == SOURCES[3]:
            bundle,fx,timing,structures = sample_risk_inputs()
            st.info('SYNTH人工风险案例：100项、固定种子月收益，包含常数、完全同向和反向序列，仅验证风险与相关性；不是市场表现或投资预测。')
        else:
            bundle = s['bundle']
            fx = pd.DataFrame(columns=FX_FIELDS); timing = pd.DataFrame(columns=TIMING_FIELDS)
            structures = pd.DataFrame(columns=STRUCTURE_COLUMNS)
            st.caption(f'当前打开版本：{s["bundle_version"]} · 产品资料{len(bundle.assets)}行 · 原币观察{len(bundle.observations)}行')
            if bundle.observations.empty: st.info('请先到“数据导入”保存或打开版本，然后返回本页。也可选择SYNTH案例先体验。')
            else: st.info('本页会从原币数据重新查验，不直接使用其他页面的通过数量。日线到共同月度窗口的桥接尚未完成；缺少结构或时间资料时可先筛选查看诊断。')
    except READ_ERRORS as exc:
        s['cs_result'] = None
        s['cs_candidate'] = None
        clear_risk()
        st.error(f'无法读取输入：{exc}'); return
    left,right = st.columns(2)
    with left: end = st.text_input('结束月份（YYYY-MM）','2025-01',key='cs_end',persist_state='session')
    with right: decision = st.text_input('决策时点（ISO，须含时区）','2025-02-01T06:00:00+08:00',key='cs_decision',persist_state='session')
    source_identity = (mode,s['bundle_version'] if mode == SOURCES[2] else '')
    evidence_choices = ['使用案例证据','上传自己的证据'] if mode != SOURCES[2] else ['上传自己的证据']
    if s.get('cs_previous_source') != source_identity:
        s['cs_evidence_mode'] = evidence_choices[0]
        s['cs_excluded'] = []
        s['cs_adjusted'] = []
        s['cs_upload_epoch'] = s.get('cs_upload_epoch',0)+1
        for key in ['cs_fx','cs_timing','cs_structures','cs_relations']: s.pop(key+'_sheet',None)
    s['cs_previous_source'] = source_identity
    adjusted_ids = sorted(bundle.observations.loc[bundle.observations.value_kind == 'adjusted_price','asset_id'].astype(str).unique())
    if 'cs_adjusted' in s: s['cs_adjusted'] = [aid for aid in s['cs_adjusted'] if aid in adjusted_ids]
    confirmations = st.multiselect('已核实包含分配／拆股调整的复权价格资产（仅价格输入需要）',adjusted_ids,key='cs_adjusted',persist_state='session')
    evidence_mode = st.selectbox('月度与结构证据来源',evidence_choices,key='cs_evidence_mode',persist_state='session')
    relations = None
    error = None
    if evidence_mode == '上传自己的证据':
        try:
            fx = upload_frame('月末汇率',FX_FIELDS,'cs_fx')
            timing = upload_frame('逐月时间证据',TIMING_FIELDS,'cs_timing')
            structures = upload_frame('结构资料',STRUCTURE_COLUMNS,'cs_structures')
        except READ_ERRORS as exc: error = f'证据文件无法读取：{exc}。请核对CSV／XLSX格式和工作表。'
    try:
        with st.expander('跨上市关系（可选）'):
            relations_frame = upload_frame('跨上市关系',RELATION_COLUMNS,'cs_relations')
            if len(relations_frame) or relations_frame.attrs.get('raw_bytes') is not None: relations = relations_frame
    except READ_ERRORS as exc: error = f'跨上市文件无法读取：{exc}。请核对格式和工作表。'
    templates()
    st.subheader('2 · 选择产品范围')
    left,right = st.columns(2)
    with left:
        markets = st.multiselect('上市市场',['US','HK'],default=['US','HK'],format_func=lambda x: '美国' if x == 'US' else '香港',key='cs_markets',persist_state='session')
        tools = st.multiselect('工具类型',sorted(TOOL_ORIGINS),default=sorted(TOOL_ORIGINS),format_func=label,key='cs_tools',persist_state='session')
    with right:
        classes = st.multiselect('经济资产类别',sorted(ASSET_CLASSES),default=sorted(ASSET_CLASSES),format_func=label,key='cs_classes',persist_state='session')
        include_stocks = st.toggle('允许直接个股（关闭时仍可选股票ETF／基金）',value=False,key='cs_stocks',persist_state='session')
    ids = sorted(bundle.assets.asset_id.astype(str).unique())
    names = dict(zip(bundle.assets.asset_id,bundle.assets.name))
    if 'cs_excluded' in s: s['cs_excluded'] = [aid for aid in s['cs_excluded'] if aid in ids]
    excluded = st.multiselect('手动排除（会减少合格候选 N）',ids,
                               format_func=lambda aid:f'{aid} · {names.get(aid,aid)}',key='cs_excluded',persist_state='session')
    k = st.number_input('目标持仓数 K（整数20–100）',min_value=20,max_value=100,value=30,step=1,key='cs_k',persist_state='session')
    st.caption('市场、工具、经济类别、个股开关和手动排除会重新计算N。数量条件要求K/N≤30%；不会自动扩大范围或降低K。')
    params = dict(end_month=end,decision_at=decision,adjusted_price_assets=confirmations)
    options = dict(k=k,markets=markets,tool_types=tools,asset_classes=classes,include_stocks=include_stocks,
                   excluded_asset_ids=excluded,listing_relations=relations)
    token = None
    try:
        _,source_token,_ = input_evidence(bundle,fx,timing,structures,**params)
        token_data = dict(source=source_token,mode=mode,version=s['bundle_version'] if mode == SOURCES[2] else '',
                          options={key:value for key,value in options.items() if key != 'listing_relations'},
                          relations=frame_evidence(relations) if relations is not None else None)
        token = hashlib.sha256(json.dumps(token_data,sort_keys=True,allow_nan=False).encode()).hexdigest()
    except READ_ERRORS as exc: error = f'输入证据未通过：{exc}。请重新读取完整原表。'
    if error or s.get('cs_token') != token:
        s['cs_result'] = None
        s['cs_candidate'] = None
        clear_risk()
    s['cs_token'] = token
    if error: st.error(error)
    if st.button('查验数据并筛选',type='secondary' if risk_mode else 'primary',key='cs_compute',disabled=bundle.observations.empty or error is not None):
        s['cs_result'] = None
        s['cs_candidate'] = None
        clear_risk()
        try:
            with st.spinner('查验同一60月数据与产品资格…'):
                candidate = prepare_candidate_input(bundle,fx,timing,structures,**params)
                s['cs_result'] = screen_candidates(candidate,**options)
                s['cs_candidate'] = candidate
                s['cs_result_token'] = token
        except READ_ERRORS as exc:
            st.error(f'无法完成筛选：{exc}。请核对月份、含时区时间、证据字段与资产标识，修正后重新查验。')
    if s['cs_result'] is not None and s.get('cs_result_token') == token:
        # Results belong outside the input expander, rendered once by the caller.
        s['_cs_view_options'] = options
    elif not error:
        st.caption('设置好后点击“查验数据并筛选”。修改输入会撤下旧结果与旧下载；搜索、展示状态和翻页只改变表格。')
