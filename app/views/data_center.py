"""S02 local import, explicit quality acceptance and version inspection."""
from pathlib import Path
from io import BytesIO
import hashlib
import os
from uuid import uuid4
from datetime import datetime, timezone
from zipfile import BadZipFile
from xml.etree.ElementTree import ParseError

import pandas as pd
import streamlit as st
from portfolio.data import (DataBundle, ImportConfig, read_file, preview_import,
                            commit_import, TOOL_TYPES, ASSET_CLASSES, CURRENCIES, FREQUENCIES)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'tests/fixtures/imports'
FIELDS = {'asset_id':'稳定资产标识', 'ticker':'代码', 'name':'产品名称', 'date':'日期（必需）',
          'value':'价格／收益数值（必需）', 'tool_type':'工具类型', 'asset_class':'经济资产类别',
          'exchange':'交易所／市场', 'currency':'原币', 'share_class':'份额类别', 'frequency':'频率'}
LABELS = {'stock':'股票', 'ETF':'ETF', 'fund':'基金', 'bond':'债券', 'index':'指数', 'cash':'现金',
 'commodity':'商品', 'REIT':'房地产信托', 'derivative':'衍生品', 'gold_trust':'黄金信托',
 'mutual_fund':'共同基金', 'equity':'权益', 'fixed_income':'固定收益', 'real_estate':'房地产',
 'mixed':'混合', 'alternative':'另类', 'daily':'日频', 'weekly':'周频', 'monthly':'月频',
 'quarterly':'季频', 'annual':'年频', 'price':'价格', 'adjusted_price':'复权价格',
 'total_return':'总收益', 'price_return':'价格收益', 'decimal':'小数', 'percent':'百分数'}

def label(value):
    return '不指定' if value == '' else f'{LABELS.get(value, value)} · {value}'

def imports_root():
    return Path(os.environ.get('PORTFOLIO_IMPORTS_ROOT', str(ROOT / 'data/processed/imports')))

def set_source(payload, filename, synthetic=False):
    st.session_state['source'] = (payload, filename, synthetic)
    st.session_state['preview'] = None
    st.session_state['overrides'] = {}
    st.session_state['alias_map'] = {}
    st.session_state['ack'] = False
    st.session_state['kind'] = 'total_return' if synthetic else 'price'
    st.session_state['unit'] = 'percent' if synthetic else 'decimal'
    for field in FIELDS:
        st.session_state.pop('map_' + field, None)

def download_table(frame, title, key):
    displayed = frame.copy()
    displayed.attrs = {}
    states = {'valid':'可接受', 'review':'待核对', 'blocked':'阻止', 'duplicate':'重复', 'review_pending':'尚未确认'}
    if 'status' in displayed:
        displayed.insert(0, '处理状态', displayed['status'].map(states).fillna(displayed['status']))
    if 'severity' in displayed:
        displayed.insert(0, '处理状态', displayed['severity'].map(states).fillna(displayed['severity']))
    if 'code' in displayed:
        reasons = {'invalid_date':'日期不符合指定格式', 'missing_value':'数值缺失，保留 NaN',
                   'invalid_value':'数值不满足当前价格／收益口径', 'malformed_value':'数值无法解析',
                   'extreme_return':'绝对单期收益达到 50%，须核对', 'manual_identity':'须明确关联资产标识',
                   'identity_conflict':'资产身份冲突，须核对交易所、代码、币种、份额',
                   'metadata_conflict':'分类／频率冲突，须明确修正', 'conflict':'同一观察有不同数值',
                   'monthly_period_collision':'同一月有多个日期，须核对'}
        for field, title_ in FIELDS.items():
            reasons['missing_' + field] = '缺少' + title_
            reasons['invalid_' + field] = title_ + '不在允许选项中'
        displayed.insert(1, '检查说明', displayed['code'].map(reasons).fillna(displayed['code']))
    st.dataframe(displayed, hide_index=True, width='stretch')
    st.download_button(f'下载{title} CSV', frame.to_csv(index=False).encode('utf-8-sig'),
                       file_name=f'{key}.csv', mime='text/csv', key='download_' + key)

