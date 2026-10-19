# 研究工作台界面重设计 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 将研究数据工作台重组为按研究阶段导航的中文界面，让用户能看见当前研究状态、阻止原因和下一步，同时完整保留现有数据与计算行为。

**Architecture:** 在现有 Streamlit 单页应用外增加只读状态投影、统一页面外壳和集中路由表。`app/main.py` 只负责初始化、渲染侧栏和根据稳定路由调用既有页面；所有业务计算继续留在当前 view 与 `portfolio` 模块。逐步为现有页面包上统一的页首、状态条、结果和证据分区，绝不在新壳层调用下载、保存或风险计算。

**Tech Stack:** Python 3.14、Streamlit、pandas、pytest、Streamlit `AppTest`、现有本地数据合同。

## Global Constraints

- 不实现 S07 成员选择、S08 utility／优化、做空、CAPM／FF3／FF5 或新风险模型。
- 不下载、修改或认证外部来源；不解除真实日线 N=0 或历史候选池认证限制。
- 研究总览只读取 `st.session_state`，不得调用下载、风险计算、导入保存或改变现有状态。
- 继续保留 `workspace` 会话键及原中文页面值，直到全部既有 AppTest 和下载页交接逻辑已迁移并验证。
- 同一业务页面只能保留一份渲染函数和一份会话状态；主流程和高级入口共用该函数。
- 所有状态按既有结果显示：`partial`、`tls_error`、人工时间声明和未认证历史池不可显示成功绿色。
- 不修改 `portfolio/` 中的计算、数据合同或数值口径；若发现必须改动，停止本计划并另建带数值回归的任务。
- 在 1440、720、390 像素宽度验收；容器内宽表横向滚动允许，页面级横向溢出和文字重叠不允许。
- 本目录尚未初始化 Git；每个任务完成后运行所列测试和记录结果，不执行虚构的提交命令。

---

## File Structure

- Create: `app/views/workspace_state.py` — 将既有会话键投影成不可变的研究阶段状态、卡片和确定下一步。
- Create: `app/views/page_chrome.py` — 渲染统一页首、状态条、结果／证据标题和跨页跳转按钮。
- Create: `app/views/workspace_shell.py` — 路由常量、分组侧栏、全局 CSS、研究总览和演示入口。
- Create: `app/views/eligibility_hub.py` — 只读资格中心，展示四类现有核对工具和目标入口。
- Modify: `app/main.py` — 使用路由表和新壳层替代平铺 radio／`if` 链，保留 `workspace` 兼容同步。
- Modify: `app/views/data_center.py` — 将导入页改为“01 准备数据”的统一页面骨架。
- Modify: `app/views/candidate_screening.py`, `app/views/risk_analysis.py`, `app/views/screening_display.py` — 将主流程筛选与风险预览改为统一顺序和明确行动文案，不触碰计算。
- Modify: `app/views/downloads.py`, `app/views/hkd_returns.py`, `app/views/alignment.py`, `app/views/daily_monthly.py`, `app/views/daily_hkd.py`, `app/views/time_eligibility.py`, `app/views/risk_free.py`, `app/views/reference_downloads.py` — 统一高级工具的页首、状态、输入／结果／证据分区。
- Modify: `tests/test_*_view.py` — 以 `workspace` 兼容切换或新 `workspace_route` 切换验证既有行为，避免依赖旧侧栏视觉结构。
- Create: `tests/test_workspace_state.py`, `tests/test_workspace_shell_view.py`, `tests/test_eligibility_hub_view.py` — 覆盖状态投影、路由、概览建议、演示隔离和新入口。
- Modify: `docs/USER_GUIDE.md`, `README.md` — 用新导航名称重新组织首次使用、已有数据快速进入和阻止状态说明。
- Create: `outputs/acceptance/UI_REDESIGN/README.md`, `outputs/acceptance/UI_REDESIGN/browser_checks.json` — 保存实际回归、浏览器宽度、跳转和下载验收证据。

### Task 1: 只读研究状态与路由合同

**Files:**
- Create: `app/views/workspace_state.py`
- Create: `tests/test_workspace_state.py`

