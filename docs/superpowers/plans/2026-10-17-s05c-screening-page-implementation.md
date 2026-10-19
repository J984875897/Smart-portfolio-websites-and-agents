# S05-C 候选筛选页面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans 按本计划逐项实现与查验。

**Goal:** 用户可在工作台核对数据、选择投资范围，解释合格 N 和 K/N，并导出与当前输入一致的结果。

**Architecture:** 页面直接将原始 DataBundle、FX、时间及结构输入交给 A，再调用 B；不复用任意缓存资格标志。输入令牌与参数绑定，改变后先撤下旧结果和下载，明确点击后重算；搜索、分页仅控制展示。

**Tech Stack:** 现有 Python 3.14、pandas、Streamlit 1.65、pytest AppTest、Chrome CDP；无新增依赖。

## Global Constraints

- 已批准 S05 设计，A/B 核心已验收；本单元只交付 C 页面，不实现估计、相关性、utility、权重、做空或联网。
- HKD、固定60月、current_universe_retrospective、timing_basis=importer_declared、historical_universe_certified=false。
- K20–100整数、K/N≤30%；人工100项不是实际选品，数量通过不代表风险合格。
- 默认剔除直接个股、保留股票ETF／基金；未知结构不放行；保留所有排除原因。
- 本项目无Git仓库，原地修改，不创建仓库／分支。

## 页面与视觉

保留研究工作台的白底与深蓝标题；原生控件保护字体图标，禁止全局重写widget字体。色彩跟随现有主题：文字#18334C、强调#0F7490、边界#D7DFE5、底色#FFFFFF、提示#EAF2FF。显示文字使用系统中文字体，数据与公式使用原生等宽代码。独特元素是可核对的数量判定 `K / N ≤ 30%`，紧邻最低N和缺口，避免让用户以为看见已生成组合。窄屏保持纵向流程，表格允许自身横向滚动。

```text
候选筛选：先看清可选范围
来源／研究模式 → 结束月与决策时间 → 补充证据（折叠说明）
市场、工具、经济类别、个股开关、手动排除 → 目标K → 查验并筛选
数量通过／阻止 + K/N、最低N、缺口
资料行数 → 身份合格 → 范围内 → 数据合格N
产品表：搜索／状态／分页（只改变展示） → 结果CSV／矩阵／证据JSON
```

## Task 1：可复用人工来源及页面输入

Files: `src/portfolio/universe/screening_samples.py`、`scripts/verify_candidate_screening.py`、`app/views/candidate_screening.py`、`app/main.py`、`tests/test_candidate_screening_view.py`。

接口 `sample_screening_inputs()` 返回原始 `(bundle,fx,timing,structures)`；从人工完整月度来源构造100独立SYNTH ID，供CLI与页面共用。CLI仍经A重新查验。页面 `render()` 消费当前 session bundle 或人工原始输入，不读取已导出的合格矩阵。

- [x] 先写测试：入口存在，初始无结果；人工100项筛选N100、K30通过；手动排除末项N99且旧结果立即消失，重算阻止。
- [x] `.venv/bin/python -m pytest tests/test_candidate_screening_view.py -q` 观察入口缺失失败。
- [x] 实现三种来源：SYNTH100项、SYNTH缺月／时间、当前已打开导入版本。当前版本默认空FX、时间、结构，上传CSV／XLSX、可选工作表；不把人工证据自动附给真实来源。模板下载不算结果导出。
- [x] 添加原币复权确认、固定窗口参数、范围与K控件、令牌失效及A→B调用，运行测试通过。

## Task 2：结果解释、导出及失败路径

Files: `app/views/candidate_screening.py`、`app/views/screening_display.py`、`tests/test_candidate_screening_view.py`。

接口 `render_result(result)` 绘制数量门槛、漏斗、产品表；`result_downloads(result)` 输出 audit CSV、合格HKD矩阵CSV、证据JSON。JSON包括fingerprint、counts、cardinality与完整研究标签，缺失费率／流动性标“未提供”，后续统计标“待后续估计”。

- [x] 失败测试覆盖个股开关、市场／类别／手动排除、时间变化与源表内容变化使旧下载撤下；搜索／分页／展示状态不改变N。
- [x] 失败测试覆盖CSV实际内容、JSON标签、空池、非法月份／无时区、缺结构和损坏上传、XLSX换表。
- [x] 实现清晰中文原因及英文代码，原始资产ID保留；输入错误指明修复方向。任何重算异常清空旧结果。
- [x] `.venv/bin/python -m pytest tests/test_candidate_screening_view.py -q` 全部通过，重跑B定向检查。

## Task 3：浏览器查验、独立复核与说明

Files: `scripts/verify_candidate_screening_browser.mjs`、`outputs/acceptance/S05C/README.md`、本步checks及截图；README、用户指南、PROJECT_PLAN、S05设计／总流程。

- [x] 浏览器实操100→99切换，核对下载CSV；1440、720、390宽度截图及页面无异常／横向溢出检查，查看实际截图确认无重叠。
- [x] 请求只读独立复核，重要问题先补失败测试再修复。
- [x] `.venv/bin/python -m pytest -q` 保存完整结果；重新安装本地包并验证源码一致，源版本文件前后散列不变。
- [x] 更新用户操作说明和本步验收材料；标记本步完成，下一步S06单独开展。
