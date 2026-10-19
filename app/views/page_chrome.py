"""Shared presentation, with no business actions or calculations."""
from contextlib import contextmanager
import streamlit as st
from .workspace_state import WorkspaceStatus

STATUS_LABELS = {'ready': '可继续', 'review': '待核对', 'blocked': '已阻止', 'input': '待输入'}


def status_band(status: WorkspaceStatus):
    show = {'ready': st.success, 'review': st.warning, 'blocked': st.error, 'input': st.info}[status.tone]
    show(f'{STATUS_LABELS[status.tone]} · {status.detail}')


def page_header(stage, title, purpose, status=None):
    if stage != '研究总览':
        from .workspace_shell import route_button
        route_button('← 研究总览', 'overview', 'page_back_overview')
    st.caption(f'投资组合研究 / {stage}')
    st.title(title)
    st.write(purpose)
    if status is not None:
        status_band(status)


def section_heading(title, detail=None):
    st.subheader(title)
    if detail:
        st.caption(detail)


@contextmanager
def live_status(status_factory):
    """Reserve header space; read state after this run's actions and invalidation."""
    slot = st.empty()
    try:
        yield
    finally:
        with slot.container():
            status_band(status_factory())


@contextmanager
def tool_header(title, purpose, result_key=None, links=()):
    """Do not equate a diagnostic result or download binding with certification."""
    from .workspace_shell import route_button
    def current_status():
        result = st.session_state.get(result_key) if result_key else None
        return WorkspaceStatus('tool', title, 'review' if result is not None else 'input',
            '已有诊断记录；请核对当前输入与下方结果，历史来源资格仍需查验' if result is not None else '选择输入并执行本页操作；结果与证据将在下方显示', '')
    page_header('数据工具与证据', title, purpose)
    with live_status(current_status):
        if links:
            with st.expander('相关工具与下一步'):
                for label, route in links:
                    route_button(label, route, 'tool_'+title+'_'+route)
        section_heading('本页操作')
        yield
