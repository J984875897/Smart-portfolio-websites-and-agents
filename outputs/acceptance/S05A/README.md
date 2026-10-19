# S05-A 月度数据输入接入验收

日期：2026-10-17。状态：**本单元开发验收通过**；S05-B/C 尚未实现。按用户调整后的顺序，A 是数据接入，B 才是分类筛选与数量规则。

依据：[已确认设计](../../../docs/superpowers/specs/2026-10-17-s05-candidate-screening-design.md)、[实施计划](../../../docs/superpowers/plans/2026-10-17-s05a-candidate-input-implementation.md)。本步没有新增工作台页面，原有页面操作不变。

## 先查看这些结果

| 文件 | 预期与实际 |
| --- | --- |
| [人工数据资格报告](synthetic/data_eligibility.csv) | HKD_COMPLETE／USD_COMPLETE 各 60 月通过；其余三项各缺 1 月，分别为缺月、仅 59 月、缺期末 FX |
| [人工 HKD 矩阵](synthetic/hkd_matrix.csv) | 60 行×2 列，2020-02 至 2025-01，每个值 0.01（1%），是合成计算案例 |
| [人工结构资料](synthetic/structures.csv) | 独立绑定结构与来源；declared 仅为输入者声明，未做产品允许规则 |
| [人工来源证据](synthetic/input_evidence.json) | 输入指纹、各表及原始字节散列、参数、HKD、60 月、声明时间与历史认证 false |
| [真实数据资格报告](real_daily_input/data_eligibility.csv) | 3 个真实产品全部阻止；monthly_preparation_required、ambiguous_return、missing_timing |
| [真实来源证据](real_daily_input/input_evidence.json) | 继承并绑定 S02 保存版本及原始文件散列，历史认证仍 false |
| [机器汇总](summary.json) | 人工矩阵 60×2、真实日线矩阵 60×0，源文件未变，不计算正式 N、不生成组合 |

每组另有 assets.csv、coverage.csv、reconciliation.csv，供逐月追溯。矩阵只有数据合格列；数据合格不表示已经通过市场、个股模式或结构筛选。

## 实际实现

`prepare_candidate_input(bundle, fx, timing, structures=None, *, end_month, decision_at, adjusted_price_assets=())` 从原始输入重新调用已有 reconcile_hkd 和 align_monthly，固定 60 月，返回 CandidateInput。既有结果表或任意“合格=true”布尔值均不能作为其输入替代证据。

输出包含身份资料、HKD 矩阵、逐资产／逐月报告、结构资料、换算对照、来源证据和指纹。未知资产、同 ID 冲突、不同 ID 指向同一上市身份、非规范空格等不进入矩阵。完全相同身份资料可折叠；结构资料缺失标 missing，不伪造核验，也不在 A 提前执行产品类型筛选。

`candidate_input_is_current(...)` 检查当前输入是否与旧结果绑定一致。修改资产、观察值、FX、时间、结构资料、导入配置、来源文件／工作表、窗口参数或复权确认会失效；旧结果保留自己的独立数据副本。文件来源重新解析并核对表值／索引；物理行号由文件生成，内存 attrs 中的行号不作为证据。

## 真实样本边界

读取 S02 的 `s01-prices-b8912ef9e8e943e0bd6b8cf22e4f3b32` 保存版本，共 3 个产品、8,305 条原币日线。原始版本及其文件散列在加载时校验，运行前后再次比较全部文件，未被修改。

它不是月度收益输入，因此本次预期为阻止，而不是 60 个月真实成功。日线月度转换仍在 C1/C2 的独立路径；C2/C3 → 共同窗口的桥接没有在本步实现。没有伪造真实时间证据、降低窗口长度或解除 FX partial 阻止。下一步 B 可基于合格的 A 输入验证规则，仍不能将这个真实日线版本算进 N。

## 测试与复核

- 基线 474 项通过；新增 40 项检查后全套 **514 passed，2 warnings，39.32 秒**，见 [全套原始输出](full_test_checks.txt)。两条仍是原有 exchange_calendars 的 NumPy timedelta 弃用提示。
- TDD：首先观察新模块缺失导致 25 项失败，再实现通过；后续新增文件损坏、来源行号、身份空格、日线频率和非有限数值复现后逐项修正。验收脚本也先观察不存在失败，再实现。
- 独立只读复核发现 3 项 Important、1 项 Minor：未经验证的来源行号、身份空格、非有限 FX 证据的严格 JSON、损坏 XLSX。均已修复；补充复查又发现 Infinity 与 NaN 的差别，已覆盖 NaN／正负 Infinity。最终复测 4 项通过，复核范围内无尚存 Critical／Important。
- 重新安装本地包，无新依赖；核对 `.venv` 的 site-packages 中四个实现文件与源码逐字节一致。
- 本轮不联网、不新增界面，因此没有声称新的浏览器视觉验收。验收脚本与测试入口见 [checks.txt](checks.txt)。

下一步为 **S05-B：分类、个股开关、去重及 K／N 数量校验**，完成后单独查验。
