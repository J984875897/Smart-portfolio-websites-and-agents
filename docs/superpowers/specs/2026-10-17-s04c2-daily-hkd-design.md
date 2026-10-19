# S04-C2：日线汇率端点与港币收益预览

本步承接用户批准的分步流程及「开始下一步」，范围是 C2。常规实现选择不重复要求批准；完成计算、界面及证据后停在可查验处，C3 历史可得认证另行推进。

## 方案

采用自然月末估值标签 + 同月最后观察到的日线 FX 端点，保留真实观察日及陈旧天数，复用 S03 `reconcile_hkd`。另外两种办法是要求自然月末当天必须报价（周末会无谓阻止），或直接前向填充（会隐藏过旧、缺失及观察日期）。本方案不宣称价格与汇率在相同瞬间成交，是当前数据版本的月度估值预览。

产品价格继续使用 C1 六个样本、日历完整性、前月锚点及复权确认。自然月末标签只用于连接，不改写原始报价日；价格实际终点与 FX 实际终点并列显示。HKD 产品使用固定 1，不需要美元汇率，FX 失败不得阻止其本来有效的原币收益。

## 端点政策

FX 输入严格列 `date,currency,hkd_per_unit,source_name`，本步只接 USD，单位固定每美元兑港币，不自动求倒数。文件通过既有 `read_file` 读 CSV/XLSX 并保留字节哈希、工作表和行号。重复列拒绝；布尔值、零、负数、NaN、inf 和未知日期均不变成有效数值。输入未修改。

对 C1 monthly 表的每个自然月末（包括前月），先从该自然月全部观察行选最大日期；不得用下月/未来报价，不得跨月回退。最大日期行有重复（即使相同）、无效数值/来源/币种时阻止端点，不退到更早的有效行。无法定位的非法日期使全部 USD 端点阻止；非 USD 输入拒绝，防止方向/币种混用。较早的无效行进入逐行诊断，但不否定一个正确的较新端点；本政策只认证端点，不认证完整 FX 日历。

`max_age_days` 为整数 0–7，默认 7，边界包含等于；这是研究假设，非官方期限。月末与观察日期相差超过上限阻止。用户必须确认每美元兑港币口径（`fx_confirmed is True`）；未确认保留端点诊断但不输出 USD 港币收益。月份成熟和 as_of 沿用 C1；FX 观察日期不推导发布时间或历史可得性。

## 核心接口

`DailyHkdResult` 包含 `prices: DailyMonthlyResult`、`fx_observations`（逐行诊断）、`fx_endpoints`（每月末端点）、`reconciliation`（恰好每目标月一行，包括阻止）、`metadata`。

`connect_daily_hkd(prices, fx_frame=None, *, fx_confirmed=False, max_age_days=7)` 接受 C1 `DailyMonthlyResult`。从已有有效 local_return 构造临时月度 total_return DataBundle，选出 FX 端点后以自然月末标签交给 `reconcile_hkd`，不重写换算公式；C1 blocked 必须继续 blocked，数值全为空。各目标行附价格起止实际观察日期、FX 起止实际日期/年龄/来源哈希/行号、FX_return、cross_term、hkd_return、status/reason、`available_at=''`、`historical_eligible=False`。USD 两端均通过才计算；HKD 为 1。metadata 保存价格及 FX 来源、政策、确认、输入哈希、单位和限制。

`cached_daily_fx(root,run_id)` 返回规范 FX DataFrame（attrs 含 manifest/source_status/source_name/source_hash）。只读验证完整快照，重解析权威原始响应，不依赖派生 CSV。支持 schema1 的 Yahoo HKD=X（close；代码、currency=HKD、CURRENCY、Europe/London 身份；显式非官方），schema2 HKMA_USDHKD（全部成功 HTTP200 原始页，按原分页顺序与范围检查）。原始布尔 quote 在数值转换前拒绝。success/partial 可诊断，partial 来源全部 USD 港币收益阻止；unavailable/cancelled 无证据拒绝。HKMA 不与 Yahoo 自动互换。下载开始或获取时间仅作来源记录。

## 界面

新增「日线港币查验」，保持旧七页不变。三步：价格来源/月份 → 汇率来源/单位确认/最大年龄 → 点击查验。价格选人工完整/缺末日案例或 schema1 缓存；USD FX 可显式选择人工、缓存（Yahoo/HKMA 清楚命名）、CSV/XLSX 导入并选择工作表；HKD 不显示必须 FX 输入。

默认人工 SPY 2025-01，价格 100→110、汇率 7.8→7.9，两个确认默认未勾。两个确认后 USD 原币 10%、FX 1.282051%、交叉项 0.128205%、港币 11.410256%；HKD 原币与港币均 10%。人工缺期末月 FX、过旧、重复末日可见失败原因。先显示中文摘要/对照，折叠完整诊断与 CSV/JSON。参数、文件/工作表、确认、目录、缓存 manifest 变化立即撤下旧结果及导出；每次重渲染复核缓存字节，错误撤下旧结果。不下载、不保存 DataBundle、不送入共同窗口、不计算候选 N。

## 验收与边界

先失败检查再实现：独立手算 100/110、7.8/7.9；USD/HKD、两端缺失、年龄等于/超过 7、0、周末跨月禁止、最新坏值不得回退、重复、非法日期、布尔数、源 partial、损坏快照、确认失效、月未成熟、local blocked、溢出及不变性。AppTest 检查三步、两确认、失败案例、旧结果撤下、无网络/无 DataBundle 修改、缓存损坏。独立脚本从原始 JSON 算端点比值，与生产输出比较，故意篡改计算结果需被发现。

真实验证优先使用已经验证的 S01 旧原始快照，显式离线重放并复用完整文件哈希核验。旧快照全历史 partial 不升级，本目标窗口端点是否可预览单独标记；不改装成新 success 缓存。无需重复已失败联网请求，在线可用性仍沿用已有失败记录。真实数据与人工数据在证据中分别标注。全套回归、宽窄屏及 CSV 下载在最终验收核实；S04 总体及历史认证保持未完成。

来源核对 2026-10-17：[HKMA 日线字段文档](https://apidocs.hkma.gov.hk/documentation/market-data-and-statistics/monthly-statistical-bulletin/er-ir/er-eeri-daily/) 明确 end_of_day 与 usd（HKD per unit of foreign currency）。文档未提供逐条历史发布时间；不填 available_at。

## 审查后的必要边界修复

价格和FX缓存均在范围筛选前调用共用 `validated_timestamp_rows`；原始时间戳必须为非布尔有限数、可定位且唯一，含null、NaT或不可表示的巨大整数时ValueError，不得丢行后通过。helper新增于provider模块，不改变既有共享parse/audit行为。FX的source_row从原始数组1起序号映射恢复，不使用排序后的索引。独立auditor还要求确切的目标行/端点数量、唯一自然月标签，以及最终对照中的FX实际日期、年龄、报价逐项匹配独立参考。这些修复落实既有数据可追溯和失败关闭要求，不扩大到C3。
