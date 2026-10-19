# S04-A 下载与缓存 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 在页面手动下载七个识别样本中的所选日线，验证离线缓存、失败保留和 S02 导入交接。

**Architecture:** 提取 S01 Yahoo 解析器，provider 返回原响应；updates 独立逐项校验，snapshots 以不可变 run 目录原子发布并校验读取。页面只组织计划、显式请求、缓存检查与现有导入流程交接。

**Tech Stack:** Python 3.14、pandas、已安装 yfinance/curl_cffi、Streamlit、pytest/AppTest；不加依赖。

## Global Constraints

- 范围固定为 AAPL、0700.HK、SPY、2800.HK、AGG、GLD、HKD=X 七个识别样本，可多选。
- 日期严格 YYYY-MM-DD，起日包含、止日不含，start < end；每项一次公开 chart 请求，不自动重试、不接收 key、不登录。
- 超时默认 15 秒，范围 1–30 秒。
- 每项状态 success / partial / unavailable / cancelled；success 只表示来源字段检查通过，不代表完整交易日历、历史可得时间或 S05 候选合格。
- 原始 chart 响应按原字节保存；所有派生文件在清单校验内；旧目录始终不修改。
- 使用缓存不触发任何网络；更新结果与已打开缓存分开，失败后仍显示旧缓存及其日期。
- 不记录异常文本、认证头、cookie、crumb 或密钥。
- 不自动 commit 或保存 bundle；本步不计算月度 HKD 收益、Sharpe 或候选资格。
- 当前无 Git，以 /private/tmp/portfolio-s04a-before 生成文件差异代替提交，不初始化仓库。

## Task 1: provider、更新和不可变快照

**Files:** 新建 src/portfolio/data/providers/{__init__,base,yahoo}.py、snapshots.py、updates.py、tests/test_updates.py；修改 scripts/probe_sources.py。输出 outputs/acceptance/S04A/task-1-report.md。

**Interfaces:**

```python
# providers/base.py
@dataclass(frozen=True)
class RawResponse:
    body: bytes
    status_code: int
# providers/yahoo.py
CATALOG: dict[str, dict]  # 精确七样本；包含 ticker/name/tool_type/asset_class/exchange/currency/provider_type
def fetch_yahoo(symbol: str, start: str, end: str, timeout: float) -> RawResponse: ...
def parse_yahoo_chart(payload: dict) -> tuple[pd.DataFrame, dict]: ... # 从 S01 原样提取
def audit_price(table, meta, currency, provider_type, *, symbol=None,start=None,end=None) -> dict: ... # 同上
# updates.py
def validate_plan(symbols, start: str, end: str, timeout: float=15) -> tuple[str,...]: ...
def run_update(root: Path, symbols, start: str, end: str, *, timeout: float=15,
               fetch=fetch_yahoo, cancelled=lambda:False) -> str: ... # 返回 run_id
# snapshots.py
def list_runs(root: Path) -> list[str]: ... # 只列已完成且命名有效目录；新在前
def load_snapshot(root: Path, run_id: str) -> dict: ... # 校验，返回 manifest
def read_artifact(root: Path, run_id: str, filename: str) -> bytes: ... # 已列文件且全快照校验
def update_log(root: Path) -> pd.DataFrame: ... # 逐项历史，损坏版本明确报错
```

manifest schema_version=1, run_id, provider='Yahoo chart', created_utc, start, end_exclusive, timeout, items:list, files:list。item 必须含 symbol/status/reason/rows/raw_file/daily_file/import_file/raw_sha256；失败缺文件用 null，不能伪装成功。files 每项 path/sha256/bytes。raw_<safe symbol>.json、daily_<safe symbol>.csv、import_<safe symbol>.csv。run_id UTC时间+UUID且路径组件严格校验。目录 root/runs/<run_id>，临时目录在 root 内。保存函数可由实现者集中在 snapshots.py，需保持各职责清楚。

导入 CSV 同名字段：ticker/name/tool_type/asset_class/exchange/currency/share_class/frequency/date/value；frequency=daily，value=adj_close。HKD=X 不生成 import_file。身份来自 S01 样本；tool_type stock/ETF/gold_trust 与 S02 枚举匹配，经济类型 equity/bond/commodity。部分数据保留 NaN，partial 不生成 import_file。原始 JSON 存所有实际收到的 HTTP 响应；fetch 抛异常没有原响应。异常仅保存类型归类码，不保存原文本。捕获预期传输/解析异常并继续下一项，本地 IO 错误必须传播，不能变成下载成功。取消在每项前和返回后检查，保留已收原响应但取消项不生成导入版本。

- [x] 写 tests/test_updates.py，测试公共行为：run_update 成功可 load；raw 字节一致；每项请求只一次；解析与 S01 原断言一致；修订值第二版不改第一版；坏格式/身份/HTTP429/超时/缺价；部分成功标记；项前和返回后取消；读取零请求；坏 hash/越界/无效 run_id；本地保存失败旧版不变；参数不合法零请求。

