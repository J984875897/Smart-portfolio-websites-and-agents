# S04-C1：日线交易日与月度原币收益查验

用户已批准分步流程并要求「进行下一步」。本轮落实 S04 后续日线连接的第一个验收单元；依据其「不要一口搞完全部」的要求，把价格月度聚合 C1、汇率配对与 HKD 连接 C2、历史可得证据 C3 分开。已有批准范围内的常规实现选择不重复请求批准。

## 方案与边界

选择版本锁定的 exchange_calendars 日历 + 逐日查验 + 复用 S03 原币收益公式。另两种办法是只取文件最后有效行（不能识别末日缺失），或本轮同时实现日历、FX 和历史发布时间（缺乏独立检查点）。本轮只交付 C1，原始缓存、S02 DataBundle 与 S03 界面保持接口兼容。

新增「日线月度查验」页面，三步操作：选择人工案例／已下载缓存 → 选择产品、月份并确认复权口径 → 点击查验。先展示中文结果摘要及阻止原因，再折叠逐日明细与来源。默认人工完整案例，无网络、无自动计算、无自动保存。页面解释下一步去哪里；不把开发阶段编号当作用户必须了解的知识。

## 输入、日历和时间

固定六个现有价格样本 AAPL、0700.HK、SPY、2800.HK、AGG、GLD，不接 HKD=X 价格聚合。USD 产品使用 XNYS 美股现金市场日历代理，香港产品使用 XHKG；美国不同场所的映射为明确代理，不认证具体产品停牌和成立时间。依赖 exchange_calendars==4.13.2；其规则不等于官方全历史认证。官方抽样核对 2025-01 美港交易日和半日、2024-12 半日、2025-03 夏令时。页面／导出携带库版本和映射标签。

日历函数 trading_schedule(market, start, end) 接受 XNYS/XHKG、严格 YYYY-MM-DD，[start,end)，范围 2014-01-01 ≤ start < end ≤ 2027-01-01。输出 date、calendar_close_at（带 UTC 时区 ISO）、market_timezone、calendar、calendar_version。close 是日历连续交易结束，不称价格观察时间或供应商发布时间；香港收市竞价可晚于此时间。Yahoo timestamp_utc 也不作为收盘时间。

聚合函数 aggregate_daily_prices(prices, *, symbol, start_month, end_month, confirmed=False, as_of=None) 接受 date、adj_close 和可选来源 attrs。月份严格 YYYY-MM，2015-01 至 2026-12，起止均包含；窗口包含起月之前完整一个月。as_of 为带时区 ISO，默认当前 UTC。月度成熟采用保守规则：该市场下一自然月第一日 00:00 已到，等于允许；不以最后报价提前宣称整月完成。

## 查验与输出

DailyMonthlyResult 包含 sessions、monthly、returns 三张表和 metadata。sessions 包括所有预期交易日及窗口内非交易日输入，显示原输入日期、价格、来源行号与 missing_price / invalid_price / duplicate_date / unexpected_session / ok；不补零、不前向填充、不删除冲突来制造有效月份。日期非法无法定位月份时整个窗口阻止。范围外合法行忽略，全部输入内容仍绑定来源哈希。空表输出完整缺日报告。

monthly 每月一行（包括前月锚点），保留自然月末标签、expected_end_date、last_observed_date、end_price、calendar_close_at、expected_sessions、valid_sessions、missing_dates、status、reason。只有该月全部预期交易日恰一条有限正复权价格、无重复／非交易日／非法日期、月份成熟时，才允许形成有效月末锚点。缺最后交易日不得回退；缺月中日也按当前保守完整性政策阻止该月。status=valid 仅指日历价格预览，不代表资格或历史可得性。

returns 恰好目标月份数；将自然月末锚点送入现有 build_local_returns，复用公式 end/start−1。只有本月和前月均有效且 confirmed 明确为 True 才输出 local_return，否则 NaN 和具体阻止原因。不重复加分红或拆股。附 calendar、calendar_version、market_timezone、currency、source_name、source_hash、available_at=''、historical_eligible=False；下载/运行开始时间和收盘标签不得填入 available_at。USD 收益明确为原币，HKD 直接产品收益仍未被认证为正式候选。没有 S03 共同窗口交接按钮。

## 缓存边界

cached_monthly_prices(root,run_id,symbol,*,start_month,end_month,confirmed=False,as_of=None) 只读 schema1 Yahoo 缓存，全文件验证后从原始 JSON 重新 parse_yahoo_chart，核对代码、币种、工具和 timezone，再按 manifest 请求边界筛选。metadata 保存完整 manifest、raw_sha256、run_id、download_started_at、source_status。success 只允许日历预览；partial 可输出诊断但全部收益阻止为 source_not_success；unavailable/cancelled 或无原始证据拒绝。来源身份不匹配与损坏失败关闭。每次页面重新渲染，包括导出时，重新核验所选快照及其 manifest；换根目录、参数、确认、月份、产品、案例、源内容都撤下旧结果。无联网，无覆盖快照，无写 DataBundle。

## 验收

人工两月每日价格 100→110，确认口径后月收益 10%，未确认 NaN。覆盖缺前月、末日缺失、月中缺失、重复、周末额外行、无效值／日期、无时区 as_of、月未成熟、行重排、缓存哈希损坏、身份及 partial。官方日历样例：2025-01 XNYS 20 日（1/9 休市），XHKG 19 日，1/28 close 为 04:00 UTC；3 月美国收盘 UTC 随 DST 改变。真实小样本只显式调用现有下载器下载 SPY/2800.HK 的 2024-12-01≤date<2025-02-01，然后离线查验；若失败照实记录。独立直接原始响应端点比值核对，不以生产聚合函数复算自己。保留 RED/GREEN、AppTest、完整回归、实际页面检查和验收说明。

官方资料核对（2026-10-16）：[日历库及 API](https://github.com/gerrymanoim/exchange_calendars)、[HKEX 2025 日历](https://www.hkex.com.hk/-/media/HKEX-Market/News/HKEX-Calendar/2025-HKEX-Calendar.pdf)、[NYSE 2025-01-09 特别休市](https://ir.theice.com/press/news-details/2024/The-New-York-Stock-Exchange-Will-Close-Markets-on-January-9-to-Honor-the-Passing-of-Former-President-Jimmy-Carter-on-National-Day-of-Mourning/default.aspx)、[HKEX 交易机制](https://www.hkex.com.hk/Services/Trading/Securities/Overview/Trading-Mechanism?sc_lang=en)。

## 执行时已确定的离线复算路径

新 SPY／2800.HK 下载分别 timeout／transport_error，原失败快照保留，不自动重试。为继续核对真实计算，验收脚本增加显式 --s01-manifest 入口：复用 S01 的 load_verified_manifest 验证全部旧原始文件，严格选择各代码唯一的成功历史响应，再做本窗口价格诊断与独立端点复算。该入口仅产生验收表，不增加页面依赖，不将 S01 快照改装为新下载成功，也不改变 partial 缓存全部阻止规则。旧历史的其他月份可有缺失，本次两月通过只表示本窗口日历价格可预览，不对旧快照整体合格性作结论。
