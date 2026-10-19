"""Inspectable tables and charts; controls here never change research inputs."""
import altair as alt
import pandas as pd
import streamlit as st
from .risk_exports import correlation_pairs,preview_exports


def show_estimates(preview,names):
    e=preview.estimate
    st.write('收益采用50%个体均值＋50%同类产品均值；年化为月算术均值×12，不是复合年增长率，也不是未来收益保证。')
    table=e.summary.copy()
    table.insert(0,'产品名称',[names.get(a,a) for a in table.index])
    titles={'asset_class':'经济类别','historical_mean_ann':'历史年化均值','estimated_mean_ann':'估计年化收益',
            'sample_vol_ann':'经验年化波动','shrunk_vol_ann':'模型年化波动','is_constant':'常数序列'}
    shown=table[['产品名称',*titles]].rename(columns=titles)
    pct={v:st.column_config.NumberColumn(v,format='percent',step=0.000001) for k,v in titles.items() if k.endswith('_ann')}
    st.dataframe(shown,column_config=pct,width='stretch')
    if e.diagnostics['constant_assets']:
        st.warning('存在常数收益序列：经验波动为零不表示产品真实无风险；收缩模型可能为其赋予正方差。')
    with st.expander('估计方法与数值状态'):
        st.write(f"样本协方差秩 {e.diagnostics['sample_covariance']['rank']} / {len(e.asset_ids)}；收缩系数 {e.diagnostics['shrinkage_coefficient']:.6f}。")
        st.caption('类别均值包含自身，类别成员数见完整收益导出。数值可优化状态仅描述矩阵，不认证投资适用性或历史候选资格。')
        st.json(e.diagnostics)


def show_correlation(preview,names):
    c=preview.correlation;ids=list(c.matrix.index)
    st.write('原始港币月收益的 Pearson 相关系数。正相关表示同向变动，负相关表示反向变动；相关性本身不能保证危机时仍有分散化效果。')
    selected=st.multiselect('热图产品（仅改变展示，选择2–30项）',ids,default=ids[:20],max_selections=30,
                            format_func=lambda aid:f'{aid} · {names.get(aid,aid)}',key='ra_corr_ids',persist_state='session')
    if len(selected) < 2:
        st.info('请选择至少2项查看热图；候选数量和风险结果不变。')
    else:
        sub=c.matrix.loc[selected,selected].rename_axis('asset_a').reset_index().melt(id_vars='asset_a',var_name='asset_b',value_name='correlation')
        # Fixed size lives in a scrollable container on narrow screens.
        chart=alt.Chart(sub).mark_rect().encode(
            x=alt.X('asset_b:N',title='产品 ID',sort=selected,axis=alt.Axis(labelAngle=-60,labelLimit=145)),
            y=alt.Y('asset_a:N',title='产品 ID',sort=selected,axis=alt.Axis(labelLimit=145)),
            color=alt.Color('correlation:Q',scale=alt.Scale(domain=[-1,1],scheme='redblue'),title='Pearson'),
            tooltip=['asset_a:N','asset_b:N',alt.Tooltip('correlation:Q',format='.4f')]
        ).properties(width=max(320,len(selected)*22),height=max(260,len(selected)*22))
        st.markdown('<style>.st-key-ra_heatmap{overflow-x:auto;max-width:100%}</style>',unsafe_allow_html=True)
        with st.container(key='ra_heatmap'):
            st.altair_chart(chart,width='content')
    unavailable=len(c.diagnostics['constant_assets'])
    st.caption(f"可用唯一产品对：{c.diagnostics['available_pairs']}；常数产品：{unavailable}。常数产品对应项（含自身）不可用，图中留空，不以0代替。完整矩阵可在导出页签下载。")
    if unavailable: st.info('部分或全部相关性不可用：常数收益序列无法计算 Pearson。')
    sort=st.selectbox('产品对排序（仅改变展示）',['相关系数从高到低','相关系数从低到高','绝对值从高到低'],key='ra_pair_sort',persist_state='session')
    pairs=correlation_pairs(c.matrix)
    if sort == '绝对值从高到低': pairs=pairs.iloc[pairs.correlation.abs().sort_values(ascending=False,kind='stable').index]
    else: pairs=pairs.sort_values('correlation',ascending=sort == '相关系数从低到高',kind='stable')
    pairs=pairs.copy()
    pairs.insert(1,'产品A名称',pairs.asset_a.map(names))
    pairs.insert(3,'产品B名称',pairs.asset_b.map(names))
    st.caption('下表显示前100对，不含自身和重复对。绝对值排序同时包含强正相关与强负相关，不据此自动剔除产品。')
    st.dataframe(pairs.head(100).rename(columns={'asset_a':'产品A','asset_b':'产品B','correlation':'相关系数'}),hide_index=True,width='stretch')


