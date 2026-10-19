# S04-C3 Time Eligibility Implementation Plan

> **For agentic workers:** Use executing-plans to implement this plan task-by-task, with test-driven-development and verification-before-completion.

**Goal:** 查验 C2 观测版本在给定决策时点的本地可得证据。

**Architecture:** 下载器记录完成时点；只读证据加载器重验文件并绑定原始散列；纯函数逐行判断时间资格；Streamlit 展示及导出。

**Tech Stack:** Python, pandas, pytest, Streamlit AppTest。无新依赖。

## Global Constraints

- completed_utc 不能由 created_utc 推算；旧缓存不得回填。
- decision_at 必须含时区；completed_utc 必须 UTC 且不早于开始。
- USD 同时需要 price / FX；HKD 仅需 price。
- 人工声明不升级资格；历史 universe 资格始终 false。
- 不修改 C2 或保存数据，不自动联网。
- 工作区无 Git 仓库，使用文件和验收记录交付，不创建仓库。

## Task 1: 下载完成时点

Files: updates.py, reference_updates.py, snapshots.py；tests/test_updates.py, tests/test_reference_updates.py。

- [x] 添加离线下载测试，断言 completed_utc 在响应取得之后且 >= created_utc；旧快照仍可读取；非法新字段被拒绝。
- [x] 运行 `.venv/bin/python -m pytest tests/test_updates.py tests/test_reference_updates.py -q`，确认缺失新字段而失败。
- [x] 两种下载器在写完数据后生成 completed_utc；load_snapshot 对可选字段检查时区及顺序。
- [x] 重跑上述测试并检查兼容性。

## Task 2: 证据与资格函数

Files: src/portfolio/data/time_eligibility.py；tests/test_time_eligibility.py。

Interfaces: CaptureEvidence(source_hash, completed_utc, source_status, run_id); load_price_capture(root, run_id, symbol); load_fx_capture(root, run_id); qualify_daily_hkd(result, *, decision_at, price_capture=None, fx_capture=None, declared_available_at='') -> TimeEligibilityResult(rows, metadata)。证据加载器调用现有哈希验证缓存函数，纯函数只消费证据，不访问网络或磁盘。

- [x] 添加相等/较晚边界、时区、缺时间、散列、partial、HKD/USD、人工声明与无修改测试；运行新测试确认缺少模块失败。
- [x] 实现上述接口，保留所有 C2 行和原始字段，添加 time_status/time_reason/historical_observation_eligible/historical_universe_eligible 及时间、散列列。
- [x] 加载器重验快照并提取实际 raw hash / 组合 FX hash；缺失新时间返回空值。
- [x] 运行 `.venv/bin/python -m pytest tests/test_time_eligibility.py -q`。

## Task 3: 页面、文档及交付

Files: app/views/time_eligibility.py, app/main.py, tests/test_time_eligibility_view.py, README.md, workflow plan, outputs/acceptance/S04C3/README.md。

- [x] 添加 AppTest 覆盖默认案例、决策时点改变、无 C2、缓存失效、导出和原始 bundle 不变，先运行确认失败。
- [x] 页面提供上一页 C2 / SYNTH 示例；根据 C2 run_id 和配置根目录重新加载证据，自动重算并导出。错误时不保留结果。
- [x] 运行针对测试，然后 `.venv/bin/python -m pytest -q`。
- [x] 重新安装本地包 `.venv/bin/python -m pip install --no-deps --no-build-isolation --no-cache-dir --force-reinstall .`，核对可导入。
- [x] 更新使用说明与验收结果；逐条对照设计并记录限制。
