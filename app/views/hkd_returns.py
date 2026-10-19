"""S03A isolated offline HKD reconciliation; calculations belong to core."""
from io import BytesIO
from pathlib import Path
import hashlib
from zipfile import BadZipFile
from xml.etree.ElementTree import ParseError

import pandas as pd
import streamlit as st
from portfolio.data import DataBundle, ImportConfig, read_file, preview_import, commit_import
from portfolio.data.fx import reconcile_hkd, validate_fx

FIXTURES = Path(__file__).resolve().parents[2] / 'tests/fixtures/hkd'
READ_ERRORS = (ValueError, OSError, KeyError, TypeError, BadZipFile, ParseError, UnicodeError, ImportError)
FX_FIELDS = ['date', 'currency', 'hkd_per_unit', 'source_name']


def sample_bundle():
    """Import synthetic data through the same pipeline as S02 without saving it."""
    bundle = DataBundle()
    for filename, kind in [('monthly_total_returns.csv', 'total_return'),
                           ('monthly_adjusted_prices.csv', 'adjusted_price')]:
        raw = read_file((FIXTURES / filename).read_bytes(), filename='SYNTH_' + filename)
        config = ImportConfig(mapping={c: c for c in raw.columns}, source_name='SYNTH',
                              value_kind=kind, return_unit='decimal')
        preview = preview_import(raw, config, bundle, filename='SYNTH_' + filename)
        bundle = commit_import(preview, bundle, allow_review=True)
    return bundle


def fingerprint(bundle, *parameters):
    digest = hashlib.sha256(repr(parameters).encode())
    # Content, schema and evidence bind results even if the S02 version is unchanged.
    for name in ['assets', 'observations', 'provenance']:
        frame = getattr(bundle, name)
        digest.update(repr((name, list(frame.columns))).encode())
        digest.update(frame.to_csv(index=False).encode())
    return digest.hexdigest()


def table(frame, title, key):
    st.subheader(title)
    display = frame.copy()
    display.attrs = {}
    if 'status' in display:
        display.insert(0, '处理状态', display['status'].map({'valid': '可查验', 'blocked': '阻止', 'alignment_required': '待时间对齐'}).fillna(display['status']))
    if 'reason' in display:
        reasons = {'ok': '通过本步查验', 'unconfirmed_adjusted_price': '未确认复权价格包含分配与拆股调整',
                   'missing_fx_start': '缺少精确起点汇率', 'missing_fx_end': '缺少精确期末汇率',
                   'missing_fx_start_and_end': '缺少精确起止汇率', 'not_total_return': '普通价格或价格收益不能视为总收益',
                   'first_period': '首期缺少前月价格', 'missing_previous_month': '缺少相邻前月价格',
                   'invalid_previous_month': '前月观察不满足条件', 'alignment_required': '频率或日期需要时间对齐',
                   'ambiguous_asset_month': '同资产同月观察口径存在歧义', 'currency_conflict': '币种与资产资料冲突',
                   'invalid_value': '数值不满足口径要求', 'invalid_date': '日期不符合严格格式'}
        display.insert(1, '处理说明', display['reason'].map(reasons).fillna(display['reason']))
    st.dataframe(display, hide_index=True, width='stretch')
    st.download_button('下载' + title + ' CSV', frame.to_csv(index=False).encode('utf-8-sig'),
                       file_name=key + '.csv', mime='text/csv', key='hkd_download_' + key)