def render():
    s = st.session_state
    for key, value in {'bundle':DataBundle(), 'preview':None, 'source':None,
                       'overrides':{}, 'alias_map':{}, 'bundle_version':'empty'}.items():
        if key not in s:
            s[key] = value
    from app.views.page_chrome import page_header, live_status
    from app.views.workspace_state import workspace_snapshot
    from app.views.workspace_shell import route_button
    page_header('完成研究 / 01', '准备数据', '打开已有版本，或按文件 → 字段映射 → 质量检查 → 保存的顺序导入资料。保留原币记录。')
    with live_status(lambda: workspace_snapshot(s).data):
        with st.expander('没有本地文件？使用市场数据工具'):
            st.write('先生成下载计划，主动下载并校验缓存，再送回本页核对。')
            route_button('前往市场数据与缓存', 'downloads', 'data_to_downloads')
        versions = sorted([p.name for p in imports_root().iterdir() if p.is_dir()], reverse=True) if imports_root().exists() else []
        with st.expander('打开已保存版本', expanded=bool(versions)):
            if versions:
                version = st.selectbox('本地版本', versions, key='version_choice',persist_state='session')
                if st.button('打开此版本', key='load_version'):
                    try:
                        loaded = DataBundle.load(imports_root() / version)
                        s['bundle'] = loaded
                        s['bundle_version'] = version
                        s['preview'] = None
                        st.success('版本已打开，表与原文件校验通过。')
                    except (ValueError, OSError, KeyError, TypeError, BadZipFile, ParseError) as exc:
                        st.error(f'无法打开版本：{exc}。请保留该目录并检查文件是否完整。')
            else:
                st.caption('尚无保存版本。完成质量检查后可以保存第一个版本。')
        st.subheader('选择文件与原始记录')
        upload = st.file_uploader('选择本地 CSV 或 XLSX', type=['csv','xlsx'], key=('upload' if not s.get('upload_generation') else f"upload_{s['upload_generation']}"))
        if upload is None:
            # Clearing the uploader permits a deliberate reselection of identical bytes.
            # Keep the active sample and its preview until a new file is selected.
            s.pop('upload_token', None)
        else:
            payload = upload.getvalue()
            token = (upload.name, hashlib.sha256(payload).hexdigest())
            if token != s.get('upload_token'):
                set_source(payload, upload.name)
                s['upload_token'] = token
        cols = st.columns([3,1])
        sample = cols[0].selectbox('合成示例（SYNTH）', ['ten_products.csv','repeated_two.csv','dirty_data.csv'], key='sample',persist_state='session')
        if cols[1].button('载入合成示例', key='load_sample'):
            set_source((FIXTURES / sample).read_bytes(), 'SYNTH_' + sample, True)
        with st.expander('下载模板与合成示例'):
            template = pd.DataFrame(columns=FIELDS)
            st.download_button('CSV 字段模板', template.to_csv(index=False).encode(), 'import_template.csv', key='template_csv')
            buf = BytesIO()
            template.to_excel(buf, index=False)
            st.download_button('XLSX 字段模板', buf.getvalue(), 'import_template.xlsx', key='template_xlsx')
            for name in ['ten_products.csv','repeated_two.csv','dirty_data.csv']:
                st.download_button('SYNTH · ' + name, (FIXTURES / name).read_bytes(), 'SYNTH_' + name, key='example_' + name)
        if s['source']:
            payload, filename, synthetic = s['source']
            sheet = 0
            try:
                if filename.lower().endswith('.xlsx'):
                    sheets = pd.ExcelFile(BytesIO(payload), engine='openpyxl').sheet_names
                    sheet = st.selectbox('Excel 工作表', sheets, key='sheet',persist_state='session')
                raw = read_file(payload, filename=filename, sheet_name=sheet)
            except (ValueError, OSError, KeyError, TypeError, BadZipFile, ParseError) as exc:
                s['preview'] = None
                st.error(f'文件无法读取：{exc}。请检查文件格式、重复列名和工作表。')
                return
            st.caption(f'来源文件：{filename} · {len(raw)} 行' + (' · SYNTH 合成数据' if synthetic else ''))
            displayed_raw = raw.copy()
            displayed_raw.attrs = {}
            st.dataframe(displayed_raw, hide_index=True, width='stretch')
            st.subheader('字段映射与口径')
            st.caption('仅同名字段预选；未映射字段不会猜测。逐行值优先，默认值只填空白。类型与经济类别须明确指定。')
            mapping = {}
            with st.expander('逐字段映射（必需与可选）', expanded=True):
                mapcols = st.columns(3)
                options = [''] + list(raw.columns)
                for i, (field, title) in enumerate(FIELDS.items()):
                    chosen = mapcols[i % 3].selectbox(title, options, index=options.index(field) if field in options else 0,
                                                    format_func=lambda x: x or '不映射', key='map_' + field,persist_state='session')
                    if chosen:
                        mapping[field] = chosen
            if 'supplier' not in s:
                s['supplier'] = 'SYNTH' if synthetic else '本地文件'
            supplier = st.text_input('来源供应商／来源名称', key='supplier',persist_state='session')
            c = st.columns(3)
            kind = c[0].selectbox('价格／收益口径', ['price','adjusted_price','total_return','price_return'], format_func=label, key='kind',persist_state='session')
            unit = c[1].selectbox('收益单位', ['decimal','percent'], format_func=label, key='unit',persist_state='session')
            date_format = c[2].text_input('日期格式', value='%Y-%m-%d', key='date_format',persist_state='session')
            defaults = {}
            with st.expander('缺失字段默认值（单产品文件也适用）'):
                dc = st.columns(3)
                for i, field in enumerate(['asset_id','ticker','name','exchange','share_class']):
                    value = dc[i % 3].text_input('默认' + FIELDS[field], key='default_' + field,persist_state='session')
                    if value.strip(): defaults[field] = value.strip()
                for i, (field, opts) in enumerate([('tool_type',sorted(TOOL_TYPES)),('asset_class',sorted(ASSET_CLASSES)),('currency',sorted(CURRENCIES)),('frequency',sorted(FREQUENCIES))]):
                    value = dc[i % 3].selectbox('默认' + FIELDS[field], [''] + opts, format_func=label, key='default_' + field,persist_state='session')
                    if value: defaults[field] = value
            try:
                config = ImportConfig(mapping=mapping, source_name=supplier, defaults=defaults, value_kind=kind,
                                      return_unit=unit, date_format=date_format, sheet_name=sheet,
                                      classification_overrides=dict(s['overrides']), alias_mappings=dict(s['alias_map']))
            except (ValueError, TypeError) as exc:
                s['preview'] = None
                s['ack'] = False
                st.error(f'请填写来源名称并核对导入口径：{exc}')
                return
            fingerprint = hashlib.sha256(repr((payload, filename, sheet, mapping, defaults, supplier, kind, unit,
                                               date_format, s['overrides'], s['alias_map'], s['bundle_version'])).encode()).hexdigest()
            if s.get('preview_fingerprint') != fingerprint:
                s['preview'] = None
                s['ack'] = False
            if st.button('质量检查', key='check', type='primary'):
                try:
                    s['preview'] = preview_import(raw, config, s['bundle'], filename=filename)
                    s['preview_fingerprint'] = fingerprint
                    s['ack'] = False
                except (ValueError, TypeError, KeyError) as exc:
                    s['preview'] = None
                    st.error(f'无法检查：{exc}。请核对映射与日期格式。')
            preview = s['preview']
            if preview is not None:
                st.subheader('核对并保存')
                counts = preview.counts
                st.write(' · '.join(f'{title} {counts.get(code, 0)} 行' for code,title in [('valid','可接受'),('review','待核对'),('blocked','阻止'),('duplicate','重复')]))
                st.warning('阻止行不会入库。重复观察不增加产品或记录；来源追踪仍保留。')
                download_table(preview.rows, '逐行质量预览', 'preview')
                download_table(preview.issues, '质量报告', 'quality_preview')
                with st.expander('明确修正产品分类（保留修改记录）'):
                    ids = sorted(set(preview.rows['asset_id'].dropna().astype(str)) | set(s['bundle'].assets['asset_id'].astype(str)))
                    ids = [v for v in ids if v]
                    if ids:
                        aid = st.selectbox('要修正的资产标识', ids, key='override_asset',persist_state='session')
                        tc = st.selectbox('修正工具类型', [''] + sorted(TOOL_TYPES), format_func=lambda v: label(v) if v else '保持原工具类型', key='override_type',persist_state='session')
                        ac = st.selectbox('修正经济类别', [''] + sorted(ASSET_CLASSES), format_func=lambda v: label(v) if v else '保持原经济类别', key='override_class',persist_state='session')
                        if st.button('应用分类修正并重新检查', key='apply_override', disabled=not (tc or ac)):
                            updates = {field:value for field,value in [('tool_type',tc),('asset_class',ac)] if value}
                            s['overrides'][aid] = {**s['overrides'].get(aid, {}), **updates}
                            s['preview'] = None
                            st.rerun()
                with st.expander('人工映射来源别名（明确关联已有产品）'):
                    targets = sorted(s['bundle'].assets['asset_id'].astype(str).tolist())
                    if targets:
                        st.caption('仅关联相同交易所、币种与份额类别的已有产品；不同柜台由质量检查阻止。')
                        alias_ticker = st.text_input('此来源中的代码', key='alias_ticker',persist_state='session').strip()
                        alias_exchange = st.text_input('此来源中的交易所', key='alias_exchange',persist_state='session').strip()
                        alias_currency = st.selectbox('此来源中的币种', sorted(CURRENCIES), key='alias_currency',persist_state='session')
                        alias_share = st.text_input('此来源中的份额类别（可空）', key='alias_share',persist_state='session').strip()
                        target = st.selectbox('关联已有资产标识', targets, key='alias_target',persist_state='session')
                        if st.button('应用来源别名并重新检查', key='apply_alias', disabled=not (alias_ticker and alias_exchange and supplier.strip())):
                            s['alias_map'][(supplier, alias_exchange, alias_ticker, alias_share, alias_currency)] = target
                            s['preview'] = None
                            st.rerun()
                    else:
                        st.caption('先保存产品，再关联新来源中的明确代码。')
                review = counts.get('review',0) > 0
                ack = st.checkbox('我已逐行核对待核对项，接受原始极端值／频率提示', key='ack',persist_state='session') if review else False
                acceptable = counts.get('valid',0) + counts.get('duplicate',0) + (counts.get('review',0) if ack else 0)
                if st.button('仅保存可接受行（阻止行不入库）', key='commit', disabled=acceptable == 0):
                    try:
                        candidate = commit_import(preview, s['bundle'], allow_review=ack)
                        version = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '_' + uuid4().hex[:10]
                        root = imports_root()
                        root.mkdir(parents=True, exist_ok=True)
                        candidate.save(root / version)
                        s['bundle'] = candidate
                        s['bundle_version'] = version
                        s['preview'] = None
                        st.success(f'已保存版本 {version}。阻止行未入库；未确认的待核对行未入库。')
                    except (OSError, ValueError, TypeError, KeyError) as exc:
                        st.error(f'保存失败：{exc}。当前数据仍保留，请检查本地目录权限与空间后重试。')
        st.subheader('已保存数据')
        if len(s['bundle'].assets):
            route_button('下一步：核对资格', 'eligibility', 'data_to_eligibility')
        bundle = s['bundle']
        st.caption(f'当前版本：{s["bundle_version"]} · 产品 {len(bundle.assets)} · 原币观察 {len(bundle.observations)}')
        tabs = st.tabs(['产品','原币观察','来源别名','来源追踪','分类修改','质量报告'])
        for tab, attr, title in zip(tabs, ['assets','observations','aliases','provenance','classification_history','issues'], ['产品','原币观察','来源别名','来源追踪','分类修改','质量报告']):
            with tab: download_table(getattr(bundle, attr), title, attr)