**Interfaces:**
- Consumes: `Mapping[str, object]`，其中已有 `bundle`、`bundle_version`、`cs_result`、`ra_preview`、`dm_result`、`dh_result`、`alignment_result`、`te_result`、`rf_result`、`dl_active`、`ref_active`。
- Produces: `WorkspaceStatus` dataclass，字段为 `code: str`、`label: str`、`tone: Literal['ready','review','blocked','input']`、`detail: str`、`route: str`；`workspace_snapshot(state) -> WorkspaceSnapshot`；`next_step(snapshot) -> WorkspaceStatus`。

- [x] **Step 1: 写入会失败的状态单元测试**

```python
from app.views.workspace_state import next_step, workspace_snapshot


def test_empty_bundle_recommends_prepare_data():
    snapshot = workspace_snapshot({'bundle_version': 'empty', 'cs_result': None, 'ra_preview': None})
    assert snapshot.data.tone == 'input'
    assert next_step(snapshot).route == 'prepare_data'
    assert '尚未打开' in next_step(snapshot).detail


def test_real_n_zero_is_blocked_not_green():
    cardinality = type('Cardinality', (), {'n': 0, 'k': 30, 'status': 'pool_too_small', 'minimum_n': 100})()
    result = type('Screening', (), {'cardinality': cardinality, 'fingerprint': 'x'})()
    snapshot = workspace_snapshot({'bundle_version': 'real-v1', 'cs_result': result, 'ra_preview': None})
    assert snapshot.candidates.tone == 'blocked'
    assert snapshot.risk.tone != 'ready'
    assert next_step(snapshot).route == 'screen_candidates'
```

- [x] **Step 2: 运行测试，确认缺少模块而失败**

Run: `.venv/bin/python -m pytest tests/test_workspace_state.py -q`

Expected: collection fails with `ModuleNotFoundError: No module named 'app.views.workspace_state'`.

- [x] **Step 3: 实现最小只读状态投影**

```python
@dataclass(frozen=True)
class WorkspaceStatus:
    code: str
    label: str
    tone: Literal['ready', 'review', 'blocked', 'input']
    detail: str
    route: str


def workspace_snapshot(state: Mapping[str, object]) -> WorkspaceSnapshot:
    bundle = state.get('bundle')
    version = str(state.get('bundle_version', 'empty'))
    assets = len(getattr(bundle, 'assets', ()))
    data = WorkspaceStatus('data', '数据版本', 'ready', f'{version} · 产品 {assets}', 'prepare_data') if assets else WorkspaceStatus('data', '数据版本', 'input', '尚未打开数据版本', 'prepare_data')
    return WorkspaceSnapshot(data=data, candidates=_candidate_status(state), target=_target_status(state), risk=_risk_status(state))
```

Implement `_candidate_status` only from `cs_result.cardinality`: `passed` becomes `ready`; `pool_too_small` becomes `blocked` and includes N、最低 N、缺口；all missing or other statuses become `input`／`review`, never `ready`. Implement `_risk_status` as `ready` only when both `ra_preview` and `ra_result_token` are present. Do not assign to `state` or import any calculator.

- [x] **Step 4: 运行状态测试与现有风险失效测试**

Run: `.venv/bin/python -m pytest tests/test_workspace_state.py tests/test_risk_workspace_helpers.py -q`

Expected: PASS; no test performs network access.

- [x] **Step 5: 记录验证结果**

Run: `.venv/bin/python -m pytest tests/test_workspace_state.py -q > /tmp/workspace-state-tests.txt && tail -n 2 /tmp/workspace-state-tests.txt`

Expected: one concise PASS summary; attach this result to the task review notes.

### Task 2: 壳层、分组导航和研究总览

**Files:**
- Create: `app/views/page_chrome.py`
- Create: `app/views/workspace_shell.py`
- Modify: `app/main.py`
- Create: `tests/test_workspace_shell_view.py`
- Modify: `tests/test_candidate_screening_view.py:9-18`, `tests/test_alignment_view.py:9-15`, `tests/test_hkd_returns_view.py:9-15`, `tests/test_risk_free_view.py:9-15`, `tests/test_time_eligibility_view.py:8-15`

