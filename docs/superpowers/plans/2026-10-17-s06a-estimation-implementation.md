# S06-A 收益与协方差 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 交付训练窗口内 HKD 收益均值、类别收缩、样本／Ledoit–Wolf 协方差与可复核诊断。

**Architecture:** 纯数值核心与输入检查独立于 S05 资格连接。连接层重新筛选，数量通过且完整 60 月才估计；计算结果不赋予历史资格或生成组合。独立离线脚本输出验收材料。

**Tech Stack:** 现有 Python 3.14、NumPy、pandas、scikit-learn 1.9.1、pytest；无新增下载。

## Global Constraints

- 已确认设计：`docs/superpowers/specs/2026-10-17-s06-estimation-risk-design.md`；本轮仅 A。
- 收益均值 50% 个体＋50% 同类等权均值；年化均值及协方差乘 12。
- 样本协方差 ddof=1；LedoitWolf 经验协方差分母 T，两者单独标明。
- 禁止未来数据参与训练统计；不填缺值、不默默修复非半正定矩阵。
- 稳定资产 ID 对齐；正式输入须通过 S05 数量规则与 60 月检查。
- 项目无 Git 仓库，原地修改，不初始化仓库；保留各步测试记录代替提交记录。

### Task 1：估计核心

**Files:** Create `src/portfolio/models/__init__.py`, `validation.py`, `moments.py`; test `tests/test_moments.py`; modify `pyproject.toml` 声明已锁定的 scikit-learn。

**Interfaces:** `estimate_moments(returns: DataFrame, asset_classes: Series, *, train_start: str, train_end: str) -> EstimateResult`；结果持有排序资产 ID、历史／类别／收缩均值、样本／收缩月年协方差、波动、诊断和训练指纹。

- [x] 先写手算测试：月均值 `[.025,.035,.01]`，年均值 `[.30,.42,.12]`；月样本协方差 `[[.0001,.0001,.00005],[.0001,.0001,.00005],[.00005,.00005,.0001]]`。
- [x] 先写 Ledoit–Wolf 独立混合式、60×100、训练外改值不变、重排不变、异常和退化测试。
- [x] 运行 `.venv/bin/python -m pytest tests/test_moments.py -q`，确认因功能缺失失败。
- [x] 实现输入检查和核心：显式窗口截取后校验、排序对齐、计算统计与退化诊断。使用 `LedoitWolf(store_precision=False, assume_centered=False)`；输入常数列精确中心化为零以免浮点噪声制造波动。
- [x] 重跑目标测试，检查有限值／对称／半正定诊断以及单成员类别说明。

### Task 2：S05 资格连接

**Files:** Create `src/portfolio/models/estimation_input.py`; test `tests/test_estimation_input.py`。

**Interfaces:** `estimate_candidates(candidate: CandidateInput, **screening_options) -> EstimateResult`；内部重新执行 `screen_candidates`，从合格矩阵和审计类别计算，将筛选及输入指纹和证据复制到诊断。

- [x] 先写原始 100 项退化、非恒定 100 项、排除一项数量阻止、真实日线 N0、源数据不变测试。
- [x] 运行 `.venv/bin/python -m pytest tests/test_estimation_input.py -q`，观察预期失败。
- [x] 实现连接：拒绝数量不通过；明确 60 月；不可将低层估计成功当作正式持仓或历史候选认证。
- [x] 重跑 A 的全部新测试。

### Task 3：验收、审查与交付

**Files:** Create `scripts/verify_estimation.py`, `tests/test_estimation_verification.py`, `outputs/acceptance/S06A/README.md`; update project README、使用指南、主开发流程与进度。

- [x] 先写脚本离线输出及输入／输出路径隔离测试，运行确认缺失失败。
- [x] 脚本使用独立手算期望值、固定种子 60×100、S05 人工与真实阻止输入；CSV 和 JSON 用断言核对，JSON 禁止 NaN／Infinity，输出不可覆盖源数据。
- [x] 执行 `.venv/bin/python scripts/verify_estimation.py` 检查产物。
- [x] 按 requesting-code-review 技能调用只读审查，修复重要问题；必要时先添加回归失败案例。
- [x] 运行 `.venv/bin/python -m pytest -q`，保存完整结果；安装本地包并核对新模块可导入、依赖一致。
- [x] 文档明确 A 仅计算核心、B／C 未实现、真实数据资格不足和人工案例局限；清单仅在证据充分时勾选。

执行结果：43项新增检查，完整回归637 passed、2条原有日历依赖弃用提示。独立审查1项Important（输出文件别名）已先回归复现后修复，并复查关闭；见 outputs/acceptance/S06A/review.md。所有实现与验收步骤完成，无Git提交。
