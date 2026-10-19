"""Inspectable S03-B UI; all window calculations belong to the alignment core."""
from io import BytesIO
from pathlib import Path
import hashlib
import json
import pandas as pd
import streamlit as st
from portfolio.data.alignment import align_monthly, TIMING_FIELDS
from portfolio.data.alignment_samples import sample_alignment_inputs
from portfolio.data import read_file
from app.views.hkd_returns import fingerprint, READ_ERRORS

NAMES = {'HKD_COMPLETE': '港币历史完整', 'USD_COMPLETE': '美元历史完整',
         'MISSING_MIDDLE': '中间缺月', 'SHORT_HISTORY': '仅59个月', 'MISSING_END_FX': '缺期末汇率'}
REASONS = {'ok': '通过', 'missing_return': '缺少本月收益', 'missing_timing': '缺少时间证据',
           'missing_fx_end': '缺少期末汇率', 'not_available_at_decision': '决策时点尚不可得',
           'period_not_complete_at_decision': '市场期间尚未结束',
           'window_start_history_insufficient': '窗口起始历史不足'}


def reason_text(value):
    return '；'.join(REASONS.get(x, '时间或收益证据不符合规则（详见完整证据）') for x in str(value).split(';'))


def render():
    s = st.session_state
    s.setdefault('alignment_result', None)
    from .page_chrome import tool_header
    with tool_header('共同窗口查验', '核对逐月时间证据与固定 60 月窗口，定位缺月及不可得资料。', 'alignment_result',
                [('返回港币收益核对', 'returns_window'), ('返回资格中心', 'eligibility'), ('前往筛选候选', 'screen_candidates')]):
        st.warning('本页查验声明的时间逻辑，不认证真实历史可得性。通过数量不是 S05 正式候选 N；月度时间检查仍不足以完成组合估计或回测，请到「港币利率查验」独立核对现金收益代理；真实来源仍需认证。')
        mode = st.radio('收益输入', ['上一页当前港币对照', '人工测试案例'], key='alignment_mode', horizontal=True,persist_state='session')
        reconciliation = None
        timing = pd.DataFrame(columns=TIMING_FIELDS)
        assets = []
        names = dict(NAMES)
        source_token = ''
        if mode == '人工测试案例':
            reconciliation, timing, assets = sample_alignment_inputs()
            source_token = repr(assets) + reconciliation.to_csv(index=False) + timing.to_csv(index=False)
            st.info('人工五资产案例：港币完整、美元完整、中间缺月、仅 59 月、缺期末汇率。全部是合成输入，不是真实产品或真实历史；与已保存导入数据隔离。2025-01-31 香港 17:00 通过 1 资产，2025-02-01 香港 06:00 通过 2 资产。')
        else:
            result = s.get('hkd_result')
            origin = s.get('hkd_result_origin')
            if result is None or origin is None:
                st.info('请先到「港币收益查验」生成当前有效对照，再上传各资产每月时间证据。不会根据收益日期猜测时间。')
            elif not (result.reconciliation['status'] == 'valid').any():
                s['alignment_result'] = None
                st.info('上一页没有有效港币收益。请先核实月度总收益口径、复权确认和起止汇率，修正阻止项后重新生成对照。')
            elif origin['mode'] == '当前已保存数据' and origin['bundle_fingerprint'] != fingerprint(s['bundle']):
                st.warning('已保存源表内容发生变化，上一页港币对照已过期。请重新生成对照。')
            elif origin['input_fingerprint'] != s.get('hkd_fingerprint'):
                st.warning('上一页输入发生变化，请重新生成港币对照。')
            else:
                reconciliation = result.reconciliation
                source_token = repr(origin) + reconciliation.to_csv(index=False)
                assets = sorted(reconciliation.asset_id.astype(str).unique())
                if origin['mode'] == '人工测试案例':
                    st.info('上一页人工港币对照：这是合成输入，不是真实产品或真实历史。此对照只有短期案例，不代表 60 月完整历史。')
                else:
                    assets = sorted(set(s['bundle'].assets.asset_id.astype(str)) | set(assets))
                    names = dict(zip(s['bundle'].assets.asset_id.astype(str), s['bundle'].assets['name']))
                    st.caption('来源：上一页当前已保存数据的有效港币对照；与源表内容绑定。')
        left, right = st.columns(2)
        with left:
            end = st.text_input('结束月份（YYYY-MM）', '2025-01', key='alignment_end',persist_state='session')
        with right:
            decision = st.text_input('决策时点（香港时间，ISO +08:00）', '2025-01-31T17:00:00+08:00', key='alignment_decision',persist_state='session')
        if s.get('alignment_previous_mode') != mode:
            # Assignment overrides the prior keyed selection restored by the browser.
            # Deleting it alone lets the frontend upload choice win on the same widget.
            s['alignment_timing_mode'] = '人工时间证据' if mode == '人工测试案例' else '上传时间证据'
        s['alignment_previous_mode'] = mode
        timing_choices = ['人工时间证据', '上传时间证据'] if mode == '人工测试案例' else ['上传时间证据']
        if s.get('alignment_timing_mode') not in timing_choices:
            s.pop('alignment_timing_mode', None)
        timing_mode = st.selectbox('时间证据输入', timing_choices, key='alignment_timing_mode',persist_state='session')
        payload, filename, sheet = b'', '', 0
        error = None
        if timing_mode == '上传时间证据':
            timing = pd.DataFrame(columns=TIMING_FIELDS)
            from .upload_state import research_upload
            upload = research_upload('选择时间证据 CSV 或 XLSX', type=['csv', 'xlsx'], key='alignment_upload', slot='alignment_upload', scope=(mode, source_token))
            try:
                if upload is not None:
                    payload, filename = upload.getvalue(), upload.name
                    if filename.lower().endswith('.xlsx'):
                        sheets = pd.ExcelFile(BytesIO(payload), engine='openpyxl').sheet_names
                        if s.get('alignment_sheet') not in sheets:
                            s.pop('alignment_sheet', None)
                        sheet = st.selectbox('时间证据 Excel 工作表', sheets, key='alignment_sheet',persist_state='session')
                    timing = read_file(payload, filename=filename, sheet_name=sheet)
                    st.caption(f'时间来源：{filename} · 工作表 {sheet} · {len(timing)} 行；完整原表交给核心，文件 SHA-256、工作表和物理行随输出保留。')
            except READ_ERRORS as exc:
                error = f'时间证据文件无法读取：{exc}。请核对格式、编码和工作表。'
        token = hashlib.sha256(repr((mode, source_token, end, decision, timing_mode, payload, filename, sheet)).encode()).hexdigest()
        if s.get('alignment_fingerprint') != token or error:
            s['alignment_result'] = None
        s['alignment_fingerprint'] = token
        with st.expander('时间证据填写说明和模板'):
            st.download_button('下载时间证据 CSV 模板', pd.DataFrame(columns=TIMING_FIELDS).to_csv(index=False).encode('utf-8-sig'), file_name='timing_template.csv', key='alignment_template')
            st.markdown((Path(__file__).resolve().parents[2] / 'docs/data/alignment_format.md').read_text())
        if error:
            st.error(error)
        if st.button('查验共同窗口', key='alignment_compute', type='primary', disabled=reconciliation is None or error is not None):
            s['alignment_result'] = None
            try:
                if not decision.endswith('+08:00'):
                    raise ValueError('请显式填写香港时间 +08:00')
                s['alignment_result'] = align_monthly(reconciliation, timing, asset_ids=assets, end_month=end, decision_at=decision)
                s['alignment_result_fingerprint'] = token
            except READ_ERRORS as exc:
                st.error(f'无法查验共同窗口：{exc}')
        result = s['alignment_result']
        if result is None or s.get('alignment_result_fingerprint') != token:
            return
        st.subheader('资产共同窗口摘要')
        eligible = len(result.matrix.columns)
        st.caption(f'{result.window_start} 至 {result.window_end} · 固定 {len(result.matrix)} 月 · 通过 {eligible} / {len(result.report)} 资产 · 决策 {decision}（香港时间）')
        report = result.report
        shown = pd.DataFrame({'产品名称': report.asset_id.map(names).fillna(report.asset_id), '资产标识': report.asset_id,
                              '窗口状态': report.status.map({'eligible': '通过', 'excluded': '排除'}),
                              '有效月数': report.valid_months, '缺失或阻止月数': report.missing_months,
                              '说明': report.reason.map(reason_text)})
        st.dataframe(shown, hide_index=True, width='stretch')
        st.caption('缺失和阻止行保留原因及原始证据，不填零，不用较早月份替补。真实 0% 可以有效；此处通过数量不是正式候选 N。')
        st.subheader('月份状态')
        coverage = result.coverage
        compact = pd.DataFrame({'资产标识': coverage.asset_id, '期间': coverage.date,
                                '状态': coverage.status.map({'valid': '有效', 'blocked': '阻止'}),
                                '说明': coverage.reason.map(reason_text), '原始换算值（小数，阻止行不可用）': coverage.hkd_return})
        st.dataframe(compact, hide_index=True, width='stretch')
        with st.expander('完整证据、固定矩阵与下载'):
            st.caption('矩阵只含完整通过资产，固定 60 行；小数 0.01 表示 1%。完整证据保留原始收益、时间、来源和英文规则代码；阻止行数值不是有效收益。')
            shown = coverage.copy(); shown.attrs = {}
            for column in ['reconciliation_evidence', 'timing_evidence']:
                shown[column] = shown[column].map(lambda value: json.dumps(value, ensure_ascii=False, default=str))
            for column in shown.select_dtypes(include=['object', 'str']).columns:
                shown[column] = shown[column].map(lambda value: '' if value is None else str(value))
            st.dataframe(shown, hide_index=True, width='stretch')
            st.dataframe(result.matrix, width='stretch')
            for name, frame, index in [('报告', report, False), ('覆盖证据', coverage, False), ('矩阵', result.matrix, True)]:
                st.download_button('下载共同窗口' + name + ' CSV', frame.to_csv(index=index).encode('utf-8-sig'), file_name='alignment_' + name + '.csv', mime='text/csv', key='alignment_download_' + name)