**Interfaces:**
- Consumes: `WorkspaceSnapshot`, `WorkspaceStatus`, routes `overview`, `prepare_data`, `eligibility`, `screen_candidates`, `risk_preview`, `downloads`, `returns_window`, `history_sources`, `rates_factors`.
- Produces: `render_navigation(snapshot) -> str`, `render_overview(snapshot) -> None`, `page_header(stage, title, purpose, status) -> None`, `navigate(route) -> None`.

- [x] **Step 1: 写入总览和路由失败测试**

```python
def test_home_is_default_and_has_clear_first_action(tmp_path, monkeypatch):
    at = start(tmp_path, monkeypatch)
    assert at.session_state['workspace_route'] == 'overview'
    assert any('准备数据' in button.label for button in at.button)
    assert any('尚未打开数据版本' in info.value for info in at.info)


def test_navigation_keeps_legacy_workspace_handoff(tmp_path, monkeypatch):
    at = start(tmp_path, monkeypatch)
    at.selectbox(key='workspace_route').set_value('downloads').run()
    assert at.session_state['workspace'] == '下载与缓存'
    assert any('下载与缓存' in title.value for title in at.title)
```

- [x] **Step 2: 运行测试，确认新路由控件和总览尚不存在**

Run: `.venv/bin/python -m pytest tests/test_workspace_shell_view.py -q`

Expected: FAIL because `workspace_route` and `render_overview` do not exist.

- [x] **Step 3: 建立页面骨架、路由表和兼容同步**

```python
ROUTES = {
    'overview': Route('研究总览', 'overview', '研究总览', '查看当前研究状态与下一步'),
    'prepare_data': Route('完成研究', 'prepare_data', '01 准备数据', '导入、打开并核对数据版本', legacy='数据导入'),
    'eligibility': Route('完成研究', 'eligibility', '02 核对资格', '核对频率、港币换算、共同窗口和时间证据'),
    'screen_candidates': Route('完成研究', 'screen_candidates', '03 筛选候选', '检查范围、资格与 K/N', legacy='候选筛选'),
    'risk_preview': Route('完成研究', 'risk_preview', '04 收益与风险', '查看收益、相关性和权重风险', legacy='候选筛选'),
}

def navigate(route: str) -> None:
    st.session_state['workspace_route'] = route
    legacy = ROUTES[route].legacy
    if legacy:
        st.session_state['workspace'] = legacy
```

In `app/main.py`, initialise `workspace_route` to `overview`; if a legacy handler changes `workspace`, map it back to its canonical route on the next rerun. Render one grouped `st.sidebar.selectbox(..., key='workspace_route')` whose labels include the required stage group names, plus compact group captions. Do not render the old flat `st.sidebar.radio`. Preserve every legacy string in a reverse map so `_handoff()` in `downloads.py` still returns to `prepare_data`.

`page_chrome.py` must define `page_header` and `section_heading`. It emits a semantic status band using `st.success`, `st.warning`, `st.error`, or `st.info` according to `WorkspaceStatus.tone`, then exactly one concise purpose sentence. `workspace_shell.py` inserts the CSS variables and renders the overview cards from the snapshot; card buttons call `navigate`, and the SYNTH demonstration button only sets `workspace_route='screen_candidates'` and `cs_source='SYNTH 相关性与风险演示'`.

- [x] **Step 4: 适配旧页面测试的导航帮助函数**

```python
def go(at, route):
    at.selectbox(key='workspace_route').set_value(route).run()
    assert not at.exception
    return at


def start(tmp_path, monkeypatch):
    # existing environment setup
    at = AppTest.from_file(str(ROOT / 'app/main.py'), default_timeout=30).run()
    return go(at, 'screen_candidates')
```

Replace only assertions that require `at.radio(key='workspace')`; retain all assertions about calculations, invalidation, downloaded bytes and no-network behavior.

- [x] **Step 5: 运行壳层、筛选和下载回归**

Run: `.venv/bin/python -m pytest tests/test_workspace_shell_view.py tests/test_candidate_screening_view.py tests/test_downloads_view.py -q`

Expected: PASS; the default page is the overview, and the existing download-to-import callback opens the preparation page.

