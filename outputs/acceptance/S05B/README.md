# S05-B：筛选规则与数量验收

本步交付筛选核心和离线文件，工作台页面在 S05-C。输入为已验收的 S05-A CandidateInput；不联网、不增加真实产品、不选择组合成员或权重。

## 如何查验

| 文件 | 可核对的结果 |
| --- | --- |
| [cardinality_cases.csv](cardinality_cases.csv) | 17 个数量案例：8 个边界、8 个非法 K、1 个空池 |
| [universe_audit.csv](universe_audit.csv) | 100 项独立 SYNTH ID，全部合格；股票 ETF 保留 |
| [universe_n99_audit.csv](universe_n99_audit.csv) | 手动排除最后一项，N=99，原因 manually_excluded |
| [synthetic_hkd_matrix.csv](synthetic_hkd_matrix.csv) | 同一 60 月、100 列、每月人工 1% 收益 |
| [real_universe_audit.csv](real_universe_audit.csv) | 已有真实 3 项仍阻止，缺结构声明且日线尚未接入共同月度窗口 |
| [summary.json](summary.json) | N100 通过、N99 阻止、真实 N0，来源文件散列前后相同 |
| [synthetic_evidence.json](synthetic_evidence.json)、[real_evidence.json](real_evidence.json) | 输入／筛选指纹、固定窗口、选择参数和证据模式 |
| [checks.txt](checks.txt)、[full_test_checks.txt](full_test_checks.txt) | 离线验收及完整测试实测输出 |

K=30 时：N=100，30/100=30%，允许；排除一项后 N=99，30/99≈30.303%，显示“候选产品池过小”，最低 N100、缺口1。K 必须是20–100整数，布尔值、30.0、小数与文本均不能作为合法目标数。数量通过提示明确保留“尚未生成组合”。

人工 100 项均为 SYNTH_SCREEN 编号，数据刻意固定便于复算。它们不是100项真实产品，也未证明分散化、风险或投资表现；本步不因相关性高就认定身份重复，相关性／分散化评估留在 S06／S07。

## 核心规则

- 默认排除直接个股、单公司 ADR、单只 REIT 和直接优先股；允许股票 ETF、股票基金及 REIT ETF。开启个股后可进入候选，不代表必须持有。
- 杠杆、反向、复杂结构及衍生品两种模式均排除。index、FX、现金收益代理不是可计数投资产品。所有产品需明确的普通结构声明及来源，混合、可转债、优先股基金和黄金商品工具也没有免检例外。
- 市场来自明确交易所映射，与交易币种独立；未知交易所、市场矛盾、工具分类冲突、缺类别或结构证据均有原因。分类按枚举，不查名称关键词。
- 相同上市身份的多个 ID 全部排除，回导入页修正；HKEX/SEHK 先按同一交易所身份比较。明确跨上市产品组须提供一致组别、组内代表和声明来源，只留代表；缺代表或待核验整组不通过。未提供关系标记 not_verified，不声称跨市场身份已认证。
- 漏斗依次记录资料行数、身份合格、范围内、最终数据合格 N；逐项原因可以多个，漏斗不累加原因数。手动排除、市场、工具、经济类别和个股开关会改变 N。
- 上游矩阵、资产身份、结构及报告按 asset_id 对齐；矩阵要求同一60个月份且无重复列、无非有限收益。修改输入或选项会改变筛选指纹；缺数据保持排除。

结构资料与跨上市资料是输入者声明，不是软件已独立核实供应商。研究模式保持 current_universe_retrospective、timing_basis=importer_declared、historical_universe_certified=false。B 的一致性检查不能替代 A 重新验证原始来源；界面接入时仍需先判断 A 输入是否过期。

## 运行与接口

在项目根目录运行：

```bash
.venv/bin/python scripts/verify_candidate_screening.py
.venv/bin/python -m pytest tests/test_cardinality.py tests/test_universe_screening.py tests/test_candidate_screening_verification.py -q
```

```python
from portfolio.universe.samples import sample_candidate_inputs
from portfolio.universe.inputs import prepare_candidate_input
from portfolio.universe.screening import screen_candidates

candidate = prepare_candidate_input(
    *sample_candidate_inputs(), end_month='2025-01',
    decision_at='2025-02-01T06:00:00+08:00')
result = screen_candidates(candidate, k=30, markets=('US','HK'), include_stocks=False)
print(result.counts, result.cardinality)
print(result.audit[['asset_id','status','reason']])
```

上述小样本 N=2，最低100，缺98；大样本仅在验收脚本中构造。`tool_types=None`／`asset_classes=None` 表示全部，空元组表示不选择任何类别；市场空元组同样得到 N0。搜索与分页在 C 层处理，不是资格条件。

可选 `listing_relations` 是 DataFrame，字段：asset_id、product_group、representative_asset_id、review_status（declared／pending）、source_name、source_reference、source_as_of（YYYY-MM-DD）。文件输入沿用 raw_bytes／source_file／source_sheet 属性验证与来源散列。候选筛选只保留声明的代表，不因代表被过滤而自动切换另一上市条目。

独立复核发现并修正了 HKEX/SEHK 别名重复计数问题：65项独立产品加两个别名重复条目原本错误得到67并越过K20门槛，修复后两个冲突条目排除、N65并阻止。保留回归测试和待修正身份映射提示。

最终定向测试67项通过；完整回归581项通过，2条既有 XHKG 日历依赖弃用警告。独立复核确认无遗留 Critical／Important 问题。本地包已重新安装，运行时源文件逐字节核对一致；本步未修改页面。