def summary(result, bundle):
    """Put core results first, with percentages strictly for display."""
    rows = result.reconciliation
    names = dict(zip(bundle.assets.asset_id.astype(str), bundle.assets.name))
    reasons = {'ok': '通过本步查验', 'unconfirmed_adjusted_price': '未确认复权价格包含分配与拆股调整',
               'missing_fx_start': '缺少精确起点汇率', 'missing_fx_end': '缺少精确期末汇率',
               'missing_fx_start_and_end': '缺少精确起止汇率', 'first_period': '首期缺少前月价格',
               'missing_previous_month': '缺少相邻前月价格', 'invalid_previous_month': '前月观察不满足条件',
               'not_total_return': '普通价格或价格收益不能视为总收益', 'alignment_required': '频率或日期需要时间对齐',
               'ambiguous_asset_month': '同资产同月观察口径存在歧义', 'currency_conflict': '币种与资产资料冲突',
               'invalid_value': '数值不满足口径要求', 'invalid_date': '日期不符合严格格式',
               'invalid_currency': '币种无效', 'unknown_asset': '缺少资产资料',
               'ambiguous_asset_metadata': '资产资料存在歧义', 'invalid_frequency': '频率无效',
               'invalid_value_kind': '收益口径无效', 'nonfinite_hkd_result': '换算结果不是有限数值'}
    compact = pd.DataFrame({
        '产品名称': rows['asset_id'].astype(str).map(names).fillna(rows['asset_id']),
        '资产标识': rows['asset_id'], '原币': rows['currency'], '期末日期': rows['end_date'],
        '原币收益（%）': rows['local_return'] * 100, '港币收益（%）': rows['hkd_return'] * 100,
        '起点汇率': rows['fx_start'], '期末汇率': rows['fx_end'],
        '处理状态': rows['status'].map({'valid': '可查验', 'blocked': '阻止：缺失或不可用',
                                       'alignment_required': '待时间对齐'}).fillna(rows['status']),
        '处理说明': rows['reason'].map(reasons).fillna(rows['reason']),
    })
    st.subheader('收益查验结果')
    st.caption('收益以百分数显示；例如 1.00 表示 1%。空白 / NaN 表示缺失或不可用，绝不是零收益。阻止行不能作为有效收益使用。汇率单位为每一单位原币对应的港币数。')
    st.dataframe(compact, hide_index=True, width='stretch', column_config={
        '原币收益（%）': st.column_config.NumberColumn(format='%.6f'),
        '港币收益（%）': st.column_config.NumberColumn(format='%.6f'),
    })