- [x] **Step 6: 做人工窄屏检查**

Run: `.venv/bin/python -m streamlit run app/main.py --server.address 127.0.0.1 --server.port 8502 --server.headless true --browser.gatherUsageStats false`

Expected: the overview at 1440, 720 and 390 px has no overlapped heading, clipped primary button or page-level horizontal scroll. Save screenshots in `outputs/acceptance/UI_REDESIGN/` after Task 5 creates that directory.

### Task 3: 主研究流程和资格中心

**Files:**
- Create: `app/views/eligibility_hub.py`
- Modify: `app/views/data_center.py`
- Modify: `app/views/candidate_screening.py`
- Modify: `app/views/risk_analysis.py`
- Modify: `app/views/screening_display.py`
- Modify: `app/main.py`
- Create: `tests/test_eligibility_hub_view.py`
- Modify: `tests/test_data_center.py`, `tests/test_candidate_screening_view.py`, `tests/test_risk_workspace_view.py`

**Interfaces:**
- Consumes: `page_header`, `section_heading`, `navigate`, `workspace_snapshot` and current result keys without changing their values.
- Produces: `render_eligibility_hub() -> None`; route rendering functions for `prepare_data`, `eligibility`, `screen_candidates`, `risk_preview`.

- [x] **Step 1: 写入资格中心和风险入口失败测试**

```python
def test_eligibility_hub_links_to_existing_checks(tmp_path, monkeypatch):
    at = start(tmp_path, monkeypatch, 'eligibility')
    labels = [button.label for button in at.button]
    assert '核对日线月度' in labels
    assert '核对港币收益' in labels
    assert '核对共同窗口' in labels
    assert '核对历史资格' in labels


def test_risk_route_keeps_existing_result_and_calculation(tmp_path, monkeypatch):
    at = prepare_passed_screening(tmp_path, monkeypatch)
    at.selectbox(key='workspace_route').set_value('risk_preview').run()
    assert at.button(key='ra_compute').label == '计算收益与风险'
```

- [x] **Step 2: 运行测试，确认资格中心和风险单独路由不存在**

Run: `.venv/bin/python -m pytest tests/test_eligibility_hub_view.py -q`

Expected: FAIL because route `eligibility` has no rendering function.

- [x] **Step 3: 以展示层最小改动实现主流程**

```python
def render_eligibility_hub():
    snapshot = workspace_snapshot(st.session_state)
    page_header('02', '核对资格', '按需要核对频率、港币换算、共同窗口和版本时间；这些核对不会自动认证候选池。', snapshot.candidates)
    for label, route, detail in CHECKS:
        st.button(label, key=f'eligibility_{route}', on_click=navigate, args=(route,))
        st.caption(detail)
```

Add a `route` argument or `render_mode` keyword to `candidate_screening.render`: default `screen_candidates` renders existing source/scope/results flow; `risk_preview` shows the same candidate screening inputs and result summary followed by `render_risk`, so no calculation state is duplicated. Replace current visual title/captions with `page_header`; preserve every existing widget key, button key and invalidation check. In `data_center.render`, replace only the local CSS/title/info block with `page_header('01', '准备数据', ...)` and section headings `选择文件与原始记录`, `字段映射与口径`, `核对并保存`, `已保存数据`.

For `screening_display.py`, place `section_heading('筛选结果与下一步')` before cardinality. Its existing risk rendering call must be moved behind the `risk_preview` route condition; exported bytes, tables and evidence stay identical. No status is marked ready solely because a SYNTH case is selected.

- [x] **Step 4: 运行主流程与失效回归**

Run: `.venv/bin/python -m pytest tests/test_data_center.py tests/test_candidate_screening_view.py tests/test_risk_workspace_view.py tests/test_eligibility_hub_view.py -q`

Expected: PASS; a source, scope, K or weight change still clears `cs_result`／`ra_preview` exactly as before.

- [x] **Step 5: 在浏览器验证第一次研究流程**

Run: `.venv/bin/python -m pytest tests/test_workspace_state.py tests/test_workspace_shell_view.py tests/test_eligibility_hub_view.py -q`

