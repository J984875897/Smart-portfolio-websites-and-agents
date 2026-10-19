# S01 数据来源矩阵

## 后续实测更新（2026-10-17）

以下 S01 表格保留 2026-10-12 的历史结论；当前界面已具备显式下载和缓存，不能再把文末“没有下载器”理解为现状。新实测及原始证据见 S04 汇总核查：Yahoo 2025-01 的 SPY／2800.HK／HKD=X 均成功，四套 French 因子 2025 年各 12 月成功，HKMA 仍为 TLS 失败。覆盖完整前月的两月请求中，两个价格成功、Yahoo FX partial，美元港币收益链路被阻止；没有改写旧 S01 结果。没有验证全部免费产品覆盖、历史名单或退市覆盖。本轮未重新核对收费服务价格／额度，后文权限表仍是原核验日记录。

核验日期：2026-10-12。真实快照 `20261012T143920Z-6f4d426f`；请求日线区间为 **2014-12-01 ≤ 日期 < 2026-01-01**。状态、行数、字段与 SHA-256 见 source_probe.csv；完整查验入口为 S01 验收记录。

结论：已有无须 key 的真实行情、月度 FX 可得性预览和因子路径，可以继续 S02。**没有验证到一个能免费、稳定地覆盖全部产品及全部关键字段的接口。** 本步只有六个识别样本，不能据此宣称正式候选池合格或满足 K/N ≤ 30%。

## 1. 已实际请求的来源

| 来源／数据 | 是否需要 key | 本次实测 | 范围／限制 | 后续处理 |
| --- | --- | --- | --- | --- |
| yfinance → Yahoo：六类产品日线 | 不需要 | 六个产品均返回；5 个产品字段检查成功，2800.HK 有 1 条空行，标记 partial | 含 OHLCV、Adj Close、分红、拆股；此处未做交易日历或完整公司行动审计 | 用日线作为来源证据；S03 确认总收益及估值规则，S04 再接入更新 |
| Yahoo：`HKD=X` 日线 | 不需要 | 返回 2,893 行，7 条 Close 缺失，标记 partial | 报价方向 HKD per USD；非 HKMA 官方汇率。报价时点不等同于美港收盘时点 | 原始缺失保留；不自动替换官方路径的身份 |
| Yahoo：月末最后真实有效 FX 观察预览 | 同上 | 133 月均有报价，缺月 0，距月末最多 2 个日历日 | 明示实际观察日；以 7 天作 **S01 陈旧性筛查假设**。不是补齐后的日线，也不是最终 S03 换算规则 | 可作为 S01 月度 FX 可得性证据；跨市场可得时间仍待 S03 |
| HKMA USD/HKD | 不需要 | 当前环境 TLS 握手中断，SSLError；未取得数据 | 官方字段 usd 表示每单位美元对应港元；本次拟请求最近 8 条，原本也不足以证明全历史覆盖 | 暂列 unavailable；保留授权文件导入；S04 接入前重试和核对分页／历史期间 |
| French 美国 FF3 | 不需要 | 1,202 月，1926-07 至 2026-08；字段及连续性检查成功 | USD、月度百分数；保存原始 ZIP、原始 CSV及转为小数的预览 | S10 使用该文件的 SMB，不能借用 FF5 SMB |
| French 美国 FF5 | 不需要 | 758 月，1963-07 至 2026-08；成功 | 多 RMW、CMA；RF 同文件匹配 | CAPM／FF5 诊断的候选来源 |
| French 亚太除日本 FF3、FF5 | 不需要 | 各 434 月，1990-07 至 2026-08；成功 | USD；香港、澳洲、新西兰、新加坡的地区因子，**不是香港专属因子** | 股票诊断可用地区代理；香港／中国敞口的代理误差须披露 |

