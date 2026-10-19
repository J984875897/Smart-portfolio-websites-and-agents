"""Explicit public-chart updates and verified, offline snapshot inspection."""
from datetime import date
from io import BytesIO
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st
from portfolio.data.providers.yahoo import CATALOG
from portfolio.data.updates import run_update, validate_plan
from portfolio.data.snapshots import list_runs, load_snapshot, read_artifact, update_log
from app.views.data_center import set_source

ROOT = Path(__file__).resolve().parents[2]
STATUS = {'success':'成功（字段通过）', 'partial':'部分可用', 'unavailable':'不可用', 'cancelled':'已取消'}
REASONS = {'fields_verified':'来源字段检查通过', 'missing_invalid_prices_or_months':'价格缺失、无效或缺少月份',
           'timeout':'请求超时', 'transport_error':'连接失败', 'not_requested':'未请求', 'cancelled':'已取消',
           'rate_limited':'来源限流', 'http_error':'来源 HTTP 错误', 'parse_error':'来源解析失败',
           'currency_or_instrument_mismatch':'币种或产品身份不匹配', 'empty_prices':'无价格记录'}


def downloads_root():
    return Path(os.environ.get('PORTFOLIO_DOWNLOADS_ROOT', str(ROOT / 'data/downloads')))


def _items(manifest):
    rows = []
    for item in manifest['items']:
        rows.append({'代码':item['symbol'], '状态':STATUS[item['status']],
                     '原因':REASONS.get(item['reason'], '来源检查未通过'), '行数':item['rows'],
                     '首日':item.get('first_date', ''), '末日':item.get('last_date', ''),
                     '创建时间 UTC':manifest['created_utc']})
    st.caption(f"版本编号：{manifest['run_id']} · 原请求 {manifest['start']}（含）至 {manifest['end_exclusive']}（不含）")
    st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')


def _handoff(root, run_id, symbol):
    # A button callback executes before main.py instantiates the route selector.
    manifest = load_snapshot(root, run_id)
    item = next(i for i in manifest['items'] if i['symbol'] == symbol)
    if item['status'] != 'success' or symbol == 'HKD=X' or not item['import_file']:
        return
    payload = read_artifact(root, run_id, item['import_file'])
    s = st.session_state
    s.pop('upload', None)
    s.pop('upload_token', None)
    s['upload_generation'] = s.get('upload_generation', 0) + 1
    set_source(payload, f"{run_id}_{item['import_file']}")
    for field in ('asset_id', 'ticker', 'name', 'exchange', 'share_class', 'tool_type', 'asset_class', 'currency', 'frequency'):
        s['default_' + field] = ''
    s['date_format'] = '%Y-%m-%d'
    s['kind'] = 'adjusted_price'
    s['unit'] = 'decimal'
    s['supplier'] = f"Yahoo chart / {run_id} / raw sha256 {item['raw_sha256']}"
    s['workspace'] = '数据导入'
    s['workspace_route'] = 'prepare_data'


def _safe_handoff(root, run_id, symbol):
    try:
        _handoff(root, run_id, symbol)
    except (ValueError, OSError, KeyError, TypeError):
        st.session_state['dl_handoff_error'] = True


def _partial_diagnostics(root, manifest, prefix):
    partial = [item for item in manifest['items'] if item['status'] == 'partial' and item['daily_file']]
    if not partial:
        return
    try:
        run_id = manifest['run_id']
        if load_snapshot(root, run_id) != manifest:
            raise ValueError('snapshot changed')
        # Read verified stored bytes before exposing any preview or export.
        artifacts = [(item, read_artifact(root, run_id, item['daily_file'])) for item in partial]
        with st.expander('部分可用日线 · 诊断查看与导出'):
            st.warning('这些日线未通过完整字段检查，仅供诊断；缺失值保留，不可送入产品导入。')
            for item, daily in artifacts:
                st.caption(item['symbol'] + ' · ' + run_id)
                st.dataframe(pd.read_csv(BytesIO(daily)), hide_index=True, width='stretch')
                st.download_button('导出诊断日线 CSV · ' + item['symbol'], daily, item['daily_file'],
                                   key=prefix + '_daily_' + item['symbol'])
    except (ValueError, OSError, KeyError, TypeError):
        st.error('诊断缓存校验失败，停止诊断查看与导出。')


