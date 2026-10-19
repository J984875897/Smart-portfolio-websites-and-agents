# S07-A 独立审查

**Mode:** PR Review  
**Scope:** 本次新增的 `src/portfolio/universe/{clustering,selection_ranking,selection,reasons}.py`、`scripts/verify_selection.py`、`tests/test_clustering.py`、`tests/test_selection.py`、`tests/test_selection_verification.py`。按冻结设计审查 S07-A；结合既有 S05、Pearson 和文件证据实现核对接口，不涉及 B/C。所有指定文件均已阅读，较深入的运行验证集中在高风险边界。  
**Health Score:** 90/100（balanced；2 Important 对应 Warning）  
**审查日期:** 2026-10-19

发现 2 项 Important；修复前不宜将 S07-A 标为已通过独立审查。未发现 Critical 或 Minor。

## Findings

### Critical

无。

### Important

**1. 两次 S05 调用耗尽筛选迭代器，可能使明确的范围排除失效**

位置：`src/portfolio/universe/selection.py:71–72`。

Symptom: `select_members` 将同一个 `screening_options` 连续传给 S05 两次。S05 的 `_options` 接受一般可迭代对象并用 `set(value)` 消费；因此第一次调用会耗尽生成器／迭代器，第二次才用于实际选择的筛选得到不同参数。使用现有 SYNTH 样本、K=20 实际复现：

```python
aid = 'SYNTH_SCREEN_000'
a = select_members(c, k=20, excluded_asset_ids=[aid])
b = select_members(c, k=20, excluded_asset_ids=iter([aid]))
```

结果：列表输入的 N=99、该资产未选、证据排除列表为 `[aid]`；迭代器输入的 N=100、该资产实际入选、证据排除列表变成 `[]`。直接单次 `screen_candidates(..., excluded_asset_ids=iter([aid]))` 的 N=99，说明该输入本来是 S05 接受的。`markets` 和 `asset_classes` 的迭代器则在第二次调用变成空范围，错误阻止选择。

Source: *Code Complete* — Defensive programming；*Domain-Driven Design* — Aggregate invariant boundary。筛选范围与实际选择必须使用同一个确定的规则快照。

Consequence: 用户明确排除的产品仍可进入草稿，N 和 K/N 的比较池语义也被改变；现有证据只记录第二次的空排除参数，无法揭示已经消费掉的原始意图。不是仅有额外计算开销。

Remedy: 在两次调用之前将所有会消费的筛选集合参数稳定地物化一次，并保证两个调用使用相同快照；或先单独验证原对象，再仅对规范化对象执行一次真正筛选。新增列表／迭代器等价回归，至少断言 N、排除资产不入选、指纹和证据一致。

**2. 合法的文件来源排序长表无法经过现有标准读取路径导入**

位置：`src/portfolio/universe/selection_ranking.py:27–39`。关联契约：`src/portfolio/data/importer.py` 的 `read_file`、`src/portfolio/universe/input_evidence.py` 的 `verified_frame`。

Symptom: `prepare_ranking` 先用 `verified_frame` 要求文件表保持原样，之后又只接受 `Real` 类型的 value；但现有 `read_file` 对 CSV 和 XLSX 均保留文本单元格。一个非空来源、合法带时区时间及合法费用数值的文件表因此必然被拒绝。实际复现无需落盘：

```python
raw = (b'asset_id,metric,value,source_reference,available_at\n'
       b'SYNTH_SCREEN_001,annual_fee_rate,0.001,declared fee document,'
       b'2025-01-01T00:00:00Z\n')
frame = read_file(raw, filename='ranking.csv')
prepare_ranking(frame, asset_ids={'SYNTH_SCREEN_001'},
                decision_at='2025-02-01T00:00:00Z')
```

结果：`ValueError: ranking values must be real numbers or missing`。调用者先用 `pd.to_numeric` 转换 value 并保留文件 attrs 后，则得到 `ValueError: ranking_data: file-backed frame must be unchanged; reload original`。现有测试只覆盖纯内存数值表，没有覆盖项目标准文件读取器输出。

Source: *Clean Architecture* — Boundary translation；*Code Complete* — Input validation。原始来源一致性校验和领域数值解析需在边界按顺序处理。

Consequence: 通过现有文件证据机制提供的合法费用／流动性长表无法参与排序；调用者必须绕过标准读取路径或丢弃文件来源绑定才能使用这些资料。该问题会直接影响后续上传接入，且已存在于本次核心接口。