Expected: PASS. In the browser, record overview → prepare data → eligibility → screening → risk preview and verify that an unprepared real version shows N=0／blocked rather than a successful portfolio.

### Task 4: 高级工具统一页面骨架和回跳

**Files:**
- Modify: `app/views/downloads.py`
- Modify: `app/views/hkd_returns.py`
- Modify: `app/views/alignment.py`
- Modify: `app/views/daily_monthly.py`
- Modify: `app/views/daily_hkd.py`
- Modify: `app/views/time_eligibility.py`
- Modify: `app/views/risk_free.py`
- Modify: `app/views/reference_downloads.py`
- Modify: `app/main.py`
- Modify: `tests/test_downloads_view.py`, `tests/test_hkd_returns_view.py`, `tests/test_alignment_view.py`, `tests/test_daily_monthly_view.py`, `tests/test_daily_hkd_view.py`, `tests/test_time_eligibility_view.py`, `tests/test_risk_free_view.py`, `tests/test_reference_downloads_view.py`

**Interfaces:**
- Consumes: `page_header`, `section_heading`, `navigate`; every tool keeps its existing module-level `render()` function and data keys.
- Produces: advanced routes that render the existing tools without a second page implementation.

- [x] **Step 1: 写入高级工具路由失败测试**

```python
@pytest.mark.parametrize('route, title', [
    ('downloads', '市场数据与缓存'),
    ('returns_window', '收益与窗口核对'),
    ('history_sources', '历史资格与来源'),
    ('rates_factors', '利率与因子'),
])
def test_advanced_route_has_group_heading(tmp_path, monkeypatch, route, title):
    at = start(tmp_path, monkeypatch)
    at.selectbox(key='workspace_route').set_value(route).run()
    assert any(title in heading.value for heading in at.subheader + at.title)
```

- [x] **Step 2: 运行测试，确认高级组路由尚未完整映射**

Run: `.venv/bin/python -m pytest tests/test_workspace_shell_view.py::test_advanced_route_has_group_heading -q`

Expected: FAIL for at least one unimplemented route.

- [x] **Step 3: 以页首和分区迁移每个高级工具**

```python
def render_tool(stage, title, purpose, status, body):
    page_header(stage, title, purpose, status)
    body()


def render_downloads_route():
    render_tool('数据工具与证据', '市场数据与缓存', '生成下载计划、打开本地缓存并保留原始来源证据。', downloads_status(), downloads.render)
```

Use route aliases to reach the underlying pages: `downloads` → `downloads.render`; `returns_window` defaults to `hkd_returns.render` and includes buttons to daily/monthly/alignment/daily-HKD; `history_sources` → `time_eligibility.render`; `rates_factors` defaults to `risk_free.render` and links to `reference_downloads.render`. Do not merge the tools, copy their state, or replace their buttons.

For every underlying view, replace only title/caption blocks and section heading strings with `page_header`/`section_heading`. Preserve widget keys (`dl_*`, `hkd_*`, `alignment_*`, `dm_*`, `dh_*`, `te_*`, `rf_*`, `ref_*`) and existing error messages. In `downloads._handoff`, set both `workspace='数据导入'` and `workspace_route='prepare_data'`.

- [x] **Step 4: 运行所有高级工具 AppTest**

Run: `.venv/bin/python -m pytest tests/test_downloads_view.py tests/test_hkd_returns_view.py tests/test_alignment_view.py tests/test_daily_monthly_view.py tests/test_daily_hkd_view.py tests/test_time_eligibility_view.py tests/test_risk_free_view.py tests/test_reference_downloads_view.py -q`

Expected: PASS; every tool remains offline until its existing explicit download button is clicked, and all existing exports remain available.

- [x] **Step 5: 手动检查跨页回跳**

Run: `.venv/bin/python -m pytest tests/test_downloads_view.py::test_offline_open_corrupt_handoff_and_fx -q`

Expected: PASS; after “送入数据导入核对”, the rendered page is `01 准备数据` and imported bytes have not been committed automatically.

### Task 5: 使用指南、视觉验收与完整回归

