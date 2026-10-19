# S06-B 相关性与基础风险 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement task-by-task. Steps use checkbox (`- [x]`) syntax.

**Goal:** 按已经确认的S06设计交付原始训练收益Pearson相关性及指定多头权重的基础风险，不新增页面或选择持仓。

**Architecture:** 将A的纯训练收益校验抽为复用函数；相关性独立于收缩协方差。多头计算器校验按ID对齐的年化均值、协方差及显式权重；连接层从原始候选重新筛选及估计，分开输出样本／模型预览。

**Tech Stack:** 现有Python3.14、NumPy、pandas、pytest，无新增依赖或数据下载。

## Global Constraints

- 设计依据 `docs/superpowers/specs/2026-10-17-s06-estimation-risk-design.md` 的S06-B与B/C边界；用户已确认并授权开始B。
- 只训练窗口、HKD小数月收益、资产ID唯一且显式对齐；不补缺值、不逐对删行。
- Pearson基于原始训练样本，常数列包括自身为不可用，不填零。
- 多头权重非负、和为1（绝对容差1e-10），不自动归一化；拒绝做空／布尔／非数值／缺失／多余ID。
- 风险计算使用同一个协方差口径的个体波动和组合波动；默认样本与LedoitWolf分开输出。
- `mu_p=w'mu`，`var_p=w'Sigma w`，`sigma_p=sqrt(var_p)`，波动贡献`w_i*(Sigma w)_i/sigma_p`，占比为贡献/sigma_p；贡献可为负。
- `N_eff=1/sum(w²)`仅表示权重集中度，`DR=sum(w_i*sigma_i)/sigma_p`仅限多头，不保证未来保护。
- 零组合波动时DR、边际贡献、贡献及占比均不可用，使用None／缺失值和原因；已知组合均值、方差、N_eff仍返回。
- 不静默修复明显非对称／非PSD矩阵；负方差和负对角直接阻止，小正方差按原值计算；不把很小的正波动强行置零。
- 本目录无Git仓库；原地开发并保存失败／通过记录，不创建仓库。

### Task 1：Pearson训练相关性

**Files:** Create `src/portfolio/evaluation/__init__.py`, `correlation.py`, `tests/test_correlation.py`; modify `src/portfolio/models/validation.py` 抽取 `training_returns(returns,train_start,train_end)`，保留 `training_input` 原接口。

**Interface:** `pearson_correlation(returns, *, train_start, train_end) -> CorrelationResult`，含 `matrix`、`asset_status`、`diagnostics`、`fingerprint`；字典诊断可用标准JSON序列化。

- [x] 测试先行：同向=1、反向=-1、A/B/C手算矩阵、常数全部不可用、训练外改值不变、输入重排不变、缺值／缺月／重复ID拒绝。
- [x] 运行 `.venv/bin/python -m pytest tests/test_correlation.py -q`，确认因功能缺失失败。
- [x] 抽取原有校验并实现Pearson：先逐列稳定中心化，再缩放归一化内积；常数整行整列保留缺失。仅将1e-12范围内浮点越界截回[-1,1]并披露数量，超过范围阻止。
- [x] 重跑相关性和A全部受影响测试。

### Task 2：多头风险及正式预览连接

**Files:** Create `src/portfolio/evaluation/diversification.py`, `risk_preview.py`, `tests/test_diversification.py`, `tests/test_risk_preview.py`。

**Interfaces:** `portfolio_risk(mean_ann, covariance_ann, weights, *, covariance_method) -> RiskResult`，含 `metrics`字典、逐项`contributions`表、`diagnostics`、`fingerprint`；`preview_candidate_risk(candidate, weights, **screening_options) -> RiskPreview` 含`estimate`、`correlation`、`sample_risk`、`model_risk`、`evidence`。连接要求weights覆盖所有合格ID（未投入项明确0），不自动选成员或绕过S05门槛。

- [x] 测试先行：w=(.5,.5)、mu=(.06,.10)、Sigma=diag(.04,.09)得均值.08、方差.0325；贡献和等于sqrt(.0325)。等权20项N_eff20；完全同向DR1；负相关减风险且可负贡献；完全抵消为不可用；零权重不计有效持仓；混合常数分开经验／模型波动。
- [x] 参数化拒绝错误权重、错位或重复ID、非有限数、非对称、非PSD及负对角；验证无输入修改及重排不变。
- [x] 运行三个新增目标文件确认缺失失败，再实现最小计算和连接；输出元数据标明HKD年化、协方差口径、指定权重研究预览及历史未认证。
- [x] 连接层原始100项恒定样本可返回不可用风险状态；N99必须阻止；非恒定原始100项显示两套独立指标；不跳过数量条件。

### Task 3：离线验收、审查与交付

**Files:** Create `scripts/verify_diversification.py`, `tests/test_diversification_verification.py`, `outputs/acceptance/S06B/README.md`; update README、USER_GUIDE、主流程及进度。

- [x] 先写验收脚本测试，检查手算、相关矩阵、零波动JSON无NaN／Infinity、真实N0、源文件不变和目标文件链接拒绝，运行确认失败。
- [x] 复用A脚本已验证的暂存／别名保护机制；生成 `hand_calculation.csv`、`correlation.csv`、`risk_contributions.csv`、`estimation_diagnostics.json`、`summary.json` 及常数案例；JSON缺失转为null，CSV保留空白。
- [x] 脚本核对手算期望、全同向DR1、20资产N_eff20、负贡献／零波动，并展示非恒定100项样本／模型预览；真实日线仍N0，不冒充真实投资结果。
- [x] 调用requesting-code-review技能的独立只读审查并解决重要问题。
- [x] 运行 `.venv/bin/python scripts/verify_diversification.py`、完整 `.venv/bin/python -m pytest -q`；更新本地已安装包并检查依赖与源码一致。
- [x] 更新文档与完成清单，明确B仅计算核心，C尚未接页面；最后提供用户可直接查验的文件。

执行结果：新增49项，完整回归686 passed、2条原有日历依赖弃用提示。独立审查89项通过，0 Critical／Important；Minor进度文档已更新。另有谱溢出与方法参数类型的失败回归并已修复。代码与已安装包一致、源哈希不变。
