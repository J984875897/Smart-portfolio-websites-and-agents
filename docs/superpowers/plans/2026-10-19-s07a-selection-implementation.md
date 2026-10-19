# S07-A 成员选择核心实施计划

> **For agentic workers:** 使用 executing-plans 在本轮顺序实施并记录验收；不同时推进 B 或 C。复选框用于恢复进度。

**Goal:** 在原 S05／S06 输入上生成可追溯、可重复的 K 项多头选择草稿。

**Architecture:** 分组、排序资料校验、选择和理由分别独立；连接层重新筛选并只使用训练窗口，界面以后接入已验收核心。

**Tech Stack:** 已安装 Python、NumPy、pandas、pytest；不新增依赖、不下载市场数据。目录不是 Git 仓库，原地新增文件，不创建仓库或提交。

## Global Constraints

- 以 `../specs/2026-10-19-s07-member-selection-design.md` 的冻结规则 v1 为准。
- S07-A 不产生权重、utility、正式组合或 UI 新入口；后续 UI 必须复用统一框架。
- 保留完整 60 月、HKD、20≤K≤100、K/N≤30% 和历史未认证边界。
- 排序、并列合并和指纹按稳定 ID；未知相关性／费用／流动性不补值或伪装最好。

### Task 1：确定性 complete-linkage 分组

Files: 新建 `src/portfolio/universe/clustering.py`、`tests/test_clustering.py`。

Interface: `cluster_correlations(matrix, *, rho_threshold=0.85) -> ClusterResult`，包含 memberships、merges、diagnostics、fingerprint。

- [x] 先写链式三资产、负相关、等号、常数、重排与错误矩阵测试；运行 `.venv/bin/python -m pytest tests/test_clustering.py -q` 确认缺失功能失败。
- [x] 使用最大簇间距离和明确 ID 并列顺序；记录合并距离，未知行／列独立标记且不计作已知覆盖。
- [x] 同命令通过，再与 S06 相关性核心回归。

### Task 2：排序资料与 K 项选择

Files: 新建 `src/portfolio/universe/selection_ranking.py`、`selection.py`、`reasons.py`、`tests/test_selection.py`。

Interfaces: `select_members(candidate, *, k, included_asset_ids=(), member_excluded_asset_ids=(), category_minimums=None, ranking_data=None, rho_threshold=0.85, **screening_options) -> SelectionResult`；可选排序资料见设计字段。

- [x] 先写 N100/K30、类别最低数、手动项、N99、成员排除不足、未来资料、缺值与并列、全同向及常数、重排和输入不修改测试；运行 `.venv/bin/python -m pytest tests/test_selection.py -q` 确认失败。
- [x] 重新运行 `screen_candidates`，拒绝不通过的数量门槛；复用 `pearson_correlation`，按设计的三个选择阶段产生逐项记录。
- [x] 校验排序资料的数值、ID、来源、时区与重复时间，只取 decision_utc 之前最新值；完整绑定证据和草稿状态。
- [x] 生成全部候选逐项理由、非承诺式候补对照、已选相关子矩阵和高相关配对；全部记录保留未知值。
- [x] 运行两组新增测试及既有 S05／S06 受影响回归。

### Task 3：离线材料、审查与文档

Files: 新建 `scripts/verify_selection.py`、`tests/test_selection_verification.py`、`outputs/acceptance/S07A/`；更新 README、USER_GUIDE、PROJECT_PLAN 和总开发流程。

- [x] 验收脚本先写测试，核对 selection_reasons.csv、candidate_alternatives.csv、selected_correlation.csv、high_correlation_pairs.csv、summary.json 及阻止案例，确保 JSON 无非有限值、源数据不变和输出别名拒绝。
- [x] 生成 SYNTH 选择证据及链式／负相关手算，真实日线保持 N0 阻止；不写任何真实持仓建议。
- [x] 进行独立只读审查，修复重要问题；运行 `.venv/bin/python -m pytest -q` 和验收命令，保存实际结果。
- [x] 标记 A 的实际状态，保留 B／C 未开始；给出可直接检查的文件，说明当前 UI 尚无选择入口。

执行记录（2026-10-19）：全部 A 任务完成。新增 58 项；完整回归 794 passed、2 条原有日历依赖弃用提示，273.20 秒；S05／S06 受影响基线 82 项通过。初审发现一次性筛选迭代器耗尽及标准 CSV／XLSX 排序表解析两项 Important，已先补失败回归、再修复并独立复审关闭。验收脚本退出码 0，真实源文件哈希未变，真实 N0 继续阻止。已重装本地包，4 个新核心文件与已安装包逐字节一致，pip check 无破损依赖。未修改 app/ 页面；B／C 未开始。