Remedy: 先对原文件表执行 `verified_frame`，再对已验证副本解析规范数值文本和空单元格，同时保留其原始来源证据；继续拒绝布尔、非法文字、无穷及单位越界。保持纯内存输入的既定严格规则。增加 `read_file` → `prepare_ranking` 的有效 CSV/XLSX 与变更文件拒绝回归。

### Minor

无。

## 核对结果与验证范围

- complete linkage 使用簇间最大距离，合并堆以排序后的成员元组确定真正等距时的并列顺序；阈值含 1e-12 容差，负相关不取绝对值。用独立直接扫描实现对照 100 组含大量并列值的 8×8 对称矩阵，全部合并顺序一致；同行列重排的指纹一致。
- 缺失矩阵校验只接受完全不可用的行／列；未知相关性保留 NaN 和 U 组，未知组不计入已知覆盖。理由和候补保留未知值，候补明确标记替换可行性未评估。
- 静态核对 K 范围、S05 的 K/N、成员排除不改变 N、可选数不足、手动冲突、手动占位及类别缺口检查。除上述筛选迭代器缺陷外，未发现这些逻辑的实际违例。
- 排序记录以 UTC 时间规范化后取决策时点之前的最新记录，未来记录计数但不参与排序；费用／流动性默认未知，排序先覆盖未覆盖的可用簇。记录、来源引用和可得时间进入选择指纹。文件表接入存在上述第二项缺陷。
- 输入规范化使用深复制，分组矩阵也复制；未发现本次实现直接修改调用者数据。未重复整套测试，定向复现均使用 `PYTHONDONTWRITEBYTECODE=1`，未写入测试或产品文件。
- 证据保留 `selection_status=draft`、`portfolio_constructed=False`、`historical_universe_certified=False`、`weights_generated=False` 和 `diversification_certified=False`；高相关配对单独输出，没有将相关性分组误称底层持仓重复或充分分散。
- 测试已覆盖主流程、错误输入、未来资料、全同向、常数、重排、JSON 和输出别名。两项缺陷对应的接口边界均尚无测试；没有发现需要另列的测试结构问题。

## Summary

优先固定筛选参数快照，避免范围排除失效；随后打通保留来源证据的排序文件解析。此次只写入本审查记录，没有修改实现、测试、数据或技能历史文件；本记录描述的是修复前状态，不构成后续修复的复审结论。

## 修复后复审（2026-10-19）

**当前结论:** 两项 Important 均已关闭；当前未关闭项为 0（Critical 0 / Important 0 / Minor 0）。本次修复范围内未发现新缺陷。当前 Health Score 为 100/100；保留上文作为首次审查的问题证据，不表示整个产品或投资结果已获认证。

1. **首次发现 1：已关闭。** `src/portfolio/universe/selection.py:71–72` 现在先用 `_validate(candidate)` 校验原对象，然后只对规范化副本运行一次 `screen_candidates`，所有筛选集合仅在一次筛选中消费。新增 `test_once_only_scope_iterators_preserve_exclusions` 同时比较列表与迭代器形式的范围排除、markets 和 asset_classes，断言相同成员、相同指纹、N=99、被排除资产未入选。原输入校验仍发生在规范化之前，没有用排序操作掩盖不合法原始窗口。
2. **首次发现 2：已关闭。** `src/portfolio/universe/selection_ranking.py:27–37` 现在先验证原文件内容，再仅对文件来源的 value 文本进行数值／空值解析；`file_evidence` 在解析前记录，包含原始字节哈希，并随排序证据进入选择指纹。解析只改局部标量，不改源表；纯内存字符串、布尔、非法文字、无穷和单位越界仍有拒绝路径。新增参数化测试覆盖 CSV、XLSX 的标准 `read_file` 路径、有效费用参与选择、raw_sha256 保留、源表保持文本，以及改动值后按文件一致性检查拒绝。

独立运行的定向回归命令与实际输出：

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_selection.py -k 'once_only_scope_iterators or standard_file_rankings'
3 passed, 33 deselected in 4.40s
```

未重复整套测试；“36 passed”的完整选择测试结果由实施者提供，本次复审仅独立确认上述 3 个新增案例及相应修复代码。复审仍只向本文件追加记录。
