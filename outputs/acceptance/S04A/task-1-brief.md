# Global constraints


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

- [ ] 写 tests/test_updates.py，测试公共行为：run_update 成功可 load；raw 字节一致；每项请求只一次；解析与 S01 原断言一致；修订值第二版不改第一版；坏格式/身份/HTTP429/超时/缺价；部分成功标记；项前和返回后取消；读取零请求；坏 hash/越界/无效 run_id；本地保存失败旧版不变；参数不合法零请求。

```python
def test_raw_and_revision(tmp_path, chart_bytes):
    first = run_update(tmp_path, ['SPY'], '2025-01-01','2025-02-01', fetch=lambda *a: RawResponse(chart_bytes,200))
    manifest = load_snapshot(tmp_path, first)
    item = manifest['items'][0]
    assert read_artifact(tmp_path, first, item['raw_file']) == chart_bytes
    assert item['status'] == 'success'
```

- [ ] `.venv/bin/python -m pytest tests/test_updates.py -q`，保存 RED。
- [ ] 实现上述接口；函数按职责拆开；S01 从 providers 导入原两个函数，不保留重复实现。
- [ ] 运行新测试及 tests/test_source_probe.py，保存 GREEN；自查后报告实现、RED/GREEN、具体数值和未解决问题，不跑全套。
