"""Workflow navigation and a read-only overview of the current research."""
from dataclasses import dataclass
from html import escape
import streamlit as st
from .page_chrome import page_header, status_band, STATUS_LABELS
from .workspace_state import next_step


@dataclass(frozen=True)
class Route:
    title: str
    group: str
    module: str
    legacy: str = ''


ROUTES = {
    'overview': Route('研究总览', '研究', ''),
    'prepare_data': Route('01 准备数据', '完成研究', 'data_center', '数据导入'),
    'eligibility': Route('02 核对资格', '完成研究', 'eligibility_hub'),
    'screen_candidates': Route('03 筛选候选', '完成研究', 'candidate_screening', '候选筛选'),
    'risk_preview': Route('04 收益与风险', '完成研究', 'candidate_screening', '候选筛选'),
    'downloads': Route('市场数据与缓存', '数据工具与证据', 'downloads', '下载与缓存'),
    'returns_window': Route('收益与窗口核对', '数据工具与证据', 'hkd_returns', '港币收益查验'),
    'history_sources': Route('历史资格与来源', '数据工具与证据', 'time_eligibility', '历史资格查验'),
    'rates_factors': Route('利率与因子', '数据工具与证据', 'risk_free', '港币利率查验'),
    'alignment': Route('共同窗口查验', '收益与窗口核对', 'alignment', '共同窗口查验'),
    'daily_monthly': Route('日线月度查验', '收益与窗口核对', 'daily_monthly', '日线月度查验'),
    'daily_hkd': Route('日线港币查验', '收益与窗口核对', 'daily_hkd', '日线港币查验'),
    'reference_downloads': Route('因子与官方汇率', '利率与因子', 'reference_downloads', '因子与官方汇率'),
}
LEGACY_ROUTES = {v.legacy: k for k, v in ROUTES.items() if v.legacy and k != 'risk_preview'}

def navigate(route):
    st.session_state['workspace_route'] = route
    st.session_state['workspace'] = ROUTES[route].legacy
    st.session_state['_workspace_legacy'] = ROUTES[route].legacy


def route_button(label, route, key, **kwargs):
    return st.button(label, key=key, on_click=navigate, args=(route,), **kwargs)


def apply_style():
    st.markdown('''<style>
    :root {--ink:#18334C;--teal:#176B87;--mist:#EEF3F8;}
    .stApp {background:#F7F9FC;color:var(--ink);}
    [data-testid="stMainBlockContainer"] {max-width:1240px;padding:5rem 2.4rem 4rem;}
    [data-testid="stMain"] h1 {font-size:2.15rem;line-height:1.3;letter-spacing:-.035em;font-weight:750;}
    [data-testid="stMain"] h2 {font-size:1.45rem;line-height:1.4;}
    [data-testid="stMain"] h3 {font-size:1.15rem;line-height:1.5;}
    [data-testid="stMain"] p,[data-testid="stMain"] label {line-height:1.65;}
    [data-testid="stSidebar"] {background:var(--ink);border-right:0;}
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"],
    [data-testid="stSidebar"] summary {color:#E4ECF4;}
    [data-testid="stSidebar"] .stButton button {background:transparent;border:1px solid transparent;color:#E4ECF4;text-align:left;justify-content:flex-start;}
    [data-testid="stSidebar"] .stButton button:hover {background:#24455F;border-color:#52758D;}
    [data-testid="stSidebar"] .stButton button[kind="primary"] {background:#176B87;border-color:#3693A7;color:white;}
    [data-testid="stSidebar"] [data-testid="stExpander"] {border-color:#36536D;}
    [data-testid="stSidebar"] summary {background:#24455F!important;color:#E4ECF4!important;}
    .desk-brand {padding:.3rem 0 1.4rem;border-bottom:1px solid #36536D;margin-bottom:1rem;}
    .desk-brand strong {display:block;font-size:1.3rem;color:white;letter-spacing:.08em;}
    .desk-brand span {font-size:.75rem;color:#A9C2D6;letter-spacing:.14em;}
    .research-ledger {border-top:3px solid var(--teal);padding:1rem 0 .4rem;margin:.5rem 0;}
    .research-ledger .eyebrow {font-size:.75rem;letter-spacing:.12em;color:var(--teal);}
    .research-ledger h2 {font-size:1.65rem!important;margin:.45rem 0!important;}
    .status-label {font-size:.75rem;color:#61788D;letter-spacing:.08em;margin-bottom:.5rem;}
    .status-value {font-weight:650;font-size:1rem;margin-bottom:.65rem;}
    .status-detail {font-size:.88rem;line-height:1.7;color:#496176;min-height:4.5rem;overflow-wrap:anywhere;}
    .stButton button,.stDownloadButton button {min-height:2.7rem;height:auto;white-space:normal;}
    button:focus-visible {outline:3px solid #54B4C9!important;outline-offset:2px;}
    [data-testid="stMain"] [data-testid="stMetricValue"] {font-variant-numeric:tabular-nums;}
    @media(max-width:760px) {
      [data-testid="stMainBlockContainer"] {padding:4.5rem 1rem 3rem;}
      [data-testid="stMain"] h1 {font-size:1.8rem;}
      [data-testid="stHorizontalBlock"] {flex-wrap:wrap;}
      [data-testid="stHorizontalBlock"]>[data-testid="stColumn"] {min-width:min(100%,260px);flex:1 1 260px;}
      .status-detail {min-height:0;}
    }
    @media(prefers-reduced-motion:reduce) {* {scroll-behavior:auto!important;}}
    </style>''', unsafe_allow_html=True)


