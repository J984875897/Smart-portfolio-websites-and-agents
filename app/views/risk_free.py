"""Inspect declared cash proxy evidence; calculation belongs to the core."""
from io import BytesIO
import hashlib
import json
import pandas as pd
import streamlit as st
from portfolio.data import read_file
from portfolio.data.risk_free import risk_free_monthly, QUOTE_FIELDS
from portfolio.data.risk_free_samples import sample_risk_free_quotes, CASES
from app.views.hkd_returns import READ_ERRORS

REASONS = {
    'ok': '通过', 'missing_quote': '缺少本月指定报价', 'ambiguous_quote': '同月存在多条报价',
    'invalid_date': '存在无效日期', 'invalid_period_label': '期间标签不是自然月末',
    'period_not_complete_at_decision': '决策时点本月尚未结束',
    'quote_after_start': '观察报价晚于月初锚点', 'stale_quote': '观察报价超过七天陈旧阈值',
    'availability_after_start': '当前报价版本在月初之后才可得',
    'not_available_at_decision': '决策时点报价尚不可得',
    'availability_before_quote': '可得时点早于观察时点',
    'invalid_currency': '币种不是港币 HKD', 'invalid_benchmark': '不是指定 HKAB HIBOR 基准',
    'invalid_tenor': '期限不是一个月', 'invalid_day_count': '计息基础不是 ACT/365F',
    'invalid_compounding': '计息方式不是单利', 'missing_source_name': '缺少来源名称',
    'invalid_quote_at': '观察时点格式或时区无效', 'invalid_available_at': '可得时点格式或时区无效',
    'invalid_quote_percent': '年化百分数报价无效', 'invalid_rf_hkd': '代理收益超出合法范围',
}


def reason_text(value):
    return '；'.join(REASONS.get(code, '证据不符合规则（详见完整证据）') for code in str(value).split(';'))


