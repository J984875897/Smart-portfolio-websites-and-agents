# S06-B 相关性与基础风险：验收入口

本步交付计算核心与候选研究预览，没有新增工作台页面；C负责接入界面。没有自动选出K项成员、优化权重、utility或做空。以下是人工计算验证，不是实际投资建议或预测。

## 先看这些文件

- [两资产及边界手算](hand_calculation.csv)：two_asset_diagonal 的均值8%、方差0.0325、年化波动约18.0278%；twenty_identical 的有效持仓数20，但DR仍为1，说明持仓多不自动代表分散化。
- [逐项风险贡献](risk_contributions.csv)：两资产贡献之和等于组合波动；negative_contribution案例中B贡献为负，保留其对冲作用。
- [相关矩阵CSV](correlation.csv)／[JSON](correlation.json)：A–B=1、A–C=0.5、A–NEG=-1，CONST整行整列（包括自身）不可用。CSV空白、JSON null，不填零或1。
- [样本与模型对照](qualified_risk_comparison.csv)：同一人工合格100项、同一指定权重、同一训练窗口，分别计算样本／Ledoit–Wolf协方差的风险。不是选出30项正式组合。
- [估计及风险诊断](estimation_diagnostics.json)、[资格与权重证据](qualified_evidence.json)、[真实阻止表](real_blocked_audit.csv)、[汇总及源哈希](summary.json)。

## 指标如何理解

`volatility_contribution_ann`是对组合年化波动的贡献，单位与波动相同；`risk_share`是贡献占组合波动的比例。贡献可能为负，不要求逐项均正。`marginal_volatility_ann`是波动对权重的边际敏感度。

有效持仓数`1/sum(w²)`衡量权重集中程度，不代表独立风险来源。多头分散化比率DR为加权个体波动／组合波动，分子分母必须用同一种协方差口径。历史相关性、DR或低波动不保证未来保护。

组合波动为零时，DR、边际贡献、波动贡献和占比均显示不可用；已知均值、方差和有效持仓数仍保留。经验零波动不是无风险结论，模型也可能给常数资产正方差，两种口径分开呈现。

Pearson基于同一完整HKD月收益训练样本，不使用收缩协方差倒推，也不逐对删缺失。公式及常数不可用语义参考 [SciPy 官方说明](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.pearsonr.html)。

## 使用与边界

```bash
.venv/bin/python scripts/verify_diversification.py
.venv/bin/python -m pytest tests/test_correlation.py tests/test_diversification.py tests/test_risk_preview.py tests/test_diversification_verification.py -q
```

预览接口要求权重按全部合格资产ID绑定，不投入的产品明确给0；不自动归一化、不接受负权重。目标K与非零权重数单独记录，底层数学案例不能绕过正式组合的20–100项要求。

候选接入重新执行S05筛选和S06-A估计。N99仍因候选池不足而阻止；真实日线仍N0，来源资格和月度桥接没有被绕过。人工100项恒定收益仍为不可用相关性／零波动案例。

脚本只读本地资料，无下载。输出目录不能与源目录重叠，已有输出符号链接／硬链接被拒绝；暂存完整产物后替换文件，并在发布前后核对源哈希。开发与最终验证记录随本目录保留。

最终验证：**新增49项检查，完整回归686 passed、2条原有日历依赖弃用提示**，见[完整日志](full_test_checks.txt)。[独立审查](review.md)89项通过，无Critical／Important；依赖检查见[dependency_checks.txt](dependency_checks.txt)。首次失败证据为core_red.txt、preview_red.txt、verification_red.txt、overflow_red.txt、method_red.txt。
