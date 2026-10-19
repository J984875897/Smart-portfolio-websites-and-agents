# S03-A 实施与查验任务

> 执行用户已授权 S03 的首个子交付，使用 subagent-driven-development；不继续 S03-B/C 或 S04。当前目录没有 Git，以独立新模块和文件备份隔离，不初始化仓库或创建提交。

**Goal:** 给月末总收益输入提供可复算 HKD 对照及准确的缺失/不适用状态。

**Architecture:** 原币收益标准化及 FX 验证在 Python 核心；界面只调用核心，保留 S02 数据不变。S03A 结果为派生视图，不覆盖旧导入版本。

**Tech Stack:** 已有 pandas、pytest、Streamlit、openpyxl；不安装新依赖。

## Global Constraints

以 [S03-A 设计](../specs/2026-10-13-s03a-hkd-design.md) 为完整规则。每单位外币对应 HKD；金额及收益必须有限。只有明确的 monthly 自然月末观察参与本步；外币 FX 必须精确匹配起止日期；缺失不是零，普通价格不是总收益，复权需来源确认，不能重复加分红。原 `DataBundle` 和 S02 界面行为不变；未完成时间对齐、N、优化和 Sharpe 必须明确说明。

### Task 1：原币收益、FX 验证及换算核心

Files: `src/portfolio/data/returns.py`, `src/portfolio/data/fx.py`, `tests/test_returns.py`, `tests/test_fx.py`；不修改 S02 契约。Interfaces 见设计文档。

- [x] 写独立预期案例的失败检查并保存实际 red 输出到 `outputs/acceptance/S03A/core_red.txt`。
- [x] 实现设计中函数及逐行失败原因，处理重复、缺月、无效日期、值、币种、精确日期、来源；保存核心报告 `core_report.md` 并说明接口列名。
- [x] 运行 `.venv/bin/python -m pytest tests/test_returns.py tests/test_fx.py -q`，保存实际 green 输出。
- [x] 独立审查需求、计算及失败行为，修复重要发现并重跑受影响测试。

核心检查的独立期望：

```python
expected_hkd = 0.02294871794871795  # local=.01, FX=7.8 -> 7.9
expected_local = 0.01              # adjusted prices 100 -> 101
expected_hkd_native = 0.01         # no FX required
# missing FX / unconfirmed adjusted price / ordinary price => status blocked, NaN HKD
# previous Dec price and Feb price without Jan => no Feb monthly return
```

### Task 2：可操作界面查验

Files: `app/main.py`, `app/views/hkd_returns.py`, `tests/test_hkd_returns_view.py`, `tests/fixtures/hkd/`。先备份 `app/main.py` 到验收目录。消费 Task1 的三个公开函数；不重写金融公式。

- [x] 先写 AppTest 失败检查：切换页，载入测试案例，换算数值，当前 bundle 不变，参数/FX/数据变化失效，缺 FX 失败；记录 red。
- [x] 保留默认 S02 页，增加中文页导航及 S03A 页面；人工案例有中文用途说明，不仅展示英文文件名。
- [x] 支持当前导入 bundle、FX CSV/XLSX 及 sheet、模板、按资产确认复权、显式计算、对照表/错误/CSV 下载；空数据和错误输入提供局部提示。
- [x] `.venv/bin/python -m pytest tests/test_hkd_returns_view.py tests/test_data_center.py -q` 保存实际 green 和任务报告 `ui_report.md`。
- [x] 审查用户操作状态、失败结果和 S02 回归。

### Task 3：可复算证据与阶段状态

Files: `scripts/verify_hkd.py`, `outputs/acceptance/S03A/README.md`, `checks.txt`, `progress.md`, `README.md`、分步流程文件。

- [x] 脚本通过真实 S02 import pipeline 读取固定人工输入并调用核心，输出 `hkd_reconciliation.csv`, `local_returns.csv`, `fx_issues.csv`, `failure_cases.csv`, `summary.json`；断言独立期望值与缺失失败，保留源 hash，禁止联网。
- [x] 更新已安装本地包：`.venv/bin/python -m pip install --no-deps --no-build-isolation --force-reinstall .`。
- [x] `.venv/bin/python scripts/verify_hkd.py` 和完整 `.venv/bin/python -m pytest -q`，检查实际结果，保存证据。
- [x] 独立最终审查，修复重要问题；检查浏览器 HTTP/健康状态与页面（可执行时），重启原本地服务使安装包更新生效。
- [x] 文档写清 S03A 可查验，S03B/C 未开始；本轮收尾提供入口、手算结果、缺失行为及下一子步骤。