**Files:**
- Modify: `docs/USER_GUIDE.md`
- Modify: `README.md`
- Create: `outputs/acceptance/UI_REDESIGN/README.md`
- Create: `outputs/acceptance/UI_REDESIGN/browser_checks.json`
- Modify: `tests/test_workspace_shell_view.py`

**Interfaces:**
- Consumes: final routes, actual screenshots and pytest output.
- Produces: user-facing operating guide and reproducible acceptance record.

- [x] **Step 1: 写入失败的导航文案验收测试**

```python
def test_overview_explains_blocked_next_step(tmp_path, monkeypatch):
    at = start_with_real_daily_bundle(tmp_path, monkeypatch)
    assert any('需要月度准备' in message.value for message in at.error + at.warning + at.info)
    assert any('核对资格' in button.label for button in at.button)
```

- [x] **Step 2: 运行测试并确认文案在实现前失败**

Run: `.venv/bin/python -m pytest tests/test_workspace_shell_view.py::test_overview_explains_blocked_next_step -q`

Expected: FAIL if the overview does not expose the exact blocker and route.

- [x] **Step 3: 更新指南和验收记录**

```markdown
## 从研究总览开始

1. 打开「研究总览」，阅读“现在建议”的按钮和阻止原因。
2. 新资料进入「01 准备数据」；只想复查已有资料可由「数据工具与证据」直接进入对应工具。
3. 筛选通过 K/N 后，在「04 收益与风险」查看预览。该页仍不是最终成员选择或投资建议。
```

Update `README.md` links from the old flat sidebar instructions to the four stage names. In `outputs/acceptance/UI_REDESIGN/README.md`, record route mapping, exact test command/output, actual browser date, viewport screenshots, tested SYNTH path, tested N=0 path, downloads path, and any known limitations. Store machine-readable checks such as `{"width":390,"route":"overview","page_overflow":false,"text_overlap":false}` in `browser_checks.json`.

- [x] **Step 4: 运行完整自动回归**

Run: `.venv/bin/python -m pytest -q`

Expected: all tests pass. Preserve the full terminal summary in `outputs/acceptance/UI_REDESIGN/full_test_checks.txt`; record only real warnings and their source.

- [x] **Step 5: 完成三种宽度和实际下载浏览器验收**

Run: start Streamlit on port 8502, then inspect 1440, 720 and 390 px for overview, prepare data, eligibility, screening/risk and one advanced tool.

Expected: no text overlap or page-level horizontal overflow; table scroll remains inside its container; a generated existing export downloads with its original file name and nonempty bytes. Save only actual screenshots and outcomes in `outputs/acceptance/UI_REDESIGN/`.

- [x] **Step 6: 完成最终针对性回归**

Run: `.venv/bin/python -m pytest tests/test_workspace_state.py tests/test_workspace_shell_view.py tests/test_eligibility_hub_view.py tests/test_candidate_screening_view.py tests/test_risk_workspace_view.py -q`

Expected: PASS, confirming status projection, routing, invalidation and risk preview after the full visual migration.


## 连续执行记录（2026-10-17）

五项任务已完成。完整回归 736 项通过；最终针对性回归 45 项通过；独立只读复审未发现剩余重要问题。浏览器实测与终端结果归档于 `outputs/acceptance/UI_REDESIGN/`。目录无 Git，按授权在原工作目录保留改动。

实施细化：

- 侧栏使用可折叠阶段按钮组及始终可见的快速跳转框，确保任意工具两次点击可达；所有旧工具共用原渲染函数。
- 普通控件使用锁定 Streamlit 版本的 `persist_state='session'`；候选证据、风险权重及四类工具上传保留会话副本，并保持来源／候选 epoch 约束与显式清除。
- 页面状态用占位区在本轮操作处理完后读取，避免计算／清除后的状态慢一轮更新。
- 针对性验证按任务合同合并执行，结果统一归档，替代分散的临时 `/tmp` 文本；最终新增实际原生上传、往返、清除及真实 N=0 浏览器检查。
- 旧 8502 服务加载了缓存模块，确认进程属于本项目后重启；另以 8504 只读打开 S02 已存版本完成真实资料验收，不修改默认导入目录。
- 没有修改 `src/portfolio/` 中的数值实现、合同与模型，也没有发起外部数据下载。
