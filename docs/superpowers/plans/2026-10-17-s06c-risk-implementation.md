# S06-C 风险界面实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement task-by-task.

**Goal:** 候选筛选通过后，能查验收益、相关性、指定多头权重风险及对应导出。

**Architecture:** 候选页面保留 CandidateInput 和筛选参数；risk_analysis 管理权重与状态，risk_display 管理表图，risk_exports 提供无界面解析与导出。全部数值复用 preview_candidate_risk。

**Tech Stack:** 现有 Python、pandas、NumPy、Streamlit、Altair；无新增依赖。当前目录非 Git 仓库，不初始化或执行提交。

## Global Constraints

固定60月、HKD、K20–100且K/N≤30%；真实N0不绕过。无做空／选品／优化；等权N项不是选出K项。常数相关性不可用、零波动DR不可用；JSON null。输入变化移除旧结果与下载，展示变化不改变研究结果。

### Task 1: 样本、权重与导出

Files: `src/portfolio/universe/risk_samples.py`, `app/views/risk_exports.py`, `tests/test_risk_workspace_helpers.py`.

Interfaces: `sample_risk_inputs()` 返回四张来源表；`parse_weights(payload, asset_ids)` 返回 ID 对齐 Series；`preview_exports(preview)` 返回文件名→bytes。

- [x] 写测试：固定种子案例60×100且常数／正反相关；拒绝缺失／多余／重复ID、布尔、负、无穷、总和不一；有效输入按ID对齐；导出strict JSON null和全部矩阵。
- [x] `.venv/bin/python -m pytest tests/test_risk_workspace_helpers.py -q` 确认功能缺失失败。
- [x] 实现上述接口：CSV只接受asset_id/weight，数值校验沿用核心容差，不归一化；导出包含证据、诊断、风险数值和原始小数。
- [x] 重跑该测试通过。

### Task 2: 页面接入与失效

Files: `app/views/candidate_screening.py`, `app/views/risk_analysis.py`, `tests/test_risk_workspace_view.py`.

Interfaces: `render_risk(candidate, options, screening, token)`；state键统一`ra_`。

- [x] 写AppTest：筛选通过才能预览、N99/N0阻止、默认等权、上传权重非法报错、输入与权重变化清空、展示控件不改变指纹、导出内容与当前结果一致。
- [x] 运行新页面测试确认缺失失败。
- [x] 来源列表追加人工风险案例（保留原三项位置）；筛选时保留candidate；风险入口重新执行资格；绑定输入及权重token，失败清空旧结果。
- [x] 重跑新页面测试和原candidate_screening_view回归。

### Task 3: 图表与解释

Files: `app/views/risk_display.py`, `app/views/risk_analysis.py`.

- [x] 四页签：收益摘要、Pearson图及唯一产品对、双协方差对照和有正负轴风险贡献图、诊断与导出。新增测试验证常数不可用和两种口径分开。
- [x] 用已安装Altair绘制固定[-1,1]色标图；展示子集2–30默认20，不改变N或风险；权重数和K同时显示。
- [x] 验证零波动null、负贡献保留、小数导出与百分数展示、模型常数方差提示。

### Task 4: 验收与使用说明

Files: `scripts/verify_risk_workspace_browser.mjs`, `outputs/acceptance/S06C/`, `README.md`, `docs/USER_GUIDE.md`, `PROJECT_PLAN.md`.

- [x] 安装同步本地包（无依赖更新）；完整pytest写入验收文件。
- [x] 真实浏览器点击／下载并检查1440、720、390宽截图与无页面横向溢出，核验源版本哈希不变。
- [x] 独立只读审查；修正重要问题并运行相应回归。
- [x] 更新设计状态、使用步骤、验收记录、主计划；仅实际完成后勾选。

## 执行结果

- 2026-10-17：新增27项测试；完整回归713 passed、2条原有日历依赖弃用警告，210.90秒。基线686项。
- 独立审查新两组27 passed，Critical/Important/未关闭Minor均0。CSV错列和具体提示两项先复现失败后修复。
- 浏览器12项宽窄屏页签检查、真实下载、实际上传自定义权重（2项同向DR=1）、错误上传清空均通过；截图已视觉核对。
- 源版本13个文件哈希不变；依赖检查通过；未增加依赖、未联网下载研究资料。新版实例8502，旧8501保留。
- 验收入口：`outputs/acceptance/S06C/README.md`。下一步S07成员选择需单独设计与授权，本步不启动。