来源条件依据：[yfinance 官方仓库](https://github.com/ranaroussi/yfinance)说明其为研究教育工具，未获 Yahoo 背书，数据用途受 Yahoo 条款约束并提示个人使用限制。免费获取不等于无限请求、可公开再分发或有服务保证；本步不发布原始行情。库参数见 [history 文档](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.history.html)，实际参数另以已安装版本源码和请求快照为准。

HKMA 报价方向依据：[官方 API 字段规格](https://apidocs.hkma.gov.hk/chi/documentation/market-data-and-statistics/monthly-statistical-bulletin/er-ir/er-eeri-daily/)。文档字段可查，与本机 API 调用成功是两件事；requests 与 curl 客户端均出现 TLS 中断，尚不能确定是网络出口还是服务端原因，没有关闭证书检查。

French 的文件入口及美国历史生成口径修订见 [Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html)；地区因子币种、收益构成和国家范围见 [官方地区 FF5 说明](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/f-f_5developed.html)。本次原始 CSV 说明 RF 在 2024-06 更换数据来源；保存这些说明，不只保留数字。因子文件下载到 2026-08，不代表未来回归可以使用决策日以后数据。

## 2. 有免费层、受权限限制或收费的来源

本次只检查指定 key 环境变量是否存在，不输出其值。Alpha Vantage 与 Twelve Data 的 key 均未配置；脚本不接收 key，也不发送这些来源的行情请求。未来只在确认免费权限后单独实现适配。

| 来源 | 当前文档条件 | 本步动作 | 替代入口 |
| --- | --- | --- | --- |
| Alpha Vantage 月度调整行情 | 官方文档列 `TIME_SERIES_MONTHLY_ADJUSTED`，含调整收盘及月度分红；普通免费额度为 25 次／日。教育项目更高额度需要供应商核准 | 缺 key，未实测具体代码、历史覆盖或实际账号额度 | 授权 CSV／XLSX；之后可配置免费 key 再验证 |
| Alpha Vantage 日度调整行情 | `TIME_SERIES_DAILY_ADJUSTED` 明示 Premium | 不请求、不订阅 | 已验证 Yahoo 路径或文件导入 |
| Twelve Data Basic | 文档列 8 credits／分钟、800／日；美国股票／ETF、FX 等，内部非展示使用。具体端点按权重消耗额度 | 缺 key，未实测；免费层用途不能直接推断允许公开界面展示 | 文件导入；免费权限及显示条件确认后再适配 |
| Twelve Data 香港市场 | XHKG 页面列 Pro+／Venture+；提供试用代码不等于香港全市场免费 | 付费正式香港路径保持关闭 | Yahoo 小样本路径或授权导入 |
| HKEX 官方市场数据服务 | 有订阅、购买及许可证条件；不能把公开报价页等同于免费全历史 API | 不购买、不调用付费服务 | 授权 CSV／XLSX |
| WRDS／CRSP | 本次公开页面重定向登录；可能需要机构权限，但没有验证当前账号或数据授权 | 不尝试登录，不记录账户口令 | 用户在获准账户导出后导入，并记录来源／口径 |
| Morningstar、其他付费终端 | 需要单独授权的数据来源；本步未验证账户和 API 权限 | 保持未接入 | 授权导出后导入，并在导入时选择产品类型 |

依据：[Alpha Vantage 配额说明](https://www.alphavantage.co/support/)、[月度／日度调整 API 文档](https://www.alphavantage.co/documentation/)、[Twelve Data 定价和用途](https://twelvedata.com/pricing)、[XHKG 市场权限](https://twelvedata.com/exchanges/XHKG)、[HKEX 数据服务 FAQ](https://www.hkex.com.hk/Global/Exchange/FAQ/Market-Data/Getting-Market-Data?sc_lang=en)、[WRDS CRSP 入口](https://wrds-www.wharton.upenn.edu/pages/get-data/center-research-security-prices-crsp/)。这些是本次核对时的条件，接入时需重新验证。

## 3. 样本身份、币种和日期

下面区分产品成立／上市日期、供应商 metadata 的首个交易日、此次实际获取期间。代码只用于来源识别，**不是推荐持仓**。

| 代码 | 工具／经济敞口 | 交易币种 | 官方成立／上市信息 | Yahoo firstTradeDate | 本次实际期间 |
| --- | --- | --- | --- | --- | --- |
| AAPL | 个股／美国股票 | USD | IPO 1980-12-12 | 1980-12-12 | 2014-12-01 至 2025-12-31 |
| 0700.HK | 个股／中国与香港股票 | HKD | 上市 2004-06-16 | 2004-06-16 | 同上 |
| SPY | 股票 ETF／美国股票 | USD | 基金成立 1993-01-22 | 1993-01-29 | 同上 |
| 2800.HK | 股票 ETF／恒生指数（包括中国敞口） | HKD | 基金推出 1999-11；上市 1999-11-12 | 2008-01-02 | 同上，2025-10-24 缺值 |
| AGG | 债券 ETF／美国投资级债券 | USD | 基金成立 2003-09-22 | 2003-09-29 | 同上 |
| GLD | 黄金信托／实物黄金 | USD | 成立 2004-11-18 | 2004-11-18 | 同上 |

官方身份依据：[Apple IPO](https://investor.apple.com/faq./default.aspx)、[Tencent 上市公告](https://www.tencent.com/en-us/articles/1600069.html)、[SPY 产品页](https://www.ssga.com/us/en/institutional/etfs/state-street-spdr-sp-500-etf-trust-spy)、[盈富基金历史](https://www.trahk.com.hk/en-hk/trahk-fund/about-us/)、[HKEX 1999-11-12 公告](https://www.hkex.com.hk/News/News-Release/1999-SEHK/991112news?sc_lang=en)、[AGG 产品页](https://www.ishares.com/us/products/239458/ishares-core-total-us-bond-market-etf)、[GLD 产品页](https://www.ssga.com/us/en/individual/etfs/spdr-gold-shares-gld)。

特别是 2800.HK 的 firstTradeDate 不是产品实际上市日，不能据此推断上市前后可投资性。接口将 GLD 标为 ETF，经济分类仍保留 gold_trust／physical gold；不能把供应商统一工具标签直接当成股票类别。排除个股模式将排除 AAPL、0700.HK，符合条件的 SPY、2800.HK 仍可选；实际规则在 S05 实现。

## 4. 价格、总收益及公司行动口径

本步显式设置 `interval=1d, auto_adjust=False, back_adjust=False, actions=True, repair=False, keepna=True, rounding=False`。`auto_adjust=False` 保留 Close 与 Adj Close 两列，**不代表 Close 是拆股前的原始成交报价**。

- Close：供应商已做拆股调整的历史收盘价，通常未做现金分红调整；不用拆股比例再次缩放。
- Adj Close：供应商调整价格，作为分红／拆股调整后的总收益代理；不是未经审计的官方总收益指数。之后若用 Adj Close 比值生成收益，不再次加分红。
- Dividends／Stock Splits／Capital Gains：原始事件分别保存；没有事件的普通日期可记事件量 0，缺价格或 FX 永远不能变成 0。
- 分红日诊断：同时列 Close 收益、现金再投资收益和 Adj Close 收益，展示差异，不强行令不同算法相等。

AAPL 在 2020-08-31 返回 4:1 拆股；Close 从 124.807503 到 129.039993，收益约 3.39117%，没有虚假的 −75% 跌幅。事件独立依据：[Apple 分红与拆股记录](https://investor.apple.com/dividend-history/default.aspx)。全部 256 条分红／拆股诊断见 corporate_actions.csv；分红诊断的最大绝对差约 0.001281（12.81 bps，2800.HK），须在 S03 解释供应商算法与事件日口径，不能称为总收益计算已验收。

## 5. 当前未验证的字段和分支

交易日历及逐日缺口、总收益构造、美港与 FX 的可得时点、HKD 无风险代理、基金费率的历史变化、实际点差／交易成本、穿透持仓、可借券及借券成本、退市产品和历史可投资名单均未在本步验收。Volume 可作为之后的流动性代理输入，但不是点差或成交能力保证。供应商 metadata 的现价、规模等是下载时信息，不能作为历史决策日特征。

S02 接着做 CSV／XLSX 字段映射、类型选择和质量报告；S03 再冻结 HKD 收益／时间规则；S04 只接入已验证路径并保持来源身份、失败状态与用户可选更新。现在没有界面更新按钮或完整下载器。
