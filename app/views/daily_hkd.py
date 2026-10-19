"""Three-step, read-only daily price and FX evidence preview."""
import hashlib
import json
import os
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile

import pandas as pd
import streamlit as st
from portfolio.data.daily_hkd import connect_daily_hkd
from portfolio.data.daily_hkd_samples import sample_daily_prices, sample_daily_fx
from portfolio.data.daily_monthly import aggregate_daily_prices
from portfolio.data.fx_cache import cached_daily_fx
from portfolio.data.importer import read_file
from portfolio.data.monthly_cache import cached_monthly_prices
from portfolio.data.snapshots import list_runs, load_snapshot
from app.views.daily_monthly import SYMBOLS, reason_text as price_reason

ERRORS = (ValueError, OSError, KeyError, TypeError, UnicodeError, BadZipFile, ImportError)
FX_REASONS = {'missing_month': '该月缺少汇率', 'stale_quote': '汇率超过最大年龄',
              'duplicate_date': '最新汇率日期重复', 'invalid_quote': '汇率数值无效',
              'invalid_currency': '币种必须为 USD', 'invalid_date': '汇率日期无效',
              'missing_source_name': '缺少汇率来源名称', 'unconfirmed_fx_unit': '尚未确认每美元兑港币口径',
              'source_not_success': '来源仅部分可用，禁止美元换算', 'ok': '通过查验'}


def reason_text(reason):
    pieces = []
    for part in reason.split(';'):
        if part.startswith(('fx_start:', 'fx_end:')):
            prefix, code = part.split(':', 1)
            pieces.append(('期初汇率：' if prefix == 'fx_start' else '期末汇率：') + FX_REASONS.get(code, code))
        else:
            pieces.append(FX_REASONS.get(part, price_reason(part)))
    return '；'.join(pieces)


def input_token(values):
    return hashlib.sha256(repr(values).encode()).hexdigest()


def read_fx_upload(data, filename, sheet):
    return read_file(data, filename=filename, sheet_name=sheet)


def _runs(root, kind):
    options = {}
    for rid in list_runs(root):
        manifest = load_snapshot(root, rid)
        items = manifest['items']
        if kind == 'price' and manifest['schema_version'] == 1 and any(i.get('symbol') in SYMBOLS for i in items):
            options[rid] = manifest
        elif kind == 'fx' and any(i.get('symbol') in {'HKD=X', 'HKMA_USDHKD'} for i in items):
            options[rid] = manifest
    return options


def _plain(frame):
    view = frame.copy()
    view.attrs = {}
    return view


