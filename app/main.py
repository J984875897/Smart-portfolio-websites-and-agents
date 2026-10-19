from pathlib import Path
import importlib
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from portfolio.data.contracts import DataBundle
from app.views.workspace_state import workspace_snapshot
from app.views.workspace_shell import ROUTES, apply_style, render_navigation, render_overview

st.set_page_config(page_title='投资研究工作台', page_icon='📑', layout='wide', initial_sidebar_state='auto')
st.session_state.setdefault('bundle', DataBundle())
st.session_state.setdefault('bundle_version', 'empty')
apply_style()
snapshot = workspace_snapshot(st.session_state)
route = render_navigation(snapshot)
if route == 'overview':
    render_overview(snapshot)
else:
    module = importlib.import_module('app.views.'+ROUTES[route].module)
    if route in ('screen_candidates', 'risk_preview'):
        module.render(render_mode=route)
    else:
        module.render()
