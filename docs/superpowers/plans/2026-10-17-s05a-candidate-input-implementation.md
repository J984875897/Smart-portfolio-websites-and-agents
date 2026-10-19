# S05-A 月度候选输入接入实施计划

> 使用 executing-plans 顺序执行，每个交付先验证。用户已授权开始 A；只实现本计划，不进入 S05-B/C。当前目录没有 Git 仓库，在原工作区新增模块，不创建仓库或分支。

**Goal:** 从 DataBundle、FX、声明时间及独立结构资料重新计算可追溯的固定 60 月 HKD 输入。

**Architecture:** 数据适配层重新调用 reconcile_hkd 和 align_monthly，不接收已缓存矩阵或资格布尔值。CandidateInput 是带输入指纹的独立结果快照；结构资料与金融资格分开。

**Tech Stack:** 现有 Python 3.14、pandas、pytest；无新依赖。

## 固定约束

仅当前资产池回溯研究，时间为输入者声明，历史候选池认证 false。不联网，不改变原始数据，不接收 K，不计算 N，不增加页面。固定 60 月；身份冲突及孤立收益不得进入矩阵。

## Task 1：输入绑定、结构资料与失败测试

文件：新增 `src/portfolio/universe/input_evidence.py`、`structures.py`、`__init__.py`；测试 `tests/test_candidate_inputs.py`。

- [x] 写失败测试：文件来源的 FX／时间／结构表必须与原始 read_file 结果一致；重复列和结构资料重复冲突报错；缺结构资料保留 missing；原始字节／文件名／工作表变化改变指纹。
- [x] 运行 `.venv/bin/python -m pytest tests/test_candidate_inputs.py -q`，确认模块未实现的预期失败。
- [x] 实现 `verified_frame(frame, name)` 重读文件来源，验证值和索引，恢复物理行来源；`frame_evidence(frame)` 记录表内容及原始字节散列；`bind_structures(frame, asset_ids)` 输出每个资产绑定后的结构资料。字段为 asset_id、market、canonical_tool_type、structure、review_status、source_name、source_reference、source_as_of。
- [x] 重跑本文件测试；结构 reviewed 只代表声明状态，不代表软件历史认证；不在此模块决定产品是否允许。

## Task 2：CandidateInput 与完整窗口

文件：新增 `src/portfolio/universe/inputs.py`；扩展同一测试文件。

接口：

```python
prepare_candidate_input(bundle, fx, timing, structures=None, *, end_month,
                        decision_at, adjusted_price_assets=()) -> CandidateInput
candidate_input_is_current(result, bundle, fx, timing, structures=None, *,
                           end_month, decision_at, adjusted_price_assets=()) -> bool
```

CandidateInput 字段：assets、matrix、data_eligibility、coverage、structures、reconciliation、evidence、input_fingerprint。返回表均独立于输入。

- [x] 写测试：HKD／USD 完整 60 月均为 1%；缺月、59 月、缺 FX、缺时间分别阻止；修改收益／时间／FX／资产／结构／参数使 is_current false；逐月来源保留；同 ID 相同资料折叠，冲突报告并剔除，重复上市身份不计两列；未知资产不得隐式丢失。
- [x] 运行测试观察缺失接口／行为失败。
- [x] 实现身份诊断后，重新计算 `reconcile_hkd(bundle, fx, adjusted_price_assets=...)` 与 `align_monthly(..., months=60)`；只保留身份和数据同时合格的列。将身份阻止原因加入逐资产报告。
- [x] 绑定完整 DataBundle 表、configs、raw_sources 散列和全部外部表；文件资料变化须重算，不以调用者提供资格代替。is_current 只检查当前输入指纹，不改变旧快照。
- [x] 跑针对测试及现有收益／共同窗口测试，确认输入不变、列与资产 ID 一致、空池仍有 60 行稳定 schema。

## Task 3：验收导出与收尾

文件：新增 `scripts/verify_candidate_inputs.py`、`outputs/acceptance/S05A/README.md`、`checks.txt`；更新 README、使用指南及总流程进度。

- [x] 合成输入从既有 S03 人工场景的原币收益重新构造 DataBundle，先独立写明预期：晚时点两个数据合格资产、每项 60 月 1%；另外三项分别缺月／59 月／缺 FX。导出 data_eligibility.csv、hkd_matrix.csv、coverage.csv、structures.csv、input_evidence.json。
- [x] 读取 S02 保存的真实日线版本，保留其来源；直接接月度入口应 monthly_preparation_required 且矩阵 60×0，不自动聚合或伪造时间。单独导出真实阻止报告，不冒充真实月度池成功。真实多日记录还会触发原 S03 的 ambiguous_return；适配层保留该原因，同时明确说明频率准备要求。
- [x] `.venv/bin/python scripts/verify_candidate_inputs.py --output outputs/acceptance/S05A` 核对预期并保存；导出元数据标明研究模式、HKD、60 月、声明时间、历史认证 false。
- [x] 运行 `.venv/bin/python -m pytest -q`、本地包无依赖重装及安装路径检查；请求独立只读代码复核，修复重要问题后补测。
- [x] 更新文档，用文件路径给出本步查验方法；不将 S05 整体或 B/C 标为完成。
