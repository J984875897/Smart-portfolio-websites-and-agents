"""Guided, offline daily completeness and original-currency preview."""
import hashlib
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st
from portfolio.data.daily_monthly import aggregate_daily_prices
from portfolio.data.monthly_cache import cached_monthly_prices
from portfolio.data.snapshots import list_runs, load_snapshot
from portfolio.data.trading_calendar import trading_schedule

SYMBOLS = ['SPY', 'AAPL', '0700.HK', '2800.HK', 'AGG', 'GLD']
ERRORS = (ValueError, OSError, KeyError, TypeError, UnicodeError)
REASONS = {'ok': '通过本步查验', 'missing_price': '缺少预期交易日报价',
           'invalid_value': '收益计算超出有限数值范围',
           'invalid_price': '价格无效', 'duplicate_date': '同日出现重复报价',
           'unexpected_session': '出现非交易日报价', 'invalid_date': '日期无效',
           'month_not_mature': '月份尚未结束，不能预览整月收益',
           'unconfirmed_adjusted_price': '尚未确认复权价格口径',
           'source_not_success': '缓存来源仅部分可用，阻止全部收益'}


def reason_text(reason):
    if reason.startswith('previous_month:'):
        return '前月：' + reason_text(reason.split(':', 1)[1])
    return '；'.join(REASONS.get(part, part) for part in reason.split(';'))


