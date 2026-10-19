# S03-C：港币现金收益代理与可得性查验

依据已确认的 PROJECT_PLAN、分步计划及用户“开始下一步”的执行授权，实施既定 S03-C。方法属于既定港币短期利率代理范围的具体化。本步不计算 Sharpe、不生成可投资现金持仓、不接入 S04 下载器。

## 方法与选择

采用上一月末香港 16:00 已知的 HKAB 1 个月 HIBOR fixing，按自然月末到自然月末的实际日数，以单利 ACT/365F 转成港币月度现金收益代理：`rf_hkd = quote_percent / 100 * days / 365`。闰年分母仍为 365。报价 3.65、31 天对应 0.0031（0.31%），29 天对应 0.0029（0.29%）。年化报价百分数、期间收益小数在表格中明确区分。

三种路线中，逐日复利 HONIA 更接近隔夜参考，但需要可靠逐日覆盖、假期和发布时间；外汇基金票据需要价格、折价收益率和期限衔接。当前选 HIBOR 单利代理以获得可追溯、可手算的月度基准，保留前两项为扩展。HIBOR 含无担保银行信用与流动性风险，不能称为真正零风险资产。固定报价跨完整自然月的计息是本研究的近似假设，不声称真实 1M 存款合同恰好在月末到期、个人能取得同一利率、或收益已经实现；真实合同的起息、假日调整和期限可能不同。

官方依据（2026-10-16 核查）：

- [HKMA 日度利率文档](https://apidocs.hkma.gov.hk/documentation/market-data-and-statistics/monthly-statistical-bulletin/er-ir/hk-interbank-ir-daily/)：`segment=hibor.fixing`，`ir_1m` 单位 percent per annum；HKAB fixing 通常香港营业日 11:15 发布，区别于停止提供的收市 HIBOR。
- [TMA Code，2.4 Interest accrual basis](https://www.tma.org.hk/PubFile/TMACode.pdf)：港币交易 ACT/365，闰年亦 365，利息 `P*r/100*days/365`。该来源支持计息基础，不将自然月代理近似说成官方存款产品定义。
- [HKAB HIBOR 页面及规格入口](https://www.hkab.hk/en/rates/hibor)：银行间报价、期限及发布；本轮规格 PDF 直接抓取超时，不以搜索摘要作为独立历史时间认证。

## 输入、时间与质量

`risk_free_monthly(quotes, *, end_month, decision_at, months=60) -> RiskFreeResult`。只接受明确月度选择表，每个目标自然月末 `date` 恰好一行。不自动选择更旧替代报价；重排不改变结果，额外窗口外记录不补缺。日期为严格 YYYY-MM-DD，结束月份 YYYY-MM；months 正整数（不含 bool）；决策为带时区 ISO datetime。

输入列为 `date,quote_at,available_at,quote_percent,currency,benchmark,tenor,day_count,compounding,source_name`。合法值分别 HKD、HKAB_HIBOR、1M、ACT/365F、simple；每行单位由 `quote_percent` 字段固定为年化百分数，不猜测 0.0365 是 3.65%。quote_at 是观察时点，available_at 声明**当前报价版本**及全部输入的最晚可得时点。两者必须带时区，available_at >= quote_at，且二者 <= 月初锚点（上一月末香港 16:00），available_at <= 决策。quote_at 须落在月初锚点之前最多 7×24 小时以内，边界允许相等；这是研究陈旧阈值，不是交易日历认证，不证明它确为当时最新报价。整月的期末香港 16:00 <= 决策才可进入历史统计。可得时间由导入者声明，不自动从 fixing 日期或今天下载时间猜测。

有限实数报价（排除 bool），允许负利率及零，不裁剪；期间收益必须有限且 >= -1。非法行、缺月、同月多行（包括日期标签错误的重复）、非自然月末标签、任何币种／口径／来源错误均阻止该期间，期间收益为 NaN。没有适用代理时状态 unavailable，禁止填零或换 USD RF。结构错误（重复表头、缺必需列、参数非法）抛 ValueError，界面清空旧结果并显示错误。

保持源表不变。CSV/XLSX 采用既有 read_file；文件内容、hash、sheet、物理行通过重新读取原字节绑定。携带 raw_bytes 的表必须完整且未修改（值和索引），忽略伪造 provenance 列／attrs 的行号，只信重新解析的 metadata。普通 DataFrame 的证据为计算用完整表 CSV 的 hash 与明确 dataframe.csv 标签，不当作外部文件认证。

## 输出与界面

RiskFreeResult 包含 report（固定每月一行，date,start_date,end_date,start_at,end_at,days,status,reason,rf_hkd,quote_evidence，及唯一报价的 quote_ 前缀原字段/来源证据），series（固定月末索引、name=rf_hkd、无效 NaN）、available（所有目标月均 valid）、window_start/window_end、decision_at。输出 currency=HKD、frequency=monthly、proxy_method=hibor_1m_simple_act365f 元数据。available 仅说明声明证据通过，不代表真实来源已认证。

侧栏新增“港币利率查验”，默认仍数据导入。独立页面：人工案例／上传 CSV或XLSX、结束月、月数、香港决策时点、口径说明、样例及模板下载、按键计算、中文逐月摘要、完整证据及两个结果 CSV 下载。默认人工案例“完整报价”，2024-03 结束、3 个月、2024-03-31T16:00:00+08:00 决策；年化报价 3.65% 转出 0.31%、0.29%、0.31%。人工失败案例：缺中间报价、月中报价、版本月底才可得、USD 报价。所有样例 SYNTH 标注，不改动原币 bundle。

更改模式、案例、参数、上传字节/文件名/工作表均立即撤下旧结果和结果下载。失败不能保留上一次成功。界面只调用核心、不联网、不写数据版本；不在本步提供 Sharpe 数值或下游候选资格。可以输出未来供风险统计按同月日期严格连接的 RF 序列，不能按位置连接或在缺月情况下减掉错误月份。

## 验收边界

核心测试包括手算、闰年、零负报价、单位、7天边界、观察/可得/决策相等及前后一瞬、期末成熟、重复/缺月/非月末、时区、非法参数、NaN/inf/bool、输入不变及文件追踪。脚本生成可独立复算的成功和失败 CSV；AppTest 检查关键结果、失效、错误与上传；实际浏览器检查页面、窄屏及图标无重叠。

S03-A/B/C 的月度声明证据链完成后，S03 月度子范围可验收。真实日线自动聚合、交易日历认证及历史发布时间自动接入继续明确未交付，不能把人工案例通过当真实数据已可回测。S04 在用户下一次指令后另行开发。
