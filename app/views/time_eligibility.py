"""Local version timing preview; recomputed on each rerun, without writes."""
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from portfolio.data.daily_hkd import connect_daily_hkd
from portfolio.data.daily_hkd_samples import sample_daily_prices, sample_daily_fx
from portfolio.data.daily_monthly import aggregate_daily_prices
from portfolio.data.time_eligibility import (
    CaptureEvidence, load_price_capture, load_fx_capture, qualify_daily_hkd,
)

STATUS = {'eligible_from_snapshot': '本地版本时间通过', 'blocked': '证据不足／阻止', 'declaration_only': '仅人工声明'}
REASONS = {
    'ok': '所需本地版本在决策时点前已取得',
    'base_return_invalid': '港币收益基础查验未通过',
    'unsupported_currency': '暂不支持该币种',
    'declaration_after_decision': '人工声明时间晚于决策时点',
}
for prefix, name in [('price', '价格'), ('fx', '汇率')]:
    for code, text in {
        'capture_missing': '缺少可核验的本地快照',
        'source_not_success': '来源未完整通过（success）',
        'hash_mismatch': '快照散列与收益所用版本不一致',
        'time_evidence_missing': '缺少下载完成时间，时间证据不足',
        'time_evidence_invalid': '下载完成时间无效',
        'capture_after_decision': '本地取得该版本晚于决策时点',
    }.items():
        REASONS[prefix + '_' + code] = name + '：' + text


def _synthetic():
    prices = aggregate_daily_prices(sample_daily_prices('SPY', '2025-01', '2025-01'),
                                    symbol='SPY', start_month='2025-01', end_month='2025-01', confirmed=True)
    result = connect_daily_hkd(prices, sample_daily_fx('2025-01', '2025-01'), fx_confirmed=True)
    moment = '2025-02-02T00:00:00+00:00'
    price = CaptureEvidence(prices.metadata['source_hash'], moment, 'success', 'SYNTH-price')
    fx = CaptureEvidence(result.metadata['fx_source_hash'], moment, 'success', 'SYNTH-fx')
    return result, price, fx


def _captures(result):
    base = Path(__file__).resolve().parents[2]
    price_root = Path(os.environ.get('PORTFOLIO_DOWNLOADS_ROOT', str(base/'data/downloads')))
    reference_root = Path(os.environ.get('PORTFOLIO_REFERENCE_DOWNLOADS_ROOT', str(base/'data/reference_downloads')))
    source = result.metadata.get('price_source', {})
    price = load_price_capture(price_root, source['run_id'], result.prices.metadata['symbol']) if source.get('run_id') else None
    fx = None
    if result.prices.metadata['currency'] == 'USD':
        source = result.metadata.get('fx_source', {})
        if source.get('run_id'):
            root = reference_root if source.get('manifest', {}).get('schema_version') == 2 else price_root
            fx = load_fx_capture(root, source['run_id'])
    return price, fx


def render():
    state = st.session_state
    state['te_result'] = None
    from .page_chrome import tool_header
    with tool_header('历史资格与来源', '历史资格查验：检查收益数据版本是否有证据证明在指定决策时点前取得。', 'te_result',
                [('返回日线港币查验', 'daily_hkd'), ('查看已保存版本', 'prepare_data'), ('返回资格中心', 'eligibility')]):
        st.caption('这是观测版本的时间查验。历史候选池、退市产品和幸存者偏差仍需另行查验。')
        source = st.radio('查验来源', ['上一页日线港币结果', 'SYNTH 时间案例'], key='te_source', horizontal=True,persist_state='session')
        decision = st.text_input('决策时点（ISO 时间，必须含时区）', value='2025-02-02T00:00:00+00:00', key='te_decision',persist_state='session')
        st.caption('例如 2025-02-02T08:00:00+08:00 与 2025-02-02T00:00:00Z 是同一时刻。')
        declaration = st.text_input('人工声明可得时间（可留空，仅供对照）', key='te_declaration',persist_state='session')
        try:
            if source == 'SYNTH 时间案例':
                st.warning('SYNTH 人工演示：模拟价格及汇率均在 2025-02-02 00:00 UTC 取得。通过结果仅演示规则，不是实际投资证据。')
                result, price, fx = _synthetic()
            else:
                result = state.get('dh_result')
                if result is None:
                    st.info('先到「日线港币查验」计算一次，再返回本页；也可选择 SYNTH 时间案例体验规则。')
                    return
                price, fx = _captures(result)
                st.caption('每次查验都会重新核对本地缓存文件散列。人工案例／上传文件缺少可核验快照时，仅展示缺失证据。')
            qualified = qualify_daily_hkd(result, decision_at=decision, price_capture=price, fx_capture=fx, declared_available_at=declaration)
        except (ValueError, OSError, KeyError, TypeError) as error:
            st.error('无法查验：时间必须包含时区，且本地快照须完整可读。请核对输入或回到上一页重新计算。')
            return
        qualified.metadata['evidence_kind'] = 'SYNTH' if source == 'SYNTH 时间案例' else 'C2 result with reverified local snapshots where present'
        state['te_result'] = qualified
        rows = qualified.rows
        st.subheader('观测版本时间资格')
        st.metric('本地版本时间通过月数', int(rows.historical_observation_eligible.sum()))
        st.dataframe(pd.DataFrame({
            '目标月末': rows.date,
            '时间资格': rows.time_status.map(STATUS),
            '原因': rows.time_reason.map(lambda value: '；'.join(REASONS.get(x, x) for x in value.split(';'))),
            '价格取得完成时间（UTC）': rows.price_capture_completed_utc,
            '汇率取得完成时间（UTC）': rows.fx_capture_completed_utc,
        }), hide_index=True)
        st.info('“本地版本时间通过”只证明该版本最晚于本地取得时点可得。人工声明不升级资格；旧缓存缺少完成时间时，不能推算补填。')
        st.caption('本地时钟和清单是研究审计记录，不是独立时间戳认证；此处不推断源站历史发布时间，也不自动送入共同窗口或候选池。')
        with st.expander('完整查验记录与散列'):
            st.dataframe(rows, hide_index=True)
            st.json(qualified.metadata)
        st.download_button('下载时间资格 CSV', rows.to_csv(index=False).encode('utf-8-sig'), file_name='time_eligibility.csv', mime='text/csv', key='te_csv')
        st.download_button('下载时间证据 JSON', json.dumps(qualified.metadata, ensure_ascii=False, indent=2), file_name='time_evidence.json', mime='application/json', key='te_json')
