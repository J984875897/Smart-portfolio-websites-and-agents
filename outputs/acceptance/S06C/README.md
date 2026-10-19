# S06-C 收益与风险界面验收

日期：2026-10-17。开发验收通过：完整回归713 passed、2条原有日历依赖弃用警告；本步新增27项。独立审查27项通过，未关闭Critical／Important／Minor均0。

## 如何使用

本次新版实例：http://127.0.0.1:8502 。旧8501实例保持运行，不保证加载本次模块；打开8502体验。

在项目目录重启：

```bash
.venv/bin/python -m streamlit run app/main.py --server.address 127.0.0.1 --server.port 8502 --server.headless true --browser.gatherUsageStats false
```

1. 左侧「候选筛选」→「SYNTH 相关性与风险演示」，其他保持默认。
2. 「查验数据并筛选」应得K30、N100。向下「收益与风险预览」保留等权，再点「计算收益与风险」。
3. 四页签查看收益估计、相关性、风险与分散化、方法与导出。热图默认20项，选2–30项只改变展示；完整相关矩阵始终100×100。
4. 自定义权重从本次模板填写。严格两列asset_id、weight；全部ID须出现，非负且和为1，零权重明确填写，不自动归一化。
5. 修改研究输入或权重后旧结果与风险下载撤下；需重算。图表和表格展示选择不改变计算指纹。

## 已验证行为

- 经验与Ledoit–Wolf协方差分别展示，同一估计收益和权重；个体与组合风险口径一致。
- K、N、正权重数分别显示。默认100项等权只是候选池风险诊断，不表示已选出目标30项。
- 人工同向两项各50%时经验DR=1；反向项可有负贡献，贡献之和等于组合波动。
- 常数收益相关性留空；全常数经验波动为零时DR／风险贡献份额不可用，JSON为null。常数不表示真实无风险。
- 自定义权重异常、源数据／范围／时间变化、N99与真实N0会清除或阻止风险结果与下载。
- CSV超出两列不能被pandas静默当作索引；明确提示列结构错误，不误报编码错误。
- 表格提高百分比精度，避免小额贡献显示成0%；贡献图保留可辨认的稳定ID、正负方向及百分点单位。

## 浏览器证据

[browser_checks.json](browser_checks.json)记录1440、720、390宽×4页签共12项检查，无页面横向溢出或异常；热图和数据表在各自容器内滚动。主进程已视觉核对截图中的文字、轴、正负贡献与窄屏状态。

- [宽屏风险](risk_1440.png)、[窄屏风险](risk_390.png)、[窄屏相关性](correlation_390.png)。其余截图按页签和宽度命名。
- 实际浏览器下载：[完整相关矩阵](browser_correlation.csv)、[风险对照](browser_risk_comparison.csv)、[等权计算证据](browser_risk_evidence.json)。
- 实际上传两项同向权重并下载：[自定义计算证据](browser_custom_risk_evidence.json)，正权重2、DR=1。
- 实际上传错误行结构后结果和下载撤下：[截图](invalid_weights_results_cleared.png)。
- [browser_run.txt](browser_run.txt)记录脚本结果。

复跑浏览器需有本机Chrome CDP9224及8502新版工作台，不访问外部网站：`node scripts/verify_risk_workspace_browser.mjs`。脚本会重写本目录同名验收截图和浏览器下载样本。

## 测试与限制

新增 `tests/test_risk_workspace_helpers.py` 和 `tests/test_risk_workspace_view.py`；[完整回归](full_test_checks.txt)、[依赖检查](dependency_checks.txt)、[审查](review.md)与[验证汇总](verification_summary.json)同目录保存。`helpers_red.txt`、`view_red.txt`记录功能缺失时失败，`csv_shape_red.txt`、`csv_message_red.txt`记录额外字段和错误提示回归的先失败证据。

本步不新增网络数据／依赖，不修改真实源版本。真实日线仍N0，历史候选池未认证。本步不做正式成员选择、做空、utility或优化。所有SYNTH数值仅为人工方法验证。