def sample_prices(symbol, start_month, end_month, case):
    # Validate user month strings through the core before constructing a schedule.
    aggregate_daily_prices(pd.DataFrame(columns=['date', 'adj_close']), symbol=symbol,
                           start_month=start_month, end_month=end_month)
    first = pd.Period(start_month, freq='M') - 1
    last = pd.Period(end_month, freq='M')
    schedule = trading_schedule('XHKG' if symbol.endswith('.HK') else 'XNYS',
                                first.start_time.strftime('%Y-%m-%d'),
                                (last + 1).start_time.strftime('%Y-%m-%d'))
    frame = schedule[['date']].copy()
    frame['adj_close'] = frame.date.map(lambda day: 100 * 1.1 ** (pd.Period(day[:7], freq='M').ordinal - first.ordinal))
    target = frame.index[frame.date.str.startswith(end_month)]
    if len(target):
        if case == '缺最后交易日':
            frame = frame.drop(target[-1])
        elif case == '缺月中交易日':
            frame = frame.drop(target[len(target)//2])
        elif case == '重复日期':
            frame = pd.concat([frame, frame.loc[[target[0]]]], ignore_index=True)
    frame.attrs['source_name'] = '人工案例（合成价格） / ' + case
    return frame


def render():
    s = st.session_state
    s.setdefault('dm_result', None)
    from .page_chrome import tool_header
    with tool_header('日线月度查验', '按来源、产品与月份、查验结果的顺序，核对交易日并预览月度原币收益。', 'dm_result',
                [('核对日线港币', 'daily_hkd'), ('返回资格中心', 'eligibility')]):
        st.subheader('1 选择来源')
        mode = st.radio('数据来源', ['人工案例', '已下载缓存'], key='dm_mode', horizontal=True,persist_state='session')
        root = Path(os.environ.get('PORTFOLIO_DOWNLOADS_ROOT', str(Path(__file__).resolve().parents[2]/'data/downloads')))
        case, run, manifest, error = '', None, None, None
        symbols = SYMBOLS
        if mode == '人工案例':
            case = st.selectbox('人工案例', ['完整报价', '缺最后交易日', '缺月中交易日', '重复日期'], key='dm_case',persist_state='session')
            st.info('人工合成案例：前月每日 100、首个目标月每日 110；每个后续月递增 10%。默认检查 2024 年 12 月与 2025 年 1 月，修改月份会生成对应交易日。')
        else:
            manifests = {}
            try:
                for rid in list_runs(root):
                    try:
                        candidate = load_snapshot(root, rid)
                        if candidate['schema_version'] == 1:
                            manifests[rid] = candidate
                    except ERRORS:
                        st.error(f'缓存记录 {rid} 损坏或无法验证，请到「下载与缓存」检查。')
                run = st.selectbox('已有缓存版本', list(manifests), key='dm_run',persist_state='session')
                manifest = manifests.get(run)
                symbols = [i['symbol'] for i in manifest['items'] if i['symbol'] in SYMBOLS and i['status'] in {'success', 'partial'} and i['raw_file']] if manifest else []
                if not symbols:
                    error = '没有可诊断的价格原始缓存。请先到「下载与缓存」显式下载。'
            except ERRORS:
                error = '缓存目录无法读取，请检查下载目录。'
            st.caption('本页只读缓存，不下载、不自动提交。查看 2025 年 1 月收益，请下载完整 2024-12-01 至 2025-02-01（不含结束日）。')
        st.subheader('2 产品与月份')
        if s.get('dm_symbol') not in symbols:
            s.pop('dm_symbol', None)
        symbol = st.selectbox('价格产品代码', symbols, key='dm_symbol',persist_state='session')
        start = st.text_input('起始目标月份（YYYY-MM）', value='2025-01', key='dm_start_month',persist_state='session')
        end = st.text_input('结束目标月份（YYYY-MM，包含）', value='2025-01', key='dm_end_month',persist_state='session')
        confirmed = st.checkbox('我已核实复权价格包含分配与拆股调整', key='dm_confirm',persist_state='session')
        st.caption('确认口径后才输出收益；不会重复加入分红。USD 保持美元原币，未换算为港币。')
        token = hashlib.sha256(repr((str(root.resolve()), mode, case, run, manifest, symbol, start, end, confirmed)).encode()).hexdigest()
        if s.get('dm_token') != token:
            s['dm_result'] = None
        s['dm_token'] = token
        # Re-read real evidence on every rerender, including download interactions.
        verified = None
        if manifest and symbol:
            try:
                verified = cached_monthly_prices(root, run, symbol, start_month=start, end_month=end, confirmed=confirmed)
            except ERRORS:
                error = '缓存或月份无法验证，已撤下结果与下载。请检查原始文件、来源身份和月份格式。'
        if error:
            s['dm_result'] = None
            st.error(error)
        if st.button('查验日线并计算月收益', key='dm_compute', type='primary', disabled=bool(error) or not symbol):
            s['dm_result'] = None
            try:
                s['dm_result'] = verified if mode == '已下载缓存' else aggregate_daily_prices(
                    sample_prices(symbol, start, end, case), symbol=symbol, start_month=start, end_month=end, confirmed=confirmed)
            except ERRORS:
                st.error('无法查验：月份须为 2015-01 至 2026-12 的 YYYY-MM，且起月不能晚于结束月。')
        st.subheader('3 查验结果')
        result = s['dm_result']
        if result is None:
            st.info('完成前两步后，点击「查验日线并计算月收益」。')
            return
        st.metric('目标月数', len(result.returns))
        st.metric('可预览收益月数', int(result.returns.local_return.notna().sum()))
        st.caption(f'原币：{result.metadata["currency"]}。这是当前版本价格预览，尚不具备历史可得资格。空白表示被阻止，不能当作零收益。')
        monthly = result.monthly
        st.dataframe(pd.DataFrame({'月份': monthly.month, '自然月末': monthly.date,
            '预期最后交易日': monthly.expected_end_date, '最后观察日': monthly.last_observed_date,
            '有效月末复权价格': monthly.end_price, '查验说明': monthly.reason.map(reason_text)}), hide_index=True)
        rows = result.returns
        st.dataframe(pd.DataFrame({'目标月末': rows.date, '原币收益（%）': rows.local_return * 100,
                                   '逐月查验说明': rows.reason.map(reason_text)}), hide_index=True)
        with st.expander('逐日明细与来源证据'):
            st.caption('CSV 保留完整字段及小数收益（0.1 表示 10%）；日历收市时间不代表供应商发布时间。')
            for name, frame, label in [('sessions', result.sessions, '逐日查验'), ('monthly', monthly, '月末锚点'), ('returns', rows, '原币收益')]:
                st.write(label)
                display = frame.copy()
                display.attrs = {}
                st.dataframe(display, hide_index=True)
                st.download_button('下载' + label + ' CSV', frame.to_csv(index=False).encode('utf-8-sig'),
                                   file_name=name+'.csv', key='dm_download_'+name, mime='text/csv')
            st.json(result.metadata)
            st.download_button('下载来源证据 JSON', json.dumps(result.metadata, ensure_ascii=False, indent=2),
                               file_name='daily_monthly_metadata.json', key='dm_download_metadata', mime='application/json')
