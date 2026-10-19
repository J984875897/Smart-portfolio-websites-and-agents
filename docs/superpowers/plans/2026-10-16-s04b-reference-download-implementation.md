# S04-B Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development; execute one task at a time with review checkpoints. No Git repository exists; preserve baseline/diffs instead of creating commits.

**Goal:** 在用户手动触发下下载、核验并离线查验四套 French 因子及 HKMA 官方 FX。

**Architecture:** 来源适配器负责格式和 HTTP；reference_updates 负责编排、覆盖、原子快照；snapshots 共用完整性检查并兼容 Yahoo schema 1。独立 Streamlit 页只调用核心及缓存。

**Tech Stack:** 现有 .venv、pandas、curl_cffi、Streamlit、pytest；不增加依赖。

## Global Constraints

- 免费无 key，只有用户明确开始下载时联网；不引入付费 API。
- FF3／FF5 的 SMB 分开，地区代理不是香港专属，USD RF 不是港币现金代理。
- HKMA 使用官方 er-eeri-daily，usd 为 HKD per USD，不替换为 Yahoo。
- 缓存读取及每次导出校验全部文件；禁止路径穿越、符号链接、未列出的或无引用文件。
- 不认证逐日交易日历完整性；不自动保存到 DataBundle。
- 新来源 schema 2 默认独立 data/reference_downloads；原 Yahoo schema 1 完全兼容。

### Task 1：核心下载与快照

**Files:** providers/french.py、providers/hkma.py、reference_updates.py、snapshots.py、scripts/probe_sources.py、tests/test_reference_updates.py（均在现有对应目录）。具体要求见 outputs/acceptance/S04B/task-1-brief.md。

**Interfaces:** `REFERENCE_CATALOG` 常量在 reference_updates；`validate_reference_plan(datasets,start,end,timeout=15,page_size=1000,max_pages=20)->tuple[str,...]`；`fetch_reference(dataset,start,end,timeout,offset=0,page_size=1000)->RawResponse`；`run_reference_update(root,datasets,start,end,*,timeout=15,page_size=1000,max_pages=20,fetch=fetch_reference,cancelled=lambda:False)->str`；共用 list_runs/load_snapshot/read_artifact/update_log（日志需兼容新来源）。

- [x] 写失败检查并记录 RED：非法计划零网络零落盘、ZIP 月度块／百分数／缺值／年度排除、四模型字段、HKMA 两页／短页／重复／越界／满页上限／中页失败、取消、429、超时、格式变化。
- [x] 最小实现来源适配与 schema 2 快照；保留 S01 parse_french/parse_hkma 引用兼容，避免第二套金融算法。
- [x] 检查完整性、历史修订新旧版、失败保留旧版、符号链接／篡改、没有泄漏凭据或异常原文；GREEN 覆盖新核心和 S01／S04-A。
- [x] 写报告和 diff，独立审查；修复后复查。

### Task 2：用户可查验页面

**Files:** app/views/reference_downloads.py、app/main.py、tests/test_reference_downloads_view.py。接口及明细见 task-2-brief.md。

- [x] 先写 AppTest RED：预览／取消不联网、显式开始才调用、参数变化使计划失效、失败不替换旧版、损坏缓存不可导出、partial 仅诊断。
- [x] 最小实现独立页、数据集选择、日期／超时／分页上限、最大请求数、明确来源／币种／频率、逐项状态、缓存版本、数据／原始证据／清单／日志导出，不提供产品导入交接。
- [x] GREEN 核对新页面及原下载页；写报告和 diff，独立审查并修复。

### Task 3：真实样本、离线重放、交付

**Files:** scripts/verify_reference_downloads.py、outputs/acceptance/S04B/*、README.md、workflow。

- [x] 一次正式真实请求四套 French 加 HKMA，失败如实保存；不关闭 TLS 验证、不自动重试。
- [x] 对照原始 CSV 百分数与派生小数、月份、模型、汇率方向；全部哈希及离线重放一致。记录未取得的证据。
- [x] 安装本地包，刷新应用；核对界面健康及宽窄屏／无重叠，保留截图。
- [x] 全套回归、最终独立审查、验收说明和步骤状态更新。仅 S04-B 范围，不跳到 S05。