def show_risk(preview,names):
    rows=[]
    for title,risk in [('经验协方差',preview.sample_risk),('收缩模型（Ledoit–Wolf）',preview.model_risk)]:
        m=risk.metrics
        rows.append({'口径':title,'估计年化收益':m['mean_ann'],'年化波动':m['volatility_ann'],
                     '有效持仓数':m['effective_holdings'],'分散化比率 DR':m['diversification_ratio']})
    st.write('两种口径使用相同的估计收益和指定权重；个体波动、组合波动及分散化比率始终来自各自同一协方差。')
    st.dataframe(pd.DataFrame(rows),hide_index=True,width='stretch',column_config={
        '估计年化收益':st.column_config.NumberColumn(format='percent',step=0.000001),
        '年化波动':st.column_config.NumberColumn(format='percent',step=0.000001),
        '分散化比率 DR':st.column_config.NumberColumn(format='%.4f')})
    st.caption('有效持仓数只衡量权重集中度，不是独立风险来源数；DR接近1表示本口径下分散化改善有限，高DR也不等于安全。')
    method=st.selectbox('风险贡献口径（仅改变展示）',['经验协方差','收缩模型（Ledoit–Wolf）'],key='ra_risk_method',persist_state='session')
    risk=preview.sample_risk if method == '经验协方差' else preview.model_risk
    table=risk.contributions.copy()
    table.insert(0,'产品名称',[names.get(a,a) for a in table.index])
    if risk.metrics['volatility_ann'] == 0:
        st.info('组合波动为零：DR、边际风险贡献和风险份额不可用。常数样本不表示真实无风险。')
    else:
        plot=table.reset_index(names='asset_id').copy()
        plot['波动贡献（百分点）']=plot.volatility_contribution_ann*100
        plot=plot.reindex(plot['波动贡献（百分点）'].abs().sort_values(ascending=False,kind='stable').index).head(30)
        chart=alt.Chart(plot).mark_bar().encode(
            x=alt.X('波动贡献（百分点）:Q',title='对年化波动的贡献（百分点）'),
            y=alt.Y('asset_id:N',sort='-x',title='产品 ID',axis=alt.Axis(labelLimit=190,labelOverlap=False)),
            color=alt.condition(alt.datum['波动贡献（百分点）'] < 0,alt.value('#267f87'),alt.value('#254c72')),
            tooltip=['asset_id:N','产品名称:N',alt.Tooltip('波动贡献（百分点）:Q',format='.4f')]
        ).properties(height=max(220,len(plot)*20))
        zero=alt.Chart(pd.DataFrame({'zero':[0]})).mark_rule(color='#778899').encode(x='zero:Q')
        st.altair_chart(chart+zero,width='stretch')
        st.caption('图示绝对贡献最大的30项；完整表保留所有产品与负贡献。负贡献表示当前权重下抵消部分风险。')
    display=table.rename(columns={'weight':'权重','asset_volatility_ann':'个体年化波动','marginal_volatility_ann':'边际波动贡献',
                                  'volatility_contribution_ann':'年化波动贡献','risk_share':'风险份额'})
    config={col:st.column_config.NumberColumn(format='percent',step=0.000001) for col in display if col != '产品名称'}
    st.dataframe(display,width='stretch',column_config=config)
    st.caption('年化波动贡献按百分比显示，例如1%为1个百分点；风险份额是贡献占组合波动的比例。两者不可混用。')


def render_preview(preview,names):
    d=preview.estimate.diagnostics
    st.caption(f"HKD · {d['train_start']} 至 {d['train_end']} · {d['n_observations']}个月 · {d['n_assets']}项")
    tabs=st.tabs(['收益估计','相关性','风险与分散化','方法与导出'])
    with tabs[0]: show_estimates(preview,names)
    with tabs[1]: show_correlation(preview,names)
    with tabs[2]: show_risk(preview,names)
    with tabs[3]:
        st.write('当前资产池回溯研究；时间与结构证据由输入者声明，历史候选池未认证。下列文件对应同一批数据、筛选和权重。CSV保留原始小数，不是界面显示的百分数。')
        st.caption('下载共9份：收益摘要、两种年化协方差、完整相关矩阵、相关状态、两种风险贡献、风险对照及证据。')
        for name,payload in preview_exports(preview).items():
            st.download_button('下载风险 · '+name,payload,file_name=name,
                               mime='application/json' if name.endswith('.json') else 'text/csv',
                               key='ra_export_'+name,on_click='ignore')
        with st.expander('计算证据与方法诊断'):
            import json
            st.json(json.loads(preview_exports(preview)['risk_evidence.json']))
