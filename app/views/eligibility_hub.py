"""Guide users to existing checks; this hub does not calculate eligibility."""
import streamlit as st
from .page_chrome import page_header
from .workspace_state import workspace_snapshot
from .workspace_shell import route_button

CHECKS = [
    ('核对日线月度', 'daily_monthly', '日线 → 月度', '检查交易日、月末端点和调整口径，预览原币月收益。'),
    ('核对港币收益', 'returns_window', '原币 → 港币', '核对月度收益与起止汇率；日线价格可使用“日线港币查验”。'),
    ('核对共同窗口', 'alignment', '固定 60 月', '检查缺月、逐月时间证据和同一决策时点。'),
    ('核对历史资格', 'history_sources', '来源与时间', '核对数据版本何时取得；人工声明不等于独立认证。'),
]


def render():
    snapshot = workspace_snapshot(st.session_state)
    page_header('完成研究 / 02', '核对资格', '按数据缺口选择核对工具，再返回候选筛选。每项工具独立出具诊断，结果不会自动合并成合格候选。',
                snapshot.candidates)
    if snapshot.daily:
        st.warning('需要月度准备：当前含日线资料。现有日线工具仅供预览，尚未自动接入候选筛选；不要只修改频率标签。')
    st.subheader('按缺口选择核对工具')
    for label, route, title, detail in CHECKS:
        with st.container(border=True):
            st.subheader(title)
            st.write(detail)
            route_button(label, route, 'eligibility_'+route)
    route_button('核对日线港币', 'daily_hkd', 'eligibility_daily_hkd')
    st.divider()
    st.info('月度与结构证据齐备后，到“03 筛选候选”重新查验。工具中的通过数量不代表正式候选 N。')
    route_button('前往筛选候选', 'screen_candidates', 'eligibility_screen')
