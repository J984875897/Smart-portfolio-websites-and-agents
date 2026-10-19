"""Risk preview workflow: current qualified inputs and explicit long-only weights."""
import hashlib
import pandas as pd
import streamlit as st
from portfolio.evaluation.risk_preview import preview_candidate_risk
from .risk_exports import parse_weights
from .risk_display import render_preview
from .upload_state import research_upload


def clear_risk():
    st.session_state['ra_preview']=None
    st.session_state.pop('ra_result_token',None)


def render_risk(candidate,options,screening,token):
    s=st.session_state
    st.divider()
    st.subheader('收益与风险预览')
    if screening.cardinality.status != 'passed':
        clear_risk()
        st.info('先使候选筛选与数量条件通过，再计算收益与风险。')
        return
    ids=list(screening.eligible_asset_ids)
    identity=token+screening.fingerprint
    if s.get('ra_source_identity') != identity:
        clear_risk()
        s['ra_source_identity']=identity
        s['ra_upload_epoch']=s.get('ra_upload_epoch',0)+1
        s.pop('ra_corr_ids',None)
        s['ra_weight_mode']='合格候选等权预览'
    mode=st.radio('风险预览权重',['合格候选等权预览','上传自定义多头权重 CSV'],key='ra_weight_mode',persist_state='session')
    weights=pd.Series(1/len(ids),index=ids,name='weight')
    payload=weights.rename_axis('asset_id').reset_index().to_csv(index=False).encode('utf-8-sig')
    st.download_button('下载本次合格产品权重模板 CSV',payload,file_name='weights_template.csv',
                       key='ra_template',on_click='ignore')
    error=None
    if mode == '上传自定义多头权重 CSV':
        file=research_upload('自定义多头权重（asset_id,weight；小数；全部合格ID）',type=['csv'], slot='ra_weights',
                              key=f'ra_weights_{s.get("ra_upload_epoch",0)}')
        if file is None:
            payload=b'';weights=None
            st.info('上传权重CSV；每个合格ID必须出现一次，零持仓填0，总和为1。不自动归一化。')
        else:
            payload=file.getvalue()
            try: weights=parse_weights(payload,ids)
            except ValueError as exc: weights=None;error=str(exc)
    key=hashlib.sha256(identity.encode()+mode.encode()+payload).hexdigest()
    if s.get('ra_input_token') != key or weights is None: clear_risk()
    s['ra_input_token']=key
    if error: st.error(error)
    positive=int((weights > 0).sum()) if weights is not None else 0
    st.write(f'目标持仓 K = {screening.cardinality.k} · 合格候选 N = {len(ids)} · 当前正权重产品数 = {positive}')
    st.warning('研究预览，尚未完成最终选品。候选池等权覆盖全部N项，不表示已选出K项；此处仅支持多头权重。')
    if st.button('计算收益与风险',type='primary',key='ra_compute',disabled=weights is None):
        clear_risk()
        try:
            with st.spinner('重新查验候选资格并计算收益与风险…'):
                s['ra_preview']=preview_candidate_risk(candidate,weights,**options)
                s['ra_result_token']=key
        except (ValueError,TypeError,KeyError) as exc:
            clear_risk();st.error(f'无法完成风险预览：{exc}。请核对数据与权重后重新计算。')
    if s.get('ra_preview') is not None and s.get('ra_result_token') == key:
        names=dict(zip(candidate.assets.asset_id,candidate.assets.name))
        render_preview(s['ra_preview'],names)
    else:
        st.caption('选择权重后点击“计算收益与风险”。修改研究输入或权重会撤下旧结果与下载。')
