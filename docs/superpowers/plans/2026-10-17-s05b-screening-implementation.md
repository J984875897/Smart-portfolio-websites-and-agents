# S05-B 筛选规则 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 消费已验收 CandidateInput，输出可追溯筛选漏斗和 K/N 数量判断。

**Architecture:** 产品分类独立于数量校验；筛选核心只读取 A 的数据快照，按 asset_id 对齐。补充跨上市身份关系显式输入，不按名称或相关性猜测；输出保留研究模式和来源指纹。

**Tech Stack:** 现有 Python 3.14、pandas、pytest；不增加依赖。

## Global Constraints

- A → B → C；本单元不改页面、不联网、不修改已保存数据。
- HKD、连续 60 月；研究模式 current_universe_retrospective，historical_universe_certified=false。
- 默认排除直接个股，保留普通股票 ETF／基金；未知、杠杆、反向和复杂结构不通过。
- K 为 20–100 整数，拒绝 bool／小数；用 `10*K <= 3*N`，最低 N `(10*K+2)//3`。
- 本目录不是 Git 仓库，原地开发，不创建仓库或提交。

## Task 1：数量规则

Files: `src/portfolio/allocation/cardinality.py`、`tests/test_cardinality.py`。

接口 `check_cardinality(k, n) -> CardinalityResult`，包含 k、n、ratio、minimum_n、shortfall、status、message。无效 K 返回 invalid_k；无效 N 抛 ValueError；N=0 ratio=None。

- [x] 写失败测试：20/66、20/67、30/99、30/100、50/166、50/167、100/333、100/334，以及非法 K、空池、非法 N。
- [x] 运行 `.venv/bin/python -m pytest tests/test_cardinality.py -q` 观察缺实现失败。
- [x] 实现整数运算与明确提示，再运行上述命令通过。

## Task 2：分类与筛选

Files: `src/portfolio/universe/classification.py`、`screening.py`、`tests/test_universe_screening.py`。

接口 `screen_candidates(candidate, *, k, markets=('US','HK'), tool_types=None, asset_classes=None, include_stocks=False, excluded_asset_ids=(), listing_relations=None) -> UniverseResult`。
结果含 eligible_asset_ids、matrix、audit、counts、cardinality、evidence、fingerprint。`universe_result_is_current(result, candidate, **params)` 对输入和选择指纹比较。

listing_relations 可选表：asset_id、product_group、representative_asset_id、review_status、source_name、source_reference、source_as_of。明确重复上市组所有成员有一致证据和组内代表才保留一个；pending 不通过；未提供关系显示 not_verified，不宣称跨市场认证。

- [x] 失败测试覆盖个股/ADR/REIT/优先股开关、股票基金保留、非产品及不支持结构、缺证据、交易所市场冲突、分类冲突、重复身份、代表选择、数据不合格、空范围、手动排除、非法参数。
- [x] 运行 `.venv/bin/python -m pytest tests/test_universe_screening.py -q` 观察缺实现失败。
- [x] 分类模块执行显式枚举和交易所映射；筛选模块验证 A 的窗口/矩阵一致性，生成逐项多原因、稳定列序及分阶段计数。只作结构一致性检查，不将输入者声明提升为独立认证。
- [x] 验证快照不变、过滤变化指纹变化、矩阵与合格 ID 一致；运行两组测试。

## Task 3：离线验收与文档

Files: `scripts/verify_candidate_screening.py`、`tests/test_candidate_screening_verification.py`、`outputs/acceptance/S05B/`、README、PROJECT_PLAN、用户指南、总流程、S05设计。

- [x] 先写 CLI 测试：独立 SYNTH ID 100 项，K=30 时 N=100 通过、手动排除一项 N=99 阻止；A 的真实日线诊断不放宽为合格。
- [x] 观察 CLI 缺失失败，再实现离线导出 cardinality_cases.csv、universe_audit.csv、summary.json、README；源文件散列前后比较，拒绝输出覆盖源路径。
- [x] `.venv/bin/python scripts/verify_candidate_screening.py` 生成验收；独立复核后修复重要发现并补回归。
- [x] `.venv/bin/python -m pytest -q` 保存完整输出；安装本地包并验证运行时模块一致。
- [x] 更新文档和任务勾选，说明 B 已交付文件验收、C 页面下一步。