def render():
    s = st.session_state
    s.setdefault('dl_plan', None)
    s.setdefault('dl_active', None)
    s.setdefault('dl_result', None)
    from .page_chrome import tool_header
    with tool_header('市场数据与缓存', '生成下载计划，主动下载或打开本地缓存，再送入准备数据核对。', 'dl_active',
                [('返回准备数据', 'prepare_data'), ('因子与官方汇率缓存', 'reference_downloads')]):
        st.info('仅七个识别样本；每项一次公开 Yahoo chart 请求，无自动重试、无需密钥或登录。使用缓存与导出均不联网。')
        st.caption('成功仅表示返回字段通过检查；完整交易日历、历史可得时间及正式候选资格仍需后续查验。')
        symbols = st.multiselect('识别样本', list(CATALOG), default=['SPY', '2800.HK'], key='dl_symbols',persist_state='session')
        cols = st.columns(3)
        start = cols[0].date_input('起日（包含）', value=date(2025,1,1), format='YYYY-MM-DD', key='dl_start_date',persist_state='session')
        end = cols[1].date_input('止日（不包含）', value=date(2025,2,1), format='YYYY-MM-DD', key='dl_end',persist_state='session')
        timeout = cols[2].number_input('单请求超时（秒）', min_value=1, max_value=30, value=15, key='dl_timeout',persist_state='session')
        fingerprint = (tuple(symbols), start.isoformat(), end.isoformat(), timeout)
        if s.get('dl_fingerprint') != fingerprint:
            s['dl_plan'] = None
            s['dl_fingerprint'] = fingerprint
        if st.button('生成下载计划', key='dl_prepare'):
            try:
                validate_plan(*fingerprint)
                s['dl_plan'] = dict(symbols=fingerprint[0], start=fingerprint[1], end=fingerprint[2], timeout=timeout)
            except (ValueError, TypeError):
                st.error('请选择样本，并填写有效 YYYY-MM-DD 日期，起日须早于止日；超时须为 1–30 秒。')
        plan = s['dl_plan']
        if plan:
            st.subheader('计划预览')
            st.write(f"请求数：{len(plan['symbols'])} · {plan['start']}（含）至 {plan['end']}（不含）")
            types = {'stock':'个股', 'ETF':'ETF', 'gold_trust':'黄金信托', 'fx':'外汇'}
            classes = {'equity':'权益', 'bond':'债券', 'commodity':'商品', 'currency':'汇率'}
            st.dataframe(pd.DataFrame([{'代码':symbol, '名称':CATALOG[symbol]['name'],
                '工具类型':types[CATALOG[symbol]['tool_type']], '经济类别':classes[CATALOG[symbol]['asset_class']],
                '市场':CATALOG[symbol]['exchange'], '币种':CATALOG[symbol]['currency']}
                for symbol in plan['symbols']]), hide_index=True, width='stretch')
            st.warning(f'仅可在开始前取消计划。下载同步进行中不能通过页面中断；单请求超时上限 {timeout} 秒。')
            if st.button('取消下载计划', key='dl_cancel'):
                s['dl_plan'] = None
                st.rerun()
            if st.button('开始下载', key='dl_start', type='primary'):
                try:
                    with st.spinner('正在逐项下载并保存原始响应…'):
                        run = run_update(downloads_root(), **plan)
                        manifest = load_snapshot(downloads_root(), run)
                    s['dl_result'] = manifest
                    s['dl_plan'] = None
                    st.success('本次请求已结束，请核对逐项结果。已打开缓存保持不变，可另选所需版本。')
                except (ValueError, OSError, KeyError, TypeError):
                    st.error('更新未完成；已打开缓存仍保留。请检查本地目录或稍后手动重试。')
        if s['dl_result']:
            st.subheader('上次更新结果（原请求范围）')
            _items(s['dl_result'])
        st.subheader('本地缓存')
        try:
            runs = list_runs(downloads_root())
        except (ValueError, OSError):
            runs = []
            st.error('缓存目录无法读取。')
        if runs:
            selected = st.selectbox('下载记录（按时间倒序）', runs, key='dl_run',persist_state='session')
            if st.button('校验并打开缓存', key='dl_open'):
                try:
                    manifest = load_snapshot(downloads_root(), selected)
                    if any(item['status'] == 'success' for item in manifest['items']):
                        s['dl_active'] = dict(root=str(downloads_root()), run_id=selected, manifest=manifest)
                    else:
                        s['dl_result'] = manifest
                        st.warning('此记录没有成功项，保留先前已打开的缓存。')
                        _items(manifest)
                except (ValueError, OSError, KeyError, TypeError):
                    st.error('缓存校验失败；先前打开的缓存及其日期仍保留。')
            try:
                log = update_log(downloads_root())
                st.download_button('导出 update_log.csv', log.to_csv(index=False).encode(), 'update_log.csv', key='dl_log')
            except (ValueError, OSError, KeyError, TypeError):
                st.warning('部分缓存损坏，无法导出完整更新日志。')
        else:
            st.caption('暂无下载记录。生成计划不会创建缓存。')
        active = s['dl_active']
        result = s['dl_result']
        if result:
            _partial_diagnostics(downloads_root(), result, 'dl_result_diag')
        if active and (not result or result['run_id'] != active['run_id']):
            _partial_diagnostics(Path(active['root']), active['manifest'], 'dl_active_diag')
        if not active:
            return
        st.subheader('已打开且通过校验的缓存')
        manifest = active['manifest']
        _items(manifest)
        if s.pop('dl_handoff_error', False):
            st.error('交接前缓存校验失败；当前导入内容保持原样。')
        try:
            # Revalidate before every export/use, including after disk changes.
            verified = load_snapshot(Path(active['root']), active['run_id'])
            if verified != manifest:
                raise ValueError('snapshot changed')
            st.json(manifest, expanded=False)
            st.download_button('导出 snapshot_manifest.json', (json.dumps(manifest, ensure_ascii=False, indent=2)+'\n').encode(), 'snapshot_manifest.json', key='dl_manifest')
            success = [i['symbol'] for i in manifest['items'] if i['status'] == 'success']
            if not success:
                st.caption('此记录没有通过字段检查的可用项。')
                return
            symbol = st.selectbox('使用成功缓存项', success, key='dl_symbol',persist_state='session')
            item = next(i for i in manifest['items'] if i['symbol'] == symbol)
            daily = read_artifact(Path(active['root']), active['run_id'], item['daily_file'])
            st.caption('原币日线 · ' + CATALOG[symbol]['currency'])
            st.dataframe(pd.read_csv(BytesIO(daily)), hide_index=True, width='stretch')
            st.download_button('导出原币日线 CSV', daily, item['daily_file'], key='dl_daily')
            if symbol == 'HKD=X':
                st.info('HKD=X 方向：每 1 USD 对应的 HKD 数量（HKD / USD）。仅提供日线导出，不送入产品导入。')
            elif item['import_file']:
                payload = read_artifact(Path(active['root']), active['run_id'], item['import_file'])
                st.download_button('导出 S02 导入 CSV', payload, item['import_file'], key='dl_import_csv')
                st.button('送入数据导入核对', key='dl_to_import', on_click=_safe_handoff,
                          args=(Path(active['root']), active['run_id'], symbol))
                st.caption('使用原币日线与供应商调整价格，导入时预选复权价格口径。送入后请核对，再决定是否保存。')
        except (ValueError, OSError, KeyError, TypeError):
            st.error('已打开缓存的磁盘文件校验失败；保留原身份与日期，停止使用与导出。')