def render():
    s = st.session_state
    s.setdefault('rf_result', None)
    from .page_chrome import tool_header
    with tool_header('利率与因子', '港币利率查验：核对月度现金收益代理与声明可得性；因子下载由相关工具进入。', 'rf_result',
                [('因子与官方汇率', 'reference_downloads'), ('返回资格中心', 'eligibility')]):
        st.warning('HIBOR 含银行信用与流动性风险；这是自然月单利现金收益近似，不是真正零风险资产或可投资存款承诺。查验只核对声明证据，不认证真实历史来源，不能据此声称已完成组合估计、Sharpe 或回测。')
        mode = st.radio('报价输入', ['人工测试案例', '上传报价文件'], key='rf_mode', horizontal=True,persist_state='session')
        case = None
        if mode == '人工测试案例':
            case = st.selectbox('人工报价案例', CASES, key='rf_case',persist_state='session')
            st.info('SYNTH 人工合成报价：仅覆盖 2024 年 1–3 月，年化报价 3.65%。与已保存导入数据隔离，不代表真实产品或真实历史；扩大窗口会出现缺月。')
        left, middle, right = st.columns(3)
        with left:
            end = st.text_input('结束月份（YYYY-MM）', '2024-03', key='rf_end',persist_state='session')
        with middle:
            months = st.number_input('窗口月数', min_value=1, max_value=600, value=3, step=1, key='rf_months',persist_state='session')
        with right:
            decision = st.text_input('决策时点（香港时间，ISO，必须 +08:00）', '2024-03-31T16:00:00+08:00', key='rf_decision',persist_state='session')
        payload, filename, sheet = b'', '', 0
        upload = None
        error = None
        if mode == '上传报价文件':
            from .upload_state import research_upload
            upload = research_upload('选择报价 CSV 或 XLSX', type=['csv', 'xlsx'], key='rf_upload', slot='rf_upload', scope=mode)
            if upload is not None:
                payload, filename = upload.getvalue(), upload.name
        # Clear old output before parsing an edited file, including broken workbooks.
        source_token = sample_risk_free_quotes(case).to_csv(index=False) if case else ''
        preliminary = repr((mode, case, end, months, decision, payload, filename, source_token))
        if s.get('rf_input_token') != preliminary:
            s['rf_result'] = None
        s['rf_input_token'] = preliminary
        quotes = None
        try:
            if mode == '人工测试案例':
                quotes = sample_risk_free_quotes(case)
            elif upload is not None:
                if filename.lower().endswith('.xlsx'):
                    sheets = pd.ExcelFile(BytesIO(payload), engine='openpyxl').sheet_names
                    if s.get('rf_sheet') not in sheets:
                        s.pop('rf_sheet', None)
                    sheet = st.selectbox('报价 Excel 工作表', sheets, key='rf_sheet',persist_state='session')
                if s.get('rf_parsed_sheet') != sheet:
                    s['rf_result'] = None
                s['rf_parsed_sheet'] = sheet
                quotes = read_file(payload, filename=filename, sheet_name=sheet)
                st.caption(f'报价来源：{filename} · 工作表 {sheet} · {len(quotes)} 行；原字节、SHA-256 与物理行证据交给核心查验。')
        except READ_ERRORS as exc:
            error = f'报价文件无法读取：{exc}。请核对格式、编码和工作表。'
        token = hashlib.sha256(repr((preliminary, sheet)).encode()).hexdigest()
        if s.get('rf_fingerprint') != token or error:
            s['rf_result'] = None
        s['rf_fingerprint'] = token
        with st.expander('口径说明、模板与人工样例'):
            st.markdown("""报价 `3.65` 表示年化 **3.65%**；期间收益采用单利，按自然月实际天数与固定 365 天年基准换算，闰年仍用 365。自然月只是研究近似，真实存款期限、起息与假日调整可能不同。

    每期从上一月末香港 16:00 至本月末香港 16:00。观察报价及当前版本的最晚可得时点都必须不晚于期初锚点，观察报价最多早于锚点七天；期末也必须不晚于决策时点。可得时间由导入者声明，不能以今天下载时间代替历史证据。

    CSV / XLSX 每个目标月末恰好一行。必需列：`date, quote_at, available_at, quote_percent, currency, benchmark, tenor, day_count, compounding, source_name`。date 用 YYYY-MM-DD 自然月末；quote_at 与 available_at 用带时区 ISO 时间（例如 +08:00）。固定口径：`HKD / HKAB_HIBOR / 1M / ACT/365F / simple`；source_name 填可追溯来源。缺月、多行或错误口径会阻止该月。

    [HKMA HIBOR 报价单位说明](https://apidocs.hkma.gov.hk/documentation/market-data-and-statistics/monthly-statistical-bulletin/er-ir/hk-interbank-ir-daily/) · [TMA 计息基础说明](https://www.tma.org.hk/PubFile/TMACode.pdf)。HIBOR 含银行信用与流动性风险；声明查验通过不代表真实历史来源已认证，人工样例不能证明真实数据已可回测。""")
            st.download_button('下载报价 CSV 模板', pd.DataFrame(columns=QUOTE_FIELDS).to_csv(index=False).encode('utf-8-sig'), file_name='risk_free_template.csv', key='rf_template')
            st.download_button('下载 SYNTH 人工完整报价 CSV', sample_risk_free_quotes().to_csv(index=False).encode('utf-8-sig'), file_name='SYNTH_risk_free_quotes.csv', key='rf_sample')
        if error:
            st.error(error)
        if st.button('查验港币利率代理', key='rf_compute', type='primary', disabled=quotes is None or error is not None):
            s['rf_result'] = None
            try:
                if not decision.endswith('+08:00'):
                    raise ValueError('请显式填写香港时间 +08:00')
                s['rf_result'] = risk_free_monthly(quotes, end_month=end, decision_at=decision, months=int(months))
                s['rf_result_fingerprint'] = token
            except READ_ERRORS as exc:
                st.error(f'无法查验港币利率代理：{exc}')
        result = s['rf_result']
        if result is None or s.get('rf_result_fingerprint') != token:
            return
        report = result.report
        st.subheader('港币月度代理摘要')
        st.caption(f'可用月份 {int((report.status == "valid").sum())} / {len(report)} · 序列状态：{"可用" if result.available else "不可用"} · {result.window_start} 至 {result.window_end} · HKD / 月度')
        shown = pd.DataFrame({'期间': report.date, '状态': report.status.map({'valid': '有效', 'blocked': '阻止'}),
                              '期间天数': report.days,
                              '年化报价（%）': report.get('quote_quote_percent', pd.Series(index=report.index, dtype=float)).map(lambda x: '未知年化报价' if pd.isna(x) else f'{x}%'),
                              '月度港币代理收益': report.rf_hkd.map(lambda x: '不可用' if pd.isna(x) else f'{x:.2%}'),
                              '说明': report.reason.map(reason_text)})
        st.dataframe(shown, hide_index=True, width='stretch')
        st.caption('缺失或阻止月份保持不可用，不填零、不使用美元利率替代。可用仅表示声明证据通过；未来统计应按同月日期严格连接。')
        with st.expander('完整证据与结果下载'):
            evidence = report.copy(); evidence.attrs = {}
            evidence['quote_evidence'] = evidence.quote_evidence.map(lambda value: json.dumps(value, ensure_ascii=False, default=str))
            for column in evidence.select_dtypes(include=['object', 'str']).columns:
                evidence[column] = evidence[column].map(lambda value: '' if value is None else str(value))
            st.caption('rf_hkd 保留原始期间收益小数，0.0031 表示 0.31%；quote_percent 是年化百分数。英文规则代码与来源证据完整保留。')
            st.dataframe(evidence, hide_index=True, width='stretch')
            st.download_button('下载利率查验报告 CSV', report.to_csv(index=False).encode('utf-8-sig'), file_name='risk_free_report.csv', mime='text/csv', key='rf_report_download')
            st.download_button('下载港币代理收益 CSV', result.series.to_csv().encode('utf-8-sig'), file_name='rf_hkd.csv', mime='text/csv', key='rf_series_download')