def render():
    s = st.session_state
    s.setdefault('dh_result', None)
    from .page_chrome import tool_header
    with tool_header('日线港币查验', '先检查价格，再选择美元汇率与估值政策，最后计算港币收益预览。', 'dh_result',
                [('核对历史资格', 'history_sources'), ('返回资格中心', 'eligibility')]):
        base = Path(__file__).resolve().parents[2]
        price_root = Path(os.environ.get('PORTFOLIO_DOWNLOADS_ROOT', str(base/'data/downloads'))).resolve()
        reference_root = Path(os.environ.get('PORTFOLIO_REFERENCE_DOWNLOADS_ROOT', str(base/'data/reference_downloads'))).resolve()
        errors = []
        price_run = price_manifest = fx_run = fx_manifest = None
        fx_root = None
        verified_prices = fx_frame = None
        upload_identity = None
        st.subheader('1 价格来源与目标月份')
        price_mode = st.radio('价格来源', ['人工案例', '已下载缓存'], key='dh_price_mode', horizontal=True,persist_state='session')
        price_case = ''
        symbols = SYMBOLS
        if price_mode == '人工案例':
            price_case = st.selectbox('价格人工案例', ['完整报价', '缺最后交易日'], key='dh_price_case',persist_state='session')
            st.info('SYNTH 合成价格：前月每日 100，首个目标月每日 110，之后每月递增 10%。使用对应市场真实交易日。')
        else:
            try:
                runs = _runs(price_root, 'price')
                if s.get('dh_price_run') not in runs: s.pop('dh_price_run', None)
                price_run = st.selectbox('价格缓存版本', list(runs), key='dh_price_run',persist_state='session')
                price_manifest = runs.get(price_run)
                symbols = [i['symbol'] for i in price_manifest['items'] if i['symbol'] in SYMBOLS and i['status'] in {'success', 'partial'} and i.get('raw_file')] if price_manifest else []
                if not symbols: errors.append('没有可诊断的价格缓存，请先到「下载与缓存」显式下载。')
            except ERRORS:
                symbols = []
                errors.append('价格缓存损坏或目录无法读取，已撤下结果与下载。')
            st.caption('当前版本真实价格缓存；partial 只供诊断，不能升级为通过。')
        if s.get('dh_symbol') not in symbols: s.pop('dh_symbol', None)
        symbol = st.selectbox('价格产品代码', symbols, key='dh_symbol',persist_state='session')
        start = st.text_input('起始目标月份（YYYY-MM）', value='2025-01', key='dh_start_month',persist_state='session')
        end = st.text_input('结束目标月份（YYYY-MM，包含）', value='2025-01', key='dh_end_month',persist_state='session')
        price_confirm = st.checkbox('我已核实复权价格包含分配与拆股调整', key='dh_price_confirm',persist_state='session')
        st.subheader('2 美元汇率与估值政策')
        fx_mode = fx_case = provider = ''
        fx_confirm = False
        max_age = 7
        if symbol and symbol.endswith('.HK'):
            st.info('本产品原币为 HKD，换算汇率固定为 1，无需美元汇率确认。')
        else:
            fx_mode = st.radio('美元汇率来源', ['人工案例', '已下载缓存', 'CSV / XLSX 文件'], key='dh_fx_mode', horizontal=True,persist_state='session')
            if fx_mode == '人工案例':
                fx_case = st.selectbox('汇率人工案例', ['完整汇率', '缺期末月', '过旧', '重复末日'], key='dh_fx_case',persist_state='session')
                st.info('SYNTH 合成汇率：前月末 7.8，首个目标月末 7.9，之后每月增加 0.1 港币。')
            elif fx_mode == '已下载缓存':
                provider = st.selectbox('汇率缓存来源', ['HKMA 官方日线', 'Yahoo HKD=X 非官方日线'], key='dh_fx_provider',persist_state='session')
                fx_root = reference_root if provider.startswith('HKMA') else price_root
                try:
                    runs = {rid:m for rid,m in _runs(fx_root, 'fx').items() if m['schema_version'] == (2 if provider.startswith('HKMA') else 1)}
                    if s.get('dh_fx_run') not in runs: s.pop('dh_fx_run', None)
                    fx_run = st.selectbox('汇率缓存版本', list(runs), key='dh_fx_run',persist_state='session')
                    fx_manifest = runs.get(fx_run)
                    if fx_manifest is None: errors.append('所选来源没有可读取的汇率缓存，请先显式下载。')
                    else: fx_frame = cached_daily_fx(fx_root, fx_run)
                except ERRORS:
                    errors.append('汇率缓存或原始响应损坏，已撤下结果与下载。')
            else:
                from .upload_state import research_upload
                uploaded = research_upload('上传美元汇率 CSV 或 XLSX', type=['csv', 'xlsx'], key='dh_fx_upload', slot='dh_fx_upload', scope=(price_mode, price_case, price_run, symbol))
                if uploaded is None:
                    errors.append('请上传汇率文件，包含 date,currency,hkd_per_unit,source_name。')
                else:
                    raw = uploaded.getvalue()
                    sheet = 0
                    try:
                        if uploaded.name.lower().endswith('.xlsx'):
                            workbook = pd.ExcelFile(BytesIO(raw), engine='openpyxl')
                            sheet = st.selectbox('汇率工作表', workbook.sheet_names, key='dh_fx_sheet',persist_state='session')
                        upload_identity = (uploaded.name, raw, sheet)
                        fx_frame = read_fx_upload(raw, uploaded.name, sheet)
                    except ERRORS:
                        upload_identity = (uploaded.name, raw, s.get('dh_fx_sheet', 0))
                        errors.append('汇率文件无法读取，请检查格式、唯一列名与工作表。')
            fx_confirm = st.checkbox('我已核实汇率单位为每美元兑港币（HKD per USD），不求倒数', key='dh_fx_confirm',persist_state='session')
            max_age = st.number_input('汇率最大年龄（自然日，含等于）', min_value=0, max_value=7, value=7, step=1, key='dh_max_age',persist_state='session')
            with st.expander('汇率文件格式与模板'):
                st.write('必需列 date,currency,hkd_per_unit,source_name；日期 YYYY-MM-DD，币种 USD。示例为人工合成，不是官方数据。')
                st.download_button('下载两行合成汇率模板', 'date,currency,hkd_per_unit,source_name\n2024-12-31,USD,7.8,SYNTH example\n2025-01-31,USD,7.9,SYNTH example\n', file_name='synthetic_daily_fx.csv', key='dh_template', mime='text/csv')
        st.caption('最大 7 日为研究假设，非官方期限；价格与汇率可能异步估值。只检查同月端点，不补齐日历，不使用未来报价。')
        st.caption('输入组合：价格 ' + ('SYNTH 人工合成' if price_mode == '人工案例' else '当前版本真实缓存') + '；汇率 ' + ('HKD 固定 1' if symbol and symbol.endswith('.HK') else ('SYNTH 人工合成' if fx_mode == '人工案例' else ('本地文件（请核实真实/合成来源）' if fx_mode == 'CSV / XLSX 文件' else '当前版本真实缓存'))) + '。混合合成与真实输入仅为演示，不代表实际投资收益。')
        token = input_token((str(price_root), str(reference_root), price_mode, price_case, price_run, price_manifest,
                             symbol, start, end, price_confirm, fx_mode, fx_case, provider, str(fx_root), fx_run, fx_manifest,
                             upload_identity, fx_confirm, max_age))
        if s.get('dh_token') != token: s['dh_result'] = None
        s['dh_token'] = token
        if price_manifest and symbol:
            try:
                verified_prices = cached_monthly_prices(price_root, price_run, symbol, start_month=start, end_month=end, confirmed=price_confirm)
            except ERRORS:
                errors.append('价格缓存或月份无法验证，已撤下结果与下载。')
        if errors:
            s['dh_result'] = None
            for message in errors: st.error(message)
        if st.button('查验并计算港币收益', key='dh_compute', type='primary', disabled=bool(errors) or not symbol):
            s['dh_result'] = None
            try:
                prices = verified_prices if price_mode == '已下载缓存' else aggregate_daily_prices(sample_daily_prices(symbol, start, end, price_case), symbol=symbol, start_month=start, end_month=end, confirmed=price_confirm)
                if fx_mode == '人工案例': fx_frame = sample_daily_fx(start, end, fx_case)
                s['dh_result'] = connect_daily_hkd(prices, fx_frame, fx_confirmed=fx_confirm, max_age_days=int(max_age))
            except ERRORS:
                st.error('无法查验：请检查月份范围（2015-01 至 2026-12）、文件必需列、来源与单位。')
        st.subheader('3 港币收益与证据')
        result = s['dh_result']
        if result is None:
            st.info('完成前两步后，点击「查验并计算港币收益」。')
            return
        rows = result.reconciliation
        st.metric('目标月数', len(rows))
        st.metric('可预览港币月数', int(rows.hkd_return.notna().sum()))
        st.caption('当前版本估值预览，不具备历史可得资格（available_at 为空）。空白是阻止，不是零收益；不会送入共同窗口或计算候选数。')
        st.dataframe(pd.DataFrame({'目标月末': rows.date, '原币收益（%）': rows.local_return * 100,
            '汇率收益（%）': rows.fx_return * 100, '交叉项（%）': rows.cross_term * 100,
            '港币收益（%）': rows.hkd_return * 100, '查验说明': rows.reason.map(reason_text)}), hide_index=True)
        st.dataframe(pd.DataFrame({'目标月末': rows.date, '价格期初实际日': rows.price_start_observed_date,
            '价格期末实际日': rows.price_end_observed_date, '汇率期初实际日': rows.fx_start_observed_date,
            '汇率期末实际日': rows.fx_end_observed_date, '期初汇率年龄（日）': rows.fx_start_age_days,
            '期末汇率年龄（日）': rows.fx_end_age_days}), hide_index=True)
        with st.expander('原始诊断、端点与来源证据下载'):
            st.caption('CSV 收益保留小数（0.1 表示 10%）；观察日和下载时间不代表历史发布时间。')
            tables = [('sessions', result.prices.sessions, '价格逐日查验'), ('monthly', result.prices.monthly, '价格月末锚点'),
                      ('returns', result.prices.returns, '原币收益'), ('fx_observations', result.fx_observations, '汇率逐行诊断'),
                      ('fx_endpoints', result.fx_endpoints, '汇率月末端点'), ('reconciliation', rows, '港币收益对照')]
            for name, frame, label in tables:
                st.write(label)
                st.dataframe(_plain(frame), hide_index=True)
                st.download_button('下载' + label + ' CSV', frame.to_csv(index=False).encode('utf-8-sig'), file_name='daily_hkd_' + name + '.csv', key='dh_download_' + name, mime='text/csv')
            st.json(result.metadata)
            st.download_button('下载来源证据 JSON', json.dumps(result.metadata, ensure_ascii=False, indent=2, default=str), file_name='daily_hkd_metadata.json', key='dh_download_metadata', mime='application/json')