def render_navigation(snapshot):
    s = st.session_state
    legacy = s.get('workspace', '')
    if legacy != s.get('_workspace_legacy', '') and legacy in LEGACY_ROUTES:
        s['workspace_route'] = LEGACY_ROUTES[legacy]
    s.setdefault('workspace_route', 'overview')
    route = s['workspace_route']
    if route not in ROUTES:
        route = s['workspace_route'] = 'overview'
    s['workspace'] = ROUTES[route].legacy
    s['_workspace_legacy'] = s['workspace']
    with st.sidebar:
        st.markdown('<div class="desk-brand"><span>CITYU · INVESTMENT RESEARCH</span><strong>投资研究工作台</strong></div>', unsafe_allow_html=True)
        route_button('研究总览', 'overview', 'nav_overview', type='primary' if route == 'overview' else 'secondary', width='stretch')
        with st.expander('完成研究', expanded=True):
            for key in ['prepare_data','eligibility','screen_candidates','risk_preview']:
                route_button(ROUTES[key].title, key, 'nav_'+key, type='primary' if route == key else 'secondary', width='stretch')
        with st.expander('数据工具与证据', expanded=ROUTES[route].group not in ['研究', '完成研究']):
            for key in ['downloads','returns_window','history_sources','rates_factors']:
                route_button(ROUTES[key].title, key, 'nav_'+key, type='primary' if route == key else 'secondary', width='stretch')
        st.selectbox('快速跳转至任意工具', list(ROUTES), key='workspace_route',
                     format_func=lambda key: ROUTES[key].group+' / '+ROUTES[key].title)
        st.caption('HKD 港币计价 · 美国 / 香港')
        st.caption('研究预览 · 最终选品与优化待开发')
    return route


def _demo():
    navigate('screen_candidates')
    st.session_state['cs_source'] = 'SYNTH 相关性与风险演示'


def render_overview(snapshot):
    page_header('研究总览', '从数据到投资组合研究', '查看当前进度，按提示完成下一项核对。所有结果均来自本次会话。')
    step = next_step(snapshot)
    st.markdown('<div class="research-ledger"><div class="eyebrow">现在建议 / NEXT ACTION</div><h2>'+escape(ROUTES[step.route].title)+'</h2></div>', unsafe_allow_html=True)
    status_band(step)
    if snapshot.daily and snapshot.candidates.tone != 'ready':
        st.warning('需要月度准备：当前版本包含日线，先核对月末端点、港币换算与时间证据；不能只改频率标签。')
        route_button('核对资格与月度准备', 'eligibility', 'overview_daily_check')
    route_button('前往'+ROUTES[step.route].title.removeprefix('01 ').removeprefix('02 ').removeprefix('03 ').removeprefix('04 '),
                 step.route, 'overview_next', type='primary')
    st.subheader('本次研究档案')
    for col, status in zip(st.columns(4), [snapshot.data,snapshot.candidates,snapshot.target,snapshot.risk]):
        with col, st.container(border=True):
            st.markdown(f'<div class="status-label">{escape(status.label)}</div><div class="status-value">{STATUS_LABELS[status.tone]}</div><div class="status-detail">{escape(status.detail)}</div>', unsafe_allow_html=True)
            route_button('查看'+status.label, status.route, 'card_'+status.code, width='stretch')
    st.subheader('第一次使用')
    st.write('准备数据 → 核对资格 → 筛选候选 → 收益与风险。每一步的结果和证据都可单独检查，侧栏可随时跳转。')
    with st.expander('没有资料？先试用人工演示', expanded=True):
        st.write('使用 100 项人工产品体验筛选与相关性分析。演示不会保存到你的数据版本，也不代表市场表现。')
        st.button('试用人工演示', key='overview_demo', on_click=_demo)