def render():
    s = st.session_state
    s.setdefault('bundle', DataBundle())
    s.setdefault('bundle_version', 'empty')
    s.setdefault('hkd_result', None)
    from .page_chrome import tool_header
    with tool_header('收益与窗口核对', '港币收益查验：核对月度原币收益与汇率，再检查共同窗口。', 'hkd_result',
                [('核对共同窗口', 'alignment'), ('日线月度查验', 'daily_monthly'), ('日线港币查验', 'daily_hkd'), ('返回资格中心', 'eligibility')]):
        st.warning('本页仅查验月度总收益与港币换算。S03-B 时间证据与 60 月共同窗口请到独立页面继续查验，港币现金收益代理请到「港币利率查验」独立核对。月度换算和时间检查仍不足以完成组合估计、Sharpe 或回测，真实来源仍需认证。')
        st.write('仅接受 monthly 自然月末观察；外币汇率须精确匹配起止日期，缺失保留 NaN。汇率单位：每一单位外币对应的港币数。')
        mode = st.radio('选择数据', ['当前已保存数据', '人工测试案例'], key='hkd_data_mode', horizontal=True,persist_state='session')
        if s.get('hkd_previous_mode') != mode:
            s.pop('hkd_fx_mode', None)
            s['hkd_adjusted_assets'] = []
        s['hkd_previous_mode'] = mode
        if mode == '人工测试案例':
            st.info('人工案例验证：美元本币收益 1%，汇率 7.8 → 7.9，港币收益约 2.2948718%；港币资产无需汇率。另含 100 → 101 调整价格、零收益及 −100% 全损。全部为合成输入，仅用于查验，不保存到数据导入版本。全损极端值在人工导入中明确接受。')
            try:
                bundle = sample_bundle()
            except READ_ERRORS as exc:
                s['hkd_result'] = None
                st.error(f'人工数据无法读取：{exc}')
                return
        else:
            bundle = s['bundle']
            st.caption(f'当前已保存版本：{s["bundle_version"]} · 原币观察 {len(bundle.observations)}')
        adjusted = sorted(bundle.observations.loc[bundle.observations.value_kind == 'adjusted_price', 'asset_id'].astype(str).unique())
        # Remove obsolete widget selections when switching to a different bundle.
        if 'hkd_adjusted_assets' in s:
            s['hkd_adjusted_assets'] = [x for x in s['hkd_adjusted_assets'] if x in adjusted]
        names = dict(zip(bundle.assets.asset_id.astype(str), bundle.assets.name))
        confirmations = st.multiselect('逐资产确认：已核实复权价格包含分配及拆股调整', adjusted,
                                       format_func=lambda aid: f'{names.get(aid, aid)} · {aid}',
                                       key='hkd_adjusted_assets',persist_state='session')
        st.caption('请先核对来源口径，再勾选资产。人工案例也不会自动确认。确认不证明历史数据在当时可得；本页不会重复加分红。')
        choices = ['不提供汇率', '完整人工汇率案例', '缺少期末汇率案例', '上传本地汇率文件']
        fx_mode = st.selectbox('汇率输入', choices, index=1 if mode == '人工测试案例' else 0, key='hkd_fx_mode',persist_state='session')
        payload, filename, sheet = b'', '', 0
        fx = pd.DataFrame(columns=FX_FIELDS)
        input_error = None
        try:
            if fx_mode in ['完整人工汇率案例', '缺少期末汇率案例']:
                filename = 'fx.csv' if fx_mode == '完整人工汇率案例' else 'fx_missing_end.csv'
                payload = (FIXTURES / filename).read_bytes()
                fx = read_file(payload, filename='SYNTH_' + filename)
                st.caption('人工美元汇率：2024-12-31 为 7.8；2025-01-31 为 7.9。' if fx_mode == '完整人工汇率案例' else '缺失案例仅保留起点 7.8：美元换算应被阻止，港币收益仍有效。')
            elif fx_mode == '上传本地汇率文件':
                from .upload_state import research_upload
                upload = research_upload('选择汇率 CSV 或 XLSX', type=['csv', 'xlsx'], key='hkd_fx_upload', slot='hkd_fx_upload', scope=(mode, fingerprint(bundle)))
                if upload is not None:
                    payload, filename = upload.getvalue(), upload.name
                    if filename.lower().endswith('.xlsx'):
                        sheets = pd.ExcelFile(BytesIO(payload), engine='openpyxl').sheet_names
                        sheet = st.selectbox('汇率 Excel 工作表', sheets, key='hkd_fx_sheet',persist_state='session')
                    fx = read_file(payload, filename=filename, sheet_name=sheet)
            validated = validate_fx(fx)
        except READ_ERRORS as exc:
            input_error = f'汇率文件无法读取：{exc}。请核对格式、编码、重复列名和工作表。'
            s['hkd_result'] = None
        token = fingerprint(bundle, mode, fx_mode, payload, filename, sheet, sorted(confirmations))
        if s.get('hkd_fingerprint') != token:
            s['hkd_result'] = None
        s['hkd_fingerprint'] = token
        with st.expander('下载汇率模板和人工测试汇率'):
            st.download_button('下载汇率 CSV 模板', pd.DataFrame(columns=FX_FIELDS).to_csv(index=False).encode(),
                               file_name='fx_template.csv', key='hkd_template')
            st.download_button('下载已测试的 7.8 → 7.9 人工汇率', (FIXTURES / 'fx.csv').read_bytes(),
                               file_name='SYNTH_fx.csv', key='hkd_example')
        if input_error:
            st.error(input_error)
            return
        if len(fx):
            st.caption(f'汇率来源：{filename} · 工作表 {sheet} · {len(fx)} 行；源文件 hash 随结果保留。')
            shown = fx.copy(); shown.attrs = {}
            st.dataframe(shown, hide_index=True, width='stretch')
        if not validated.issues.empty:
            st.error('汇率存在阻止项；受影响日期与币种不能换算。')
            shown = validated.issues.copy(); shown.attrs = {}
            st.dataframe(shown, hide_index=True, width='stretch')
        if bundle.observations.empty:
            st.info('尚无已保存原币观察。请到数据导入页保存数据，或选择人工测试案例。')
        if st.button('计算港币收益对照', key='hkd_compute', type='primary', disabled=bundle.observations.empty):
            s['hkd_result'] = None
            try:
                s['hkd_result'] = reconcile_hkd(bundle, fx, adjusted_price_assets=confirmations)
                s['hkd_result_origin'] = {'mode': mode, 'bundle_fingerprint': fingerprint(bundle),
                                          'input_fingerprint': token}
            except READ_ERRORS as exc:
                st.error(f'无法生成对照：{exc}。请核对数据与汇率输入。')
        result = s['hkd_result']
        if result is not None:
            summary(result, bundle)
            with st.expander('完整对照、来源证据及 CSV 下载'):
                st.caption('完整表与下载保留核心小数收益口径，例如 0.01 表示 1%；CSV 包含全部来源字段。')
                table(result.reconciliation, '港币收益对照及来源', 'hkd_reconciliation')
                table(result.local_returns, '原币收益及来源', 'local_returns')
                table(result.fx_issues, '汇率质量报告', 'fx_issues')