```python
def test_raw_and_revision(tmp_path, chart_bytes):
    first = run_update(tmp_path, ['SPY'], '2025-01-01','2025-02-01', fetch=lambda *a: RawResponse(chart_bytes,200))
    manifest = load_snapshot(tmp_path, first)
    item = manifest['items'][0]
    assert read_artifact(tmp_path, first, item['raw_file']) == chart_bytes
    assert item['status'] == 'success'
```

- [x] `.venv/bin/python -m pytest tests/test_updates.py -q`，保存 RED。
- [x] 实现上述接口；函数按职责拆开；S01 从 providers 导入原两个函数，不保留重复实现。
- [x] 运行新测试及 tests/test_source_probe.py，保存 GREEN；自查后报告实现、RED/GREEN、具体数值和未解决问题，不跑全套。

## Task 2: 可查验页面与导入交接

**Files:** 新建 app/views/downloads.py、tests/test_downloads_view.py；修改 app/main.py、app/views/data_center.py（仅交接所需）。输出 outputs/acceptance/S04A/task-2-report.md。

**Consumes:** Task 1 所有公开接口。缓存根目录 PORTFOLIO_DOWNLOADS_ROOT，默认 ROOT/data/downloads。统一由 view.downloads_root() 取值方便隔离；不在导入时创建/下载。

**Produces:** 侧栏“下载与缓存”，原页面默认不变。控件 key 前缀 dl_，symbols 多选默认 SPY/2800.HK，date_input 默认 2025-01-01/2025-02-01，timeout 默认15。`dl_prepare` 生成纯计划；`dl_start` 开始下载；`dl_cancel` 取消计划。参数指纹变化清计划，结果带原请求范围，不作为新参数的结果。用原生控件和中文状态/原因，预览逐项身份及请求数。清楚提示取消在开始前，下载进行中单请求超时上限。

缓存区域列已完成 run；打开 run 校验全部文件；展示逐项状态和时间，只有 success 项可作为缓存使用。`dl_open` 打开所选run，`dl_active` 存已验证manifest/run identity；失败打开或失败下载不替换旧active。更新结果 `dl_result` 与active分开，不自动覆盖。可选择已打开缓存中的成功 symbol，显示原币日线和原始清单；导出 update_log.csv、snapshot_manifest.json、日线与对应导入CSV。点击缓存操作、改变参数及导航都零网络。

`dl_to_import` 通过回调交接至 S02（回调先于侧栏radio渲染）。调用 set_source，kind=adjusted_price，unit=decimal，supplier 写 Yahoo chart/run_id/raw sha256。用生成的同名 CSV，不自动 commit。旧file_uploader可能仍带内容：需清除旧 uploader session state/token，使交接内容保持不被覆盖；不要破坏普通上传重选。S02来源显示 filename 包含 run_id 方便追踪。HKD=X 导出日线并说明方向、不提供送入产品导入。未交接时 S02 bundle 无变化。

- [x] 写 AppTest：默认零下载、计划+取消零下载、参数变更清计划、显式按钮才下载、部分结果逐项显示、失败保留active、离线打开与导出、损坏不替换active、交接精确字段/口径/来源和保留bundle、旧上传不覆盖、FX禁止产品导入。

```python
def test_no_auto_download(monkeypatch, tmp_path):
    monkeypatch.setenv('PORTFOLIO_DOWNLOADS_ROOT',str(tmp_path))
    monkeypatch.setattr('app.views.downloads.run_update',lambda *a,**k: (_ for _ in ()).throw(AssertionError('unexpected download')))
    at=AppTest.from_file('app/main.py').run()
    at.radio(key='workspace').set_value('下载与缓存').run()
    at.button(key='dl_prepare').click().run()
    at.button(key='dl_cancel').click().run()
    assert not at.exception
```

- [x] 运行该测试，记录 RED；实现最小页面和交接后记录 GREEN。
- [x] 运行 tests/test_data_center.py（若实际名不同用 rg 确认原 S02 view 测试）和新测试；报告精确测试命令、结果、自查发现。不要联网或运行全套，controller 统一集成验证。

## Final acceptance（controller）

- [x] 每项任务独立审查通过；差异与审查记录保存。
- [x] 真实 SPY/2800.HK/HKD=X 小样本下载，离线同快照重读；逐项报告行数、缺失、币种及原始哈希。不将在线失败写为成功。
- [x] `.venv/bin/python -m pytest -q` 全套回归。
- [x] 真实浏览器 1440/720 截图、正常缓存及失败保留旧版检查；检查无重叠/异常/额外网络调用。
- [x] 最终独立审查无未处理 Critical/Important；更新 README、workflow、acceptance README 及 progress。只标 S04-A，S04 总体未验收。
