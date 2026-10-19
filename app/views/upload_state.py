"""Session-local upload copies survive workflow navigation, scoped by widget epoch."""
from io import BytesIO
import streamlit as st


def _changed(slot, key):
    if st.session_state.get(key) is None:
        st.session_state.setdefault('_research_uploads', {}).pop(slot, None)


def _clear(slot):
    st.session_state.setdefault('_research_uploads', {}).pop(slot, None)


def research_upload(title, *, type, key, slot, scope=None):
    cache = st.session_state.setdefault('_research_uploads', {})
    uploaded = st.file_uploader(title, type=type, key=key, on_change=_changed, args=(slot, key))
    if uploaded is not None:
        cache[slot] = (key, uploaded.name, uploaded.getvalue(), scope)
        return uploaded
    saved = cache.get(slot)
    if saved is None or saved[0] != key or saved[3] != scope:
        return None
    st.caption(f'本次研究已保留：{saved[1]}。可重新上传替换，或清除已保留文件。')
    st.button('清除已保留文件', key='clear_retained_'+slot, on_click=_clear, args=(slot,))
    file = BytesIO(saved[2])
    file.name = saved[1]
    return file
