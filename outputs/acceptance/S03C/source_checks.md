# S03-C 方法来源核查

核查日期：2026-10-16。此记录核查公开文档，不代表已下载历史报价或获得当时版本。

| 来源 | 本轮证据 | 实施含义 |
| --- | --- | --- |
| [HKMA daily interbank interest rates](https://apidocs.hkma.gov.hk/documentation/market-data-and-statistics/monthly-statistical-bulletin/er-ir/hk-interbank-ir-daily/) | 官方网页可读取；HIBOR Fixing 的 ir_1m 为 percent per annum，日期字段说明 as at11:15；区分 hibor.fixing、hibor、honia | 报价先除100，不能把年化百分数当月收益；只接受明确 HKAB_HIBOR/1M |
| [TMA Code](https://www.tma.org.hk/PubFile/TMACode.pdf) | 官方 PDF 可读取，印刷页52（PDF第53页）2.4 Interest accrual basis：港币交易使用 ACT/365，闰年分母仍365，并给出本金×r/100×实际天数/365示例 | 使用单利 ACT/365F 的计息基础；不支持把自然月研究近似声称为可投资存款合同 |
| [HKAB HIBOR](https://www.hkab.hk/en/rates/hibor) | 官方页面及规格链接可检索；规格PDF直接抓取超时 | 不宣称已通过PDF独立认证历史发布、修订和节假日规则；导入需声明当前版本 available_at |

明确的研究选择：月初锚点为上一自然月末香港16:00，期末锚点为本自然月末香港16:00；固定月初已知报价跨该月按实际日数简单计息。七天报价陈旧阈值由项目设定，不来自交易所日历。HIBOR有银行信用/流动性风险；本功能仅生成可核对的统计代理，不声称零风险、实际成交、已实现收益或真实合同期限完全一致。

本步没有新增实时数据调用；S01历史HKMA连通失败记录仍保留。S04另行实现更新和缓存；真实历史可得性不得用当前下载时间推断。
